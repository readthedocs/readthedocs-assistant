import pytest

from readthedocs_assistant.migrators import use_build_tools


@pytest.mark.parametrize(
    "config, expected_config",
    [
        [
            {
                "version": 2,
            },
            {"version": 2, "build": {"os": "ubuntu-20.04", "tools": {"python": "3.7"}}},
        ],
        [
            {"version": 2, "python": {"version": "3.8"}},
            {"version": 2, "build": {"os": "ubuntu-20.04", "tools": {"python": "3.8"}}},
        ],
        [
            {
                "version": 2,
                "python": {
                    "version": "3.8",
                    "install": [{"requirements": "requirements.txt"}],
                },
            },
            {
                "version": 2,
                "build": {"os": "ubuntu-20.04", "tools": {"python": "3.8"}},
                "python": {"install": [{"requirements": "requirements.txt"}]},
            },
        ],
    ],
)
@pytest.mark.asyncio
async def test_use_build_tools_returns_expected_config(config, expected_config):
    new_config, applied = await use_build_tools(config)

    assert new_config == expected_config
    assert applied
