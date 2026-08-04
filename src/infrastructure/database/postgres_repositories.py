from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from psycopg import Connection, sql

from src.domain.models import ColumnMetadata


class PostgresMetadataRepository:
    def __init__(self, connect: Callable[[], Connection], schemas: tuple[str, ...]) -> None:
        self._connect = connect
        self._schemas = schemas

    def columns(self) -> Sequence[ColumnMetadata]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_schema, table_name, column_name, ordinal_position,
                       data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = ANY(%s)
                ORDER BY table_schema, table_name, ordinal_position
                """,
                (list(self._schemas),),
            )
            return tuple(
                ColumnMetadata(*row[:5], nullable=row[5] == "YES")
                for row in cursor.fetchall()
            )

    def relationships(self) -> tuple[()]:
        return ()


class PostgresSourceRepository:
    def __init__(self, connect: Callable[[], Connection], schemas: tuple[str, ...]) -> None:
        self._connect = connect
        self._schemas = schemas

    def table_names(self) -> tuple[str, ...]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_schema, table_name FROM information_schema.tables
                WHERE table_type='BASE TABLE' AND table_schema = ANY(%s)
                ORDER BY table_schema, table_name
                """,
                (list(self._schemas),),
            )
            return tuple(f"{schema}.{table}" for schema, table in cursor.fetchall())

    def row_counts(self) -> dict[str, int]:
        with self._connect() as connection, connection.cursor() as cursor:
            counts = {}
            for qualified in self.table_names():
                schema_name, table_name = qualified.split(".")
                cursor.execute(
                    sql.SQL("SELECT count(*) FROM {}.{}").format(
                        sql.Identifier(schema_name), sql.Identifier(table_name)
                    )
                )
                counts[qualified] = cursor.fetchone()[0]
            return counts

    def ordered_rows(self, table_name: str) -> Sequence[tuple[Any, ...]]:
        raise NotImplementedError("Ordered source reads require an explicit column and key projection.")


class PostgresMaskedRepository:
    """Transaction-bound target adapter; DDL is delegated by the masking application service."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def reset_structure(self) -> None:
        raise NotImplementedError("Structure reset requires the validated masking load plan.")

    def insert_rows(self, table_name: str, rows: Sequence[tuple[Any, ...]]) -> None:
        raise NotImplementedError("Insertion requires explicit validated column metadata.")

    def row_counts(self) -> dict[str, int]:
        raise NotImplementedError("Masked schemas must be supplied by the application context.")
