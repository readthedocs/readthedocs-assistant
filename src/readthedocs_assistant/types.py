from __future__ import annotations

from typing import Literal, TypedDict, Union

Formats = Literal["htmlzip", "pdf", "epub"]
Tools = Literal["python", "nodejs", "rust", "golang"]
LegacyImages = Literal["stable", "latest", "testing"]


# The *Build classes below are designed in this contorted way
# to overcome the limited TypedDict semantics
# in a way that we can cover all the possible cases,
# while disallowing empty dictionaries.
# No validation is performed with respect to the version number.
# Still, there are some bugs in MyPy that prevent this from working:
# https://github.com/python/mypy/issues/11988

# If only "image" is present, it can either be v1 or v2
class LegacyImageBuild(TypedDict):
    image: LegacyImages


# If only "apt_packages" is present, it can only be v2
class APTPackagesBuild(TypedDict):
    apt_packages: list[str]


# It can also have both "image" and "apt_packages"
class LegacyV2BuildTotal(LegacyImageBuild, APTPackagesBuild):
    pass


# "New" v2 build is more sanely defined,
# but TypedDict does not allow marking individual keys
# as required or potentially-missing
# (see PEP 655 for background)
# and that's why we need two classes
class BaseV2Build(TypedDict):
    os: Literal["ubuntu-20.04"]
    tools: dict[Tools, str]


class V2Build(BaseV2Build, total=False):
    apt_packages: list[str]


# PEP 604 union syntax does not work for TypedDict,
# see https://github.com/python/typing/issues/1021
# Build = V2Build | LegacyImageBuild | APTPackagesBuild | LegacyV2BuildTotal
Build = Union[V2Build, LegacyImageBuild, APTPackagesBuild, LegacyV2BuildTotal]


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
