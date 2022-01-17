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

    def __init_subclass__(cls: Type[Migrator], **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.registry[cls.__name__] = cls

    async def migrate(self, config: RTDConfig) -> tuple[RTDConfig, bool]:
        raise NotImplementedError


class UseBuildTools(Migrator):
    async def migrate(self, config: RTDConfig) -> tuple[RTDConfig, bool]:
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

        # Validate configuration before returning
        try:
            await validate_config(new_config)
        except jsonschema.exceptions.ValidationError:
            raise MigrationError(
                "Produced configuration is invalid, this is an internal problem"
            )

        return new_config, True
