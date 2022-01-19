from __future__ import annotations

import logging  # TODO: Migrate to structlog
import re
import textwrap
import webbrowser
from difflib import Differ
from itertools import zip_longest
from typing import TYPE_CHECKING, Any

import gidgethub
import gidgethub.httpx
import httpx
from yaml import dump

from ..config import RTDDumper, load_and_validate_config
from ..github import fork_repo, get_tip_sha, load_contents, update_contents
from ..migrators import Migrator
from ..types import RTDConfig

if TYPE_CHECKING:
    from gidgethub.abc import GitHubAPI

logger = logging.getLogger(__name__)

# https://github.com/readthedocs/readthedocs.org/blob/2e1b121d/readthedocs/config/config.py#L59
CONFIG_FILENAME_REGEX = r"^\.?readthedocs.ya?ml$"

PULL_REQUEST_BODY_TPL = """Howdy! :wave:

I am @readthedocs-assistant and I am sending you this pull request to
upgrade the configuration of your Read the Docs project.
Your project will continue working whether or not you merge it,
but I recommended you to take it into consideration.

Also, in case you haven't done it already, remember that you can
enable the pull request builds for your project
to see the effect of these changes.
To do it, [follow the
instructions](https://docs.readthedocs.io/en/stable/pull-requests.html),
close this pull request, and open it again.

_*Note*: This tool is in beta phase. Don't hesitate to ping
@astrojuanlu and/or @humitos if you spot any problems._

{migrator_summary}
---

Happy documenting! :sparkles:
"""

COMMIT_TPL = """Update Read the Docs configuration (automatic)

{migrators_summary}
"""

MIGRATOR_SUMMARY_TPL = """The following migrators were applied:

{migrators_fragments}"""

MIGRATOR_FRAGMENT_TPL = """- {migrator_one_liner}

{migrator_description}
"""


def unwrap_text(text: str) -> str:
    lines = text.splitlines()
    return "".join(line.strip() + " " if line else "\n\n" for line in lines)


def build_migrators_summary(migrators: list[Migrator], applied: list[bool]) -> str:
    migrators_fragments = []
    for migrator, applied in zip_longest(migrators, applied, fillvalue=False):
        if applied:
            migrators_fragments.append(
                MIGRATOR_FRAGMENT_TPL.format(
                    migrator_one_liner=migrator.__doc__.strip().splitlines()[0].strip(),
                    migrator_description=(
                        textwrap.dedent(
                            migrator.__doc__.split("\n\n", maxsplit=1)[1]
                        ).strip()
                    ),
                )
                if migrator.__doc__
                else f"- `{migrator.__class__.__name__}`"
            )

    return MIGRATOR_SUMMARY_TPL.format(
        migrators_fragments="\n".join(migrators_fragments)
    )


async def find_config(repo: Any, tip_sha: str, *, gh: GitHubAPI) -> Any:
    tree = await gh.getitem(f"/repos/{repo['full_name']}/git/trees/{tip_sha}")
    logger.debug(tree)

    for item in tree["tree"]:
        if item["type"] == "blob" and re.match(CONFIG_FILENAME_REGEX, item["path"]):
            # TODO: Error early if there are more than one config files
            return item


def compare_strings(s1: str, s2: str) -> str:
    d = Differ()
    result = d.compare(s1.splitlines(keepends=True), s2.splitlines(keepends=True))
    return "".join(result)


async def apply_migrators(
    config: RTDConfig, migrators: list[Migrator]
) -> tuple[RTDConfig, list[bool]]:
    new_config = config  # Initialize before iteration
    applied = []
    for migrator in migrators:
        logger.debug("Applying %s...", migrator.__class__.__name__)
        new_config, this_applied = await migrator.migrate(new_config)
        logger.debug("New config after step: %s", new_config)
        applied.append(this_applied)

    return new_config, applied


async def fork_and_update(
    target_repo: Any,
    config_item: Any,
    yaml_new_config: str,
    tip_sha: str,
    new_branch_name: str,
    migrators_summary: str,
    interactive: bool = True,
    *,
    gh: GitHubAPI,
) -> None:
    forked_repo = await fork_repo(target_repo, gh=gh)
    logger.info("%s created", forked_repo["full_name"])

    # TODO: Decide what to do if the branch already exists
    # At the moment it fails with an error "Reference already exists"
    await gh.post(
        f"/repos/{forked_repo['full_name']}/git/refs",
        data={
            "ref": f"refs/heads/{new_branch_name}",
            "sha": tip_sha,
        },
    )
    logger.info("New branch created successfully")

    await update_contents(
        forked_repo,
        config_item,
        yaml_new_config,
        branch_name=new_branch_name,
        message=COMMIT_TPL.format(migrators_summary=migrators_summary),
        gh=gh,
    )
    logger.info("Contents updated successfully")

    compare_url = await gh.getitem(
        f"/repos/{target_repo['full_name']}"
        f"/compare/{target_repo['default_branch']}..."
        f"{forked_repo['owner']['login']}:{new_branch_name}"
    )
    if interactive:
        logger.info(
            "Opening %s to see the changes",
            compare_url["html_url"],
        )
        webbrowser.open(compare_url["html_url"])
    else:
        logger.info("Browse %s to see the changes", compare_url["html_url"])

    # TODO: Create pull request if permission to write upstream
    # See https://github.com/readthedocs/readthedocs-assistant/issues/8


async def migrate_config(
    username: str,
    token: str,
    owner: str,
    repository_name: str,
    migrators: list[Migrator],
    new_branch_name: str = "update-rtd-config-assistant",
    interactive: bool = True,
    dry_run: bool = True,
) -> None:
    async with httpx.AsyncClient() as client:
        gh = gidgethub.httpx.GitHubAPI(client, username, oauth_token=token)

        all_repos = gh.getiter("/user/repos")
        logger.debug("%d repos found", len([r async for r in all_repos]))

        target_repo = await gh.getitem(f"/repos/{owner}/{repository_name}")
        logger.debug("Analyzing repository %s", target_repo["full_name"])

        tip_sha = await get_tip_sha(target_repo, gh=gh)

        config_item = await find_config(target_repo, tip_sha, gh=gh)
        assert config_item

        yaml_config = await load_contents(target_repo, config_item["path"], gh=gh)
        config, valid = await load_and_validate_config(yaml_config, raise_error=False)
        if not valid:
            logger.warning("Original config is invalid, proceeding anyway")

        # At this point, the repository is forked and the configuration is validated
        # and we can do whatever change we want to do
        logger.info("Current config: %s", config)

        new_config, applied = await apply_migrators(config, migrators)
        logger.info("New config: %s", new_config)

        if not any(applied):
            logger.info("No migration was applied, nothing else to do")
        elif any(applied) and new_config == config:
            logger.info(
                "At least one migration was applied but configuration did not change, "
                "nothing else to do"
            )
        else:
            logger.info(
                "At least one migration was applied and configuration changed, "
                "pull request is required!"
            )

            yaml_new_config = dump(new_config, Dumper=RTDDumper)
            migrators_summary = build_migrators_summary(migrators, applied)

            if not dry_run:
                await fork_and_update(
                    target_repo=target_repo,
                    config_item=config_item,
                    yaml_new_config=yaml_new_config,
                    tip_sha=tip_sha,
                    new_branch_name=new_branch_name,
                    migrators_summary=migrators_summary,
                    interactive=interactive,
                    gh=gh,
                )
            else:
                logger.info(
                    "Difference: \n%s", compare_strings(yaml_config, yaml_new_config)
                )
                logger.info(migrators_summary)
