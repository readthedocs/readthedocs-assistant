from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

import gidgethub
import gidgethub.httpx
import httpx

if TYPE_CHECKING:
    from gidgethub.abc import GitHubAPI


logger = logging.getLogger(__name__)


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
