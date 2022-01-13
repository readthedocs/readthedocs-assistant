from __future__ import annotations

from typing import Literal, TypedDict

Formats = Literal["htmlzip", "pdf", "epub"]
Tools = Literal["python", "nodejs", "rust", "golang"]


class LegacyV2Build(TypedDict, total=False):
    image: Literal["stable", "latest", "testing"]
    apt_packages: list[str]


class BaseV2Build(TypedDict):
    os: Literal["ubuntu-20.04"]
    tools: dict[Tools, str]


class V2Build(BaseV2Build, total=False):
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
    build: V2Build | LegacyV2Build  # FIXME: What about V1 build?
    python: Python
