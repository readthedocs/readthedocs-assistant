import logging
from typing import Any, cast

import httpx
from jsonschema import validate

from .types import RTDConfig

logger = logging.getLogger(__name__)

# https://www.schemastore.org/json/
SCHEMA_URL = (
    "https://raw.githubusercontent.com/readthedocs/readthedocs.org/"
    "master/readthedocs/rtd_tests/fixtures/spec/v2/schema.json"
)


async def validate_config(
    config: Any, schema_url: str = SCHEMA_URL, *, client: httpx.AsyncClient
) -> RTDConfig:
    resp_schema = await client.get(SCHEMA_URL)
    resp_schema.raise_for_status()
    schema = resp_schema.json()
    logger.debug(schema)

    validate(instance=config, schema=schema)

    return cast(RTDConfig, config)
