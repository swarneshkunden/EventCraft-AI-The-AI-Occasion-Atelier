"""Copy application rows from SQLite to an empty PostgreSQL database."""
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Engine, Table, create_engine, func, inspect, select, text
from sqlalchemy.engine import Connection, URL, make_url
from sqlalchemy.exc import SQLAlchemyError

from app.config.settings import normalize_database_url
from app.models import models  # noqa: F401
from app.config.database import Base


EXPECTED_ALEMBIC_HEAD = "51d2a6f89c43"
BATCH_SIZE = 500
APPLICATION_TABLES = tuple(Base.metadata.sorted_tables)
APPLICATION_TABLE_NAMES = {table.name for table in APPLICATION_TABLES}


def _readonly_sqlite_url(value: str) -> URL:
    url = make_url(value)
    if url.get_backend_name() != "sqlite":
        raise ValueError("SOURCE_DATABASE_URL must be a SQLite URL.")
    database = url.database
    if database and not database.startswith("file:"):
        database = f"file:{Path(database).resolve().as_posix()}"
    return url.set(database=database, query={**url.query, "mode": "ro", "uri": "true"})


def _postgres_url(value: str) -> URL:
    url = make_url(normalize_database_url(value))
    if url.get_backend_name() != "postgresql" or url.drivername != "postgresql+psycopg":
        raise ValueError("TARGET_DATABASE_URL must use PostgreSQL with psycopg 3.")
    if (url.host or "").endswith(".neon.tech") and url.query.get("sslmode") != "require":
        raise ValueError("Neon TARGET_DATABASE_URL must include sslmode=require.")
    return url


def _schema_tables(connection: Connection, *, source: bool) -> None:
    actual_tables = set(inspect(connection).get_table_names())
    expected_tables = APPLICATION_TABLE_NAMES
    allowed_tables = expected_tables | {"alembic_version"}
    missing = expected_tables - actual_tables
    unexpected = actual_tables - allowed_tables
    if missing or unexpected:
        raise ValueError(
            "Database tables do not match the application schema "
            f"(missing={sorted(missing)}, unexpected={sorted(unexpected)})."
        )

    for table in APPLICATION_TABLES:
        actual_columns = {
            column["name"] for column in inspect(connection).get_columns(table.name)
        }
        expected_columns = {column.name for column in table.columns}
        if actual_columns != expected_columns:
            raise ValueError(f"Column layout does not match for table {table.name}.")

    if not source:
        try:
            revisions = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalars().all()
        except SQLAlchemyError as exc:
            raise ValueError("Target must be migrated to the current Alembic head.") from exc
        if revisions != [EXPECTED_ALEMBIC_HEAD]:
            raise ValueError("Target must be migrated to the current Alembic head.")


def _lock_target_tables(connection: Connection) -> None:
    preparer = connection.dialect.identifier_preparer
    for table in APPLICATION_TABLES:
        name = preparer.quote(table.name)
        connection.execute(text(f"LOCK TABLE {name} IN SHARE ROW EXCLUSIVE MODE"))


def _table_counts(connection: Connection) -> dict[str, int]:
    return {
        table.name: connection.execute(
            select(func.count()).select_from(table)
        ).scalar_one()
        for table in APPLICATION_TABLES
    }


def _utc_values(table: Table, row: Any) -> dict[str, Any]:
    values = dict(row)
    for column in table.columns:
        if column.name not in values:
            continue
        value = values[column.name]
        if (
            value is not None
            and isinstance(column.type, DateTime)
            and column.type.timezone
            and isinstance(value, datetime)
            and value.tzinfo is None
        ):
            values[column.name] = value.replace(tzinfo=timezone.utc)
    return values


def _copy_rows(source: Connection, target: Connection) -> dict[str, int]:
    expected_counts = _table_counts(source)
    target_counts = _table_counts(target)
    nonempty = {name: count for name, count in target_counts.items() if count}
    if nonempty:
        raise ValueError(
            "Refusing to copy into a non-empty target; rows exist in "
            f"{sorted(nonempty)}."
        )

    for table in APPLICATION_TABLES:
        rows = source.execution_options(stream_results=True).execute(
            select(table)
        ).mappings()
        while batch := rows.fetchmany(BATCH_SIZE):
            target.execute(
                table.insert(),
                [_utc_values(table, row) for row in batch],
            )

    copied_counts = _table_counts(target)
    if copied_counts != expected_counts:
        raise RuntimeError("Copied row counts do not match the SQLite source.")
    return copied_counts


def copy_database(source_value: str, target_value: str, confirmed_host: str) -> dict[str, int]:
    source_url = _readonly_sqlite_url(source_value)
    target_url = _postgres_url(target_value)
    if not confirmed_host or confirmed_host.casefold() != (target_url.host or "").casefold():
        raise ValueError(
            "--confirm-target must exactly match the PostgreSQL hostname in "
            "TARGET_DATABASE_URL."
        )

    source_engine = create_engine(source_url, pool_pre_ping=True)
    target_engine = create_engine(
        target_url,
        connect_args={"connect_timeout": 5},
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
    )
    try:
        with source_engine.connect() as source_connection:
            with source_connection.begin():
                _schema_tables(source_connection, source=True)
                with target_engine.begin() as target_connection:
                    _schema_tables(target_connection, source=False)
                    _lock_target_tables(target_connection)
                    return _copy_rows(source_connection, target_connection)
    finally:
        source_engine.dispose()
        target_engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-target",
        required=True,
        help="Exact PostgreSQL hostname to authorize for this copy.",
    )
    args = parser.parse_args()

    source_url = os.environ.get("SOURCE_DATABASE_URL")
    target_url = os.environ.get("TARGET_DATABASE_URL")
    if not source_url or not target_url:
        parser.error("Set SOURCE_DATABASE_URL and TARGET_DATABASE_URL in the environment.")

    try:
        counts = copy_database(source_url, target_url, args.confirm_target)
    except (SQLAlchemyError, ValueError, RuntimeError) as exc:
        print(f"Copy failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    for table_name, count in counts.items():
        print(f"{table_name}: {count}")
    print("Copy committed. Source row counts match PostgreSQL target counts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
