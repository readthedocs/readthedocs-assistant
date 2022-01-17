from __future__ import annotations

import asyncio
import base64
import logging  # TODO: Migrate to structlog
import re
from difflib import Differ
from typing import TYPE_CHECKING, Any

import click
import gidgethub
import gidgethub.httpx
import httpx
from yaml import Loader, dump, load

from .io import RTDDumper
from .migrators import Migrator
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


async def update_contents(
    repo: Any,
    blob: Any,
    new_contents: str,
    branch_name: str,
    encoding: str = "utf-8",
    *,
    gh: GitHubAPI,
) -> None:
    await gh.put(
        f"/repos/{repo['full_name']}/contents/{blob['path']}",
        data={
            "message": "Update RTD configuration (automatic)",
            "content": base64.b64encode(new_contents.encode(encoding)).decode("ascii"),
            "sha": blob["sha"],
            "branch": branch_name,
        },
    )


def compare_strings(s1: str, s2: str) -> str:
    d = Differ()
    result = d.compare(s1.splitlines(keepends=True), s2.splitlines(keepends=True))
    return "".join(result)


async def migrate_config(
    username: str,
    token: str,
    owner: str,
    repository_name: str,
    migrators: list[Migrator],
    new_branch_name: str = "assistant-update-config",
    dry_run: bool = True,
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

        new_config = config  # Initialize before iteration
        applied = []
        for migrator in migrators:
            logger.debug("Applying %s...", migrator.__class__.__name__)
            new_config, this_applied = await migrator.migrate(new_config)
            logger.debug("New config after step: %s", new_config)
            applied.append(this_applied)

        logger.info("New config: %s", new_config)

        if not any(applied):
            logger.info("No migration was applied, nothing else to do")
        elif any(applied) and new_config == config:
            # Useful if we want to "mark project as migrated" somehow
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

            if not dry_run:
                forked_repo = await fork_repo(target_repo, gh=gh)
                logger.info("%s created", forked_repo["full_name"])

                await gh.post(
                    f"/repos/{forked_repo['full_name']}/git/refs",
                    data={
                        "ref": f"refs/heads/{new_branch_name}",
                        "sha": default_branch["commit"]["sha"],
                    },
                )
                logger.info("New branch created successfully")

                await update_contents(
                    forked_repo,
                    config_item,
                    yaml_new_config,
                    branch_name=new_branch_name,
                    gh=gh,
                )
                logger.info("Contents updated successfully")

                compare_url = await gh.getitem(
                    f"/repos/{forked_repo['full_name']}"
                    f"/compare/{forked_repo['default_branch']}...{new_branch_name}"
                )
                logger.info(
                    "Browse %s to see the changes",
                    compare_url["html_url"],
                )

                # TODO: Create pull request with message
            else:
                logger.info(
                    "Difference: \n%s", compare_strings(yaml_config, yaml_new_config)
                )


def parse_migrators(migrator_names_str: str) -> list[Migrator]:
    migrators = []
    for migrator_name in migrator_names_str.split(","):
        MigratorClass = Migrator.registry[migrator_name]
        migrators.append(MigratorClass())
    return migrators


@click.command()
@click.option("--username", required=True)
@click.option("--password-or-token", required=True)
@click.option("--repository-owner", required=True)
@click.option("--repository-name", required=True)
@click.option(
    "--migrator-names", required=True, help="Comma-separated list of migrators"
)
@click.option("--run-migration", default=False)
@click.option("-d", "--debug", is_flag=True, default=False)
def main(
    username: str,
    password_or_token: str,
    repository_owner: str,
    repository_name: str,
    migrator_names: str,
    run_migration: bool,
    debug: bool,
) -> None:
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)

    asyncio.run(
        migrate_config(
            username,
            password_or_token,
            repository_owner,
            repository_name,
            migrators=parse_migrators(migrator_names),
            dry_run=not run_migration,
        )
    )


if __name__ == "__main__":
    # TODO: Detect migrations and write small report
    main()
