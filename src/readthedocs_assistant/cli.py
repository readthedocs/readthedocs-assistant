from __future__ import annotations

import asyncio
import functools
import logging
import os
import re
from typing import TYPE_CHECKING

import aiofiles
import gidgethub
import gidgethub.httpx
import httpx
import pygit2

if TYPE_CHECKING:
    from gidgethub.abc import GitHubAPI


logger = logging.getLogger(__name__)


# https://github.com/readthedocs/readthedocs.org/blob/2e1b121d/readthedocs/config/config.py#L59
CONFIG_FILENAME_REGEX = r"^\.?readthedocs.ya?ml$"


# https://github.com/readthedocs/readthedocs.org/blob/bc3e1477/readthedocs/config/find.py#L9-L16
def find_one(path, filename_regex):
    """Find the first file in ``path`` that match ``filename_regex`` regex."""
    _path = os.path.abspath(path)
    for filename in os.listdir(_path):
        if re.match(filename_regex, filename):
            return os.path.join(_path, filename)

    return ""


find_config = functools.partial(find_one, filename_regex=CONFIG_FILENAME_REGEX)


async def clone_repo(clone_url: str, target_dir: str, *, loop=None):
    loop = loop or asyncio.get_running_loop()

    logger.info("Cloning repository %s in %s", clone_url, target_dir)
    repo = await loop.run_in_executor(
        None, functools.partial(pygit2.clone_repository, clone_url, target_dir)
    )

    logger.debug(repo.path)


async def fork_repo(owner: str, repository_name: str, *, gh: GitHubAPI):
    # Create fork
    try:
        await gh.post(f"/repos/{owner}/{repository_name}/forks", data={})
    except gidgethub.HTTPException as exc:
        # 202 ACCEPTED raises an error,
        # see https://github.com/brettcannon/gidgethub/issues/171
        if exc.status_code != 202:
            raise

    # Retrieve forked project
    while True:
        try:
            # Idempotent, if it already exists, doesn't do anything
            # +gh_repo
            forked_repo = await gh.getitem(
                f"/repos/readthedocs-assistant/{repository_name}"
            )
        except gidgethub.BadRequest:
            # TODO: Is this necessary?
            # The doc says "You may have to wait a short period of time
            # before you can access the git objects",
            # but perhaps the repository object is available immediately
            logger.info("Does not exist yet, retrying")
            await asyncio.sleep(5)
        else:
            logging.info("%s created", forked_repo["full_name"])
            break

    return forked_repo


async def main(username: str, token: str, owner: str, repository_name: str):
    async with httpx.AsyncClient() as client:
        gh = gidgethub.httpx.GitHubAPI(client, username, oauth_token=token)

        all_repos = gh.getiter("/user/repos")
        logger.debug("%d repos found", len([r async for r in all_repos]))

        forked_repo = await fork_repo(owner, repository_name, gh=gh)
        logger.debug(forked_repo["full_name"])

    async with aiofiles.tempfile.TemporaryDirectory() as temp_dir:
        # TODO: Do we need a local clone?
        # https://github3.readthedocs.io/en/latest/examples/github.html#create-a-commit-to-change-an-existing-file
        await clone_repo(forked_repo["clone_url"], temp_dir)

        config_file = find_config(temp_dir)
        logger.debug(config_file)
        assert config_file

        # TODO: Validate schema
        # https://github.com/readthedocs/readthedocs.org/blob/master/readthedocs/rtd_tests/fixtures/spec/v2/schema.json


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # For testing purposes
    asyncio.run(
        main(
            os.environ["GH_USERNAME"],
            os.environ["GH_TOKEN"],
            "jupyterlite",
            "jupyterlite",
        )
    )
