from __future__ import annotations

import asyncio
import base64
import logging  # TODO: Migrate to structlog
import os
import re
from difflib import Differ
from typing import TYPE_CHECKING, Any

import gidgethub
import gidgethub.httpx
import httpx
from yaml import Loader, dump, load

from .io import RTDDumper
from .migrators import use_build_tools
from .validation import validate_config

if TYPE_CHECKING:
    from gidgethub.abc import GitHubAPI


logger = logging.getLogger(__name__)

# https://github.com/readthedocs/readthedocs.org/blob/2e1b121d/readthedocs/config/config.py#L59
CONFIG_FILENAME_REGEX = r"^\.?readthedocs.ya?ml$"


async def fork_repo(repo: Any, *, gh: GitHubAPI) -> Any:
    # Create fork
    try:
        await gh.post(f"/repos/{repo['full_name']}/forks", data={})
    except gidgethub.HTTPException as exc:
        # 202 ACCEPTED raises an error,
        # see https://github.com/brettcannon/gidgethub/issues/171
        if exc.status_code != 202:
            raise

    forked_repo = await gh.getitem(f"/repos/readthedocs-assistant/{repo['name']}")
    logger.debug(forked_repo)
    return forked_repo


async def find_config(repo: Any, branch: Any, *, gh: GitHubAPI) -> Any:
    tree = await gh.getitem(
        f"/repos/{repo['full_name']}/git/trees/{branch['commit']['sha']}"
    )
    logger.debug(tree)

    for item in tree["tree"]:
        if item["type"] == "blob" and re.match(CONFIG_FILENAME_REGEX, item["path"]):
            # TODO: Error early if there are more than one config files
            return item


async def load_contents(
    repo: Any, path: str, encoding: str = "utf-8", *, gh: GitHubAPI
) -> str:
    file_contents = await gh.getitem(f"/repos/{repo['full_name']}/contents/{path}")
    content = base64.b64decode(file_contents["content"].encode("ascii")).decode(
        encoding
    )
    return content


def compare_strings(s1: str, s2: str) -> str:
    d = Differ()
    result = d.compare(s1.splitlines(keepends=True), s2.splitlines(keepends=True))
    return "".join(result)


async def main(
    username: str, token: str, owner: str, repository_name: str, dry_run: bool = True
) -> None:
    async with httpx.AsyncClient() as client:
        gh = gidgethub.httpx.GitHubAPI(client, username, oauth_token=token)

        all_repos = gh.getiter("/user/repos")
        logger.debug("%d repos found", len([r async for r in all_repos]))

        target_repo = await gh.getitem(f"/repos/{owner}/{repository_name}")
        logger.debug("Analyzing repository %s", target_repo["full_name"])

        default_branch = await gh.getitem(
            f"/repos/{target_repo['full_name']}"
            f"/branches/{target_repo['default_branch']}"
        )

        config_item = await find_config(target_repo, default_branch, gh=gh)
        assert config_item

        yaml_config = await load_contents(target_repo, config_item["path"], gh=gh)

        unvalidated_config = load(yaml_config, Loader=Loader)
        config = await validate_config(unvalidated_config)

        # At this point, the repository is forked and the configuration is validated
        # and we can do whatever change we want to do
        logger.info("Current config: %s", config)

        # For example, migrate to build.tools
        new_config, applied = await use_build_tools(config)

        logger.info("New config: %s", new_config)

        if not applied:
            logger.info("Migration was not applied, nothing else to do")
        elif applied and new_config == config:
            # Useful if we want to "mark project as migrated" somehow
            logger.info(
                "Migration was applied with no changes in configuration, "
                "nothing else to do"
            )
        else:
            logger.info(
                "Migration was applied and configuration was changed, "
                "pull request is required"
            )

            yaml_new_config = dump(new_config, Dumper=RTDDumper)

            if not dry_run:
                forked_repo = await fork_repo(target_repo, gh=gh)
                logger.info("%s created", forked_repo["full_name"])

                # TODO: Commit contents to separate branch and push
                # TODO: Create pull request with message
            else:
                logger.info(
                    "Difference: \n%s", compare_strings(yaml_config, yaml_new_config)
                )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # TODO: Add cli parameter to pick migrator
    # TODO: Detect migrations and write small report
    asyncio.run(
        main(
            os.environ["GH_USERNAME"],
            os.environ["GH_TOKEN"],
            "jupyterlite",  # TODO: Do not hardcode repositories
            "jupyterlite",
        )
    )
