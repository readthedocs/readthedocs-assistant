import base64
from typing import Any

import gidgethub
import gidgethub.httpx
from gidgethub.abc import GitHubAPI


async def get_tip_sha(repo: Any, *, gh: GitHubAPI) -> str:
    default_branch = await gh.getitem(
        f"/repos/{repo['full_name']}" f"/branches/{repo['default_branch']}"
    )
    tip_sha = str(default_branch["commit"]["sha"])
    return tip_sha


async def fork_repo(repo: Any, *, gh: GitHubAPI) -> Any:
    # Create fork
    try:
        await gh.post(f"/repos/{repo['full_name']}/forks", data={})
    except gidgethub.HTTPException as exc:
        # 202 ACCEPTED raises an error,
        # see https://github.com/brettcannon/gidgethub/issues/171
        if exc.status_code != 202:
            raise

    # Retrieve forked repo
    forked_repo = await gh.getitem(f"/repos/readthedocs-assistant/{repo['name']}")
    return forked_repo


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
    message: str,
    encoding: str = "utf-8",
    *,
    gh: GitHubAPI,
) -> None:
    await gh.put(
        f"/repos/{repo['full_name']}/contents/{blob['path']}",
        data={
            "message": message,
            "content": base64.b64encode(new_contents.encode(encoding)).decode("ascii"),
            "sha": blob["sha"],
            "branch": branch_name,
        },
    )
