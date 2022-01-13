from __future__ import annotations

import logging

from .types import RTDConfig

logger = logging.getLogger(__name__)


class MigrationError(RuntimeError):
    pass


async def use_build_tools(config: RTDConfig) -> tuple[RTDConfig, bool]:
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
