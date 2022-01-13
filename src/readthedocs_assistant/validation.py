from __future__ import annotations

import logging
from typing import Any, Dict, cast

import httpx
from jsonschema import validate

from .types import RTDConfig

logger = logging.getLogger(__name__)

# https://www.schemastore.org/json/
SCHEMA_URL = (
    "https://raw.githubusercontent.com/readthedocs/readthedocs.org/"
    "master/readthedocs/rtd_tests/fixtures/spec/v2/schema.json"
)

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
