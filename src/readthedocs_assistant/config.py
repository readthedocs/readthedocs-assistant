from __future__ import annotations

import logging
from typing import Any, Dict, cast

import httpx
from jsonschema import ValidationError, validate
from yaml import Dumper, Loader, load

from .types import RTDConfig

logger = logging.getLogger(__name__)

# https://www.schemastore.org/json/
SCHEMA_URL = (
    "https://raw.githubusercontent.com/readthedocs/readthedocs.org/"
    "master/readthedocs/rtd_tests/fixtures/spec/v2/schema.json"
)

# This list specifies the order in which the keys will appear in the config
# We only care about primary ones, the inner ones will be sorted alphabetically
# TODO: Make indentation configurable
# TODO: Add one empty line after each config block?
# TODO: Retain comments?
SORTED_KEYS = ["version", "build", "sphinx", "python", "method", "path", "extra_requirements", "conda", "formats"]

Schema = Dict[str, Any]


async def _get_schema(schema_url: str = SCHEMA_URL) -> Schema:
    async with httpx.AsyncClient() as client:
        resp_schema = await client.get(SCHEMA_URL)
        resp_schema.raise_for_status()
        schema = resp_schema.json()

    return cast(Schema, schema)


async def validate_config(config: Any, schema: Schema | None = None) -> RTDConfig:
    # TODO: Cache schema
    if not schema:
        schema = await _get_schema()
    logger.debug("Using schema: %s", schema)

    validate(instance=config, schema=schema)

    return cast(RTDConfig, config)


def rtd_key_sorting(item):
    return SORTED_KEYS.index(item[0])


class RTDDumper(Dumper):
    def represent_dict_custom_order(self, data):
        try:
            items = sorted(data.items(), key=rtd_key_sorting)
            return self.represent_dict(items)
        except ValueError:
            # A sub-dictionary from the config
            # Let it be dumped with the usual method
            return super().represent_dict(data)


RTDDumper.add_representer(dict, RTDDumper.represent_dict_custom_order)


async def load_and_validate_config(
    yaml_config: str, raise_error: bool
) -> tuple[RTDConfig | Any, bool]:
    unvalidated_config = load(yaml_config, Loader=Loader)
    try:
        config = await validate_config(unvalidated_config)
    except ValidationError as exc:
        if raise_error:
            raise exc
        else:
            logger.error("Config is invalid: %s", exc)
            return unvalidated_config, False
    else:
        return config, True
