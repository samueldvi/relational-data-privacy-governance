from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from src.shared.errors import ConfigurationError


# Compatibility bootstrap at the infrastructure boundary; never imported by domain code.
load_dotenv()


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    database: str
    user: str
    password: str
    host: str
    port: int

    @classmethod
    def from_environment(cls) -> "DatabaseSettings":
        required = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT")
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise ConfigurationError("Missing required PostgreSQL environment configuration.")
        try:
            port = int(os.environ["POSTGRES_PORT"])
        except ValueError as error:
            raise ConfigurationError("POSTGRES_PORT must be an integer.") from error
        return cls(
            database=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"], host=os.environ["POSTGRES_HOST"],
            port=port,
        )
