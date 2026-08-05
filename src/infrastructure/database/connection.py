from __future__ import annotations

from collections.abc import Callable

import psycopg

from src.infrastructure.config.settings import DatabaseSettings
from src.shared.errors import DatabaseUnavailableError


def get_connection(settings: DatabaseSettings | None = None) -> psycopg.Connection:
    resolved = settings or DatabaseSettings.from_environment()
    try:
        return psycopg.connect(
            dbname=resolved.database,
            user=resolved.user,
            password=resolved.password,
            host=resolved.host,
            port=resolved.port,
        )
    except psycopg.OperationalError as error:
        raise DatabaseUnavailableError("PostgreSQL is unavailable.") from error


def connection_factory(settings: DatabaseSettings | None = None) -> Callable[[], psycopg.Connection]:
    resolved = settings or DatabaseSettings.from_environment()
    return lambda: get_connection(resolved)
