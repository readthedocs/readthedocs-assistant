from __future__ import annotations

import logging
from typing import Any, Type

import jsonschema

from .types import RTDConfig
from .validation import validate_config

logger = logging.getLogger(__name__)


class MigrationError(RuntimeError):
    pass


class Migrator:
    registry = {}  # type: dict[str, Type[Migrator]]

    # This magic method registers the subclass when it's created
    # see PEP 487
    def __init_subclass__(cls: Type[Migrator], **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.registry[cls.__name__] = cls

    # This does do_migrate + new config validation
    # So that subclasses only need to implement do_migrate
    async def migrate(self, config: RTDConfig) -> tuple[RTDConfig, bool]:
        new_config, migration_applied = await self.do_migrate(config)
        await self.__validate(new_config)

        return new_config, migration_applied

    async def do_migrate(self, config: RTDConfig) -> tuple[RTDConfig, bool]:
        raise NotImplementedError

    # Validates that the new configuration is valid
    # Mangled so it's not easily overridden by subclasses
    async def __validate(self, new_config: RTDConfig) -> None:
        try:
            await validate_config(new_config)
        except jsonschema.exceptions.ValidationError:
            raise MigrationError(
                "Produced configuration is invalid, this is an internal problem"
            )


class UseBuildTools(Migrator):
    async def do_migrate(self, config: RTDConfig) -> tuple[RTDConfig, bool]:
        """Migrate to build.tools configuration

        See https://docs.readthedocs.io/en/latest/config-file/v2.html#build.
        """
        if config.get("version", 1) < 2:
            raise MigrationError("Config uses V1, migrate to V2 first")

        if "tools" in config.get("build", {}):
            logger.info("Config already contains build.tools, nothing to do")
            return config, False

        new_config = config.copy()

        # Very old docker images used Python 3.5, but they are not in use anymore
        # From 4.0 onwards, the default Python version was 3.7
        if "conda" in new_config:
            # https://github.com/readthedocs/readthedocs.org/issues/8595
            python_version = "miniconda3-4.7"
        else:
            python_version = config.get("python", {}).get("version", "3.7")

        new_config["build"] = {
            "os": "ubuntu-20.04",
            "tools": {"python": python_version},
        }
        if apt_packages := new_config.get("build", {}).get("apt_packages", []):
            new_config["build"]["apt_packages"] = apt_packages

        # Drop python.version if it exists
        new_config.get("python", {}).pop("version", None)

        # If python has no keys left, drop it altogether
        if "python" in new_config and not new_config["python"]:
            new_config.pop("python")

        return new_config, True


class UseMamba(Migrator):
    async def do_migrate(self, config: RTDConfig) -> tuple[RTDConfig, bool]:
        """Migrate to Mamba as a drop-in replacement for Conda."""
        if config.get("version", 1) < 2:
            raise MigrationError("Config uses V1, migrate to V2 first")

        if "conda" not in config:
            raise MigrationError(
                "Conda environment not specified, config does not use conda"
            )

        python_version = config.get("build", {}).get("tools", {}).get("python", "")
        if "miniconda" not in python_version:
            raise MigrationError(
                f"Python version set to '{python_version}' instead of Miniconda, "
                "run UseBuildTools migration first"
            )

        if "mamba" in python_version:
            logger.info("Config already uses Mamba, nothing to do")
            return config, False

        new_config = config.copy()
        new_config["build"]["tools"]["python"] = "mambaforge-4.10"

        return new_config, True
