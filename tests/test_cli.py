from unittest import mock

import pytest
from gidgethub.abc import GitHubAPI

from readthedocs_assistant.cli import fork_repo


@mock.patch("readthedocs_assistant.cli.gidgethub.httpx.GitHubAPI", spec=GitHubAPI)
@pytest.mark.asyncio
async def test_fork_repo_awaits_fork_repo(mock_gh):
    target_repo = {"full_name": "owner/repo", "name": "repo"}
    await fork_repo(target_repo, gh=mock_gh)

    mock_gh.post.assert_awaited_once_with("/repos/owner/repo/forks", data={})
