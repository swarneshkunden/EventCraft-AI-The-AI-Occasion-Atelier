"""Safety and row-preservation checks for the opt-in database copy utility."""
from datetime import UTC, datetime

import pytest
from scripts.copy_sqlite_to_postgres import (
    _copy_rows,
    _readonly_sqlite_url,
    _utc_values,
    copy_database,
)
from sqlalchemy import create_engine, insert, select

from app.config.database import Base
from app.models import models  # noqa: F401


def test_source_url_is_read_only_and_requires_sqlite(tmp_path, monkeypatch):
    source_path = tmp_path / "source database.db"
    source_path.touch()
    monkeypatch.chdir(tmp_path)
    url = _readonly_sqlite_url("sqlite:///source database.db")

    assert url.query["mode"] == "ro"
    assert url.query["uri"] == "true"
    assert url.database.startswith("file:")
    with create_engine(url).connect() as connection:
        assert connection.execute(select(1)).scalar_one() == 1
    with pytest.raises(ValueError, match="SQLite URL"):
        _readonly_sqlite_url("postgresql+psycopg://user:pass@localhost/test")


def test_utc_values_restores_utc_timezone_for_sqlite_datetimes():
    table = Base.metadata.tables["users"]
    naive_value = datetime(2026, 1, 1, 12, 0)

    converted = _utc_values(
        table,
        {"id": "user-id", "created_at": naive_value},
    )

    assert converted["created_at"] == naive_value.replace(tzinfo=UTC)


def test_copy_rows_preserves_ids_and_refuses_nonempty_target(tmp_path):
    source_engine = create_engine(f"sqlite:///{tmp_path / 'source.db'}")
    target_engine = create_engine(f"sqlite:///{tmp_path / 'target.db'}")
    Base.metadata.create_all(source_engine)
    Base.metadata.create_all(target_engine)
    user_table = Base.metadata.tables["users"]

    try:
        with source_engine.begin() as source:
            source.execute(
                insert(user_table).values(
                    id="user-1",
                    email="legacy@example.test",
                    hashed_password="hash",
                    display_name="Legacy",
                    currency="INR",
                    is_active=True,
                    created_at=datetime(2026, 1, 1, 12, 0),
                )
            )
        with source_engine.connect() as source, target_engine.begin() as target:
            counts = _copy_rows(source, target)
            assert counts["users"] == 1
            assert counts["events"] == 0
            assert target.execute(
                select(user_table.c.id, user_table.c.email)
            ).one() == ("user-1", "legacy@example.test")

        with source_engine.connect() as source, target_engine.begin() as target:
            with pytest.raises(ValueError, match="non-empty target"):
                _copy_rows(source, target)
    finally:
        source_engine.dispose()
        target_engine.dispose()


def test_copy_database_requires_confirmation_of_exact_target_host():
    with pytest.raises(ValueError, match="exactly match"):
        copy_database(
            "sqlite:///source.db",
            "postgresql+psycopg://user:pass@localhost/target",
            "different-host",
        )


def test_copy_utility_never_opens_sqlite_target():
    with pytest.raises(ValueError, match="PostgreSQL with psycopg"):
        copy_database(
            "sqlite:///source.db",
            "sqlite:///target.db",
            "target.db",
        )
