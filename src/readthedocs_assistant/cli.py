from __future__ import annotations

import asyncio
import logging  # TODO: Migrate to structlog

import click

from .commands import migrate_config
from .migrators import Migrator

logger = logging.getLogger(__name__)


def parse_migrators(migrator_names_str: str) -> list[Migrator]:
    migrators = []
    for migrator_name in migrator_names_str.split(","):
        MigratorClass = Migrator.registry[migrator_name]
        migrators.append(MigratorClass())
    return migrators


@click.command()
@click.option("--username", required=True)
@click.option("--password-or-token", required=True)
@click.option("--repository-owner", required=True)
@click.option("--repository-name", required=True)
@click.option(
    "--migrator-names", required=True, help="Comma-separated list of migrators"
)
@click.option("--run-migration", is_flag=True, default=False)
@click.option("--interactive/--no-interactive", is_flag=True, default=True)
@click.option("-d", "--debug", is_flag=True, default=False)
def main(
    username: str,
    password_or_token: str,
    repository_owner: str,
    repository_name: str,
    migrator_names: str,
    run_migration: bool,
    interactive: bool,
    debug: bool,
) -> None:
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)

    asyncio.run(
        migrate_config(
            username,
            password_or_token,
            repository_owner,
            repository_name,
            migrators=parse_migrators(migrator_names),
            interactive=interactive,
            dry_run=not run_migration,
        )
    )


if __name__ == "__main__":
    # TODO: Detect migrations and write small report
    main()
