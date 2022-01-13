from __future__ import annotations

from typing import Literal, TypedDict

Formats = Literal["htmlzip", "pdf", "epub"]
Tools = Literal["python", "nodejs", "rust", "golang"]


# This class mixes several possible specifications
# depending on the configuration version,
# but it turns out that crafting a proper specification
# using Python TypedDict is not possible and also fraught with bugs
# See https://github.com/python/mypy/issues/11988
class Build(TypedDict, total=False):
    os: Literal["ubuntu-20.04"]
    tools: dict[Tools, str]
    image: Literal["stable", "latest", "testing"]
    apt_packages: list[str]


class PythonRequirements(TypedDict):
    requirements: str


class PythonInstallPath(TypedDict):
    path: str
    method: Literal["pip", "setuptools"]
    extra_requirements: list[str]


class Python(TypedDict, total=False):
    version: str
    system_packages: bool
    install: list[PythonRequirements | PythonInstallPath]


class RTDConfig(TypedDict, total=False):
    version: int
    formats: list[Formats]
    build: Build
    python: Python
