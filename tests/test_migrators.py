import pytest

from readthedocs_assistant.migrators import UseBuildTools, UseMamba


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
async def test_use_build_tools_returns_expected_config_simple(config, expected_config):
    migrator = UseBuildTools()
    new_config, applied = await migrator.migrate(config)

    assert new_config == expected_config
    assert applied


@pytest.mark.parametrize(
    "config, expected_config",
    [
        [
            {"version": 2, "conda": {"environment": "environment.yml"}},
            {
                "version": 2,
                "build": {
                    "os": "ubuntu-20.04",
                    "tools": {"python": "miniconda3-4.7"},
                },
                "conda": {"environment": "environment.yml"},
            },
        ],
        [
            {
                "version": 2,
                "conda": {"environment": "environment.yml"},
                "python": {"version": "3.9"},
            },
            {
                "version": 2,
                "build": {
                    "os": "ubuntu-20.04",
                    "tools": {"python": "miniconda3-4.7"},
                },
                "conda": {"environment": "environment.yml"},
            },
        ],
    ],
)
@pytest.mark.asyncio
async def test_use_build_tools_returns_expected_config_conda(config, expected_config):
    migrator = UseBuildTools()
    new_config, applied = await migrator.migrate(config)

    assert new_config == expected_config
    assert applied


@pytest.mark.parametrize(
    "config, expected_config",
    [
        [
            {
                "version": 2,
                "build": {
                    "os": "ubuntu-20.04",
                    "tools": {"python": "miniconda3-4.7"},
                },
                "conda": {"environment": "environment.yml"},
            },
            {
                "version": 2,
                "build": {
                    "os": "ubuntu-20.04",
                    "tools": {"python": "mambaforge-4.10"},
                },
                "conda": {"environment": "environment.yml"},
            },
        ],
    ],
)
@pytest.mark.asyncio
async def test_use_mamba_returns_expected_config(config, expected_config):
    migrator = UseMamba()
    new_config, applied = await migrator.migrate(config)

    assert new_config == expected_config
    assert applied
