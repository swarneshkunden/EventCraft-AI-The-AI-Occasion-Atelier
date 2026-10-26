"""Exercise schema upgrades against a fresh isolated database."""
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import Numeric, create_engine, inspect, text
from sqlalchemy.dialects.postgresql import JSONB

from app.config.settings import normalize_database_url


def test_initial_migration_creates_application_schema(tmp_path, monkeypatch):
    backend_dir = Path(__file__).resolve().parents[1]
    database_url = f"sqlite:///{(tmp_path / 'migration-test.db').as_posix()}"
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "migrations"))
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.delenv("DATABASE_URL_DIRECT", raising=False)

    command.upgrade(config, "head")
    command.upgrade(config, "head")
    command.check(config)

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        columns = {
            column["name"]: column["type"]
            for column in inspector.get_columns("events")
        }
        event_column_names = set(columns)
        with engine.connect() as connection:
            email_index_sql = connection.execute(
                text(
                    "SELECT sql FROM sqlite_master "
                    "WHERE type = 'index' AND name = 'uq_users_email_lower'"
                )
            ).scalar_one()
        foreign_keys = inspector.get_foreign_keys("events")
    finally:
        engine.dispose()

    assert {
        "users",
        "refresh_tokens",
        "events",
        "budget_categories",
        "tasks",
        "vendors",
        "guests",
        "chat_messages",
        "plan_change_proposals",
        "plan_change_audits",
        "alembic_version",
    } <= tables
    assert isinstance(columns["total_budget"], Numeric)
    assert "version" in event_column_names
    assert "CREATE UNIQUE INDEX" in email_index_sql.upper()
    assert "LOWER(EMAIL)" in email_index_sql.upper()
    assert any(
        foreign_key["constrained_columns"] == ["owner_id"]
        and foreign_key["options"].get("ondelete") == "CASCADE"
        for foreign_key in foreign_keys
    )


def test_upgrade_preserves_rows_from_initial_schema(tmp_path, monkeypatch):
    backend_dir = Path(__file__).resolve().parents[1]
    database_url = f"sqlite:///{(tmp_path / 'existing-data.db').as_posix()}"
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "migrations"))
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.delenv("DATABASE_URL_DIRECT", raising=False)

    command.upgrade(config, "0f5a78aeb321")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, email, hashed_password, display_name, currency, is_active, created_at) "
                    "VALUES (:id, :email, :password, :name, :currency, :active, :created)"
                ),
                {
                    "id": "user-1",
                    "email": "legacy@example.test",
                    "password": "hash",
                    "name": "Legacy",
                    "currency": "INR",
                    "active": True,
                    "created": "2026-01-01 00:00:00",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO events "
                    "(id, owner_id, name, event_type, profile, total_budget, guest_count, "
                    "is_demo, ai_cache, created_at, updated_at) "
                    "VALUES (:id, :owner, :name, :type, :profile, :budget, :guests, "
                    ":demo, :cache, :created, :updated)"
                ),
                {
                    "id": "event-1",
                    "owner": "user-1",
                    "name": "Legacy Event",
                    "type": "wedding",
                    "profile": '{"budget": 0.3}',
                    "budget": 0.3,
                    "guests": 2,
                    "demo": False,
                    "cache": "{}",
                    "created": "2026-01-01 00:00:00",
                    "updated": "2026-01-01 00:00:00",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO budget_categories "
                    "(id, event_id, name, allocated, spent, notes, sort_order) "
                    "VALUES ('category-1', 'event-1', 'Test', 0.1, 0.2, '', 0)"
                )
            )
        command.upgrade(config, "head")
        with engine.connect() as connection:
            event = connection.execute(
                text("SELECT id, total_budget, version FROM events WHERE id = 'event-1'")
            ).one()
            category = connection.execute(
                text(
                    "SELECT id, allocated, spent FROM budget_categories "
                    "WHERE id = 'category-1'"
                )
            ).one()
            foreign_key_issues = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
    finally:
        engine.dispose()

    assert event.id == "event-1"
    assert event.total_budget == pytest.approx(0.3)
    assert event.version == 1
    assert category.id == "category-1"
    assert category.allocated == pytest.approx(0.1)
    assert category.spent == pytest.approx(0.2)
    assert not foreign_key_issues


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to a dedicated, disposable PostgreSQL database.",
)
def test_postgresql_migrations_create_current_schema(monkeypatch):
    database_url = normalize_database_url(os.environ["TEST_DATABASE_URL"])
    if not database_url.startswith("postgresql+psycopg://"):
        pytest.fail("TEST_DATABASE_URL must point to PostgreSQL.")

    from app.config.database import Base

    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "migrations"))
    engine = create_engine(
        database_url,
        connect_args={"connect_timeout": 5},
        pool_pre_ping=True,
    )
    try:
        Base.metadata.drop_all(engine, checkfirst=True)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))

        monkeypatch.setenv("DATABASE_URL", database_url)
        monkeypatch.setenv("DATABASE_URL_DIRECT", database_url)
        command.upgrade(config, "head")

        inspector = inspect(engine)
        event_columns = {
            column["name"]: column["type"]
            for column in inspector.get_columns("events")
        }
        assert isinstance(event_columns["profile"], JSONB)
        assert isinstance(event_columns["total_budget"], Numeric)
        assert any(
            index["name"] == "uq_users_email_lower" and index["unique"]
            for index in inspector.get_indexes("users")
        )
    finally:
        engine.dispose()


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to a dedicated, disposable PostgreSQL database.",
)
def test_postgresql_numeric_money_and_constraints(db):
    from decimal import Decimal

    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from app.models.models import BudgetCategory, Event, User

    total = db.scalar(
        select(
            text("CAST(:left_amount AS NUMERIC(14, 2)) + CAST(:right_amount AS NUMERIC(14, 2))")
        ).params(left_amount=Decimal("0.10"), right_amount=Decimal("0.20"))
    )
    assert total == Decimal("0.30")

    user = User(
        email="casecheck@example.test",
        hashed_password="not-a-real-password-hash",
        display_name="Database Test",
    )
    db.add(user)
    db.flush()
    db.add(
        User(
            email="CASECHECK@example.test",
            hashed_password="not-a-real-password-hash",
            display_name="Duplicate Test",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
    assert db.scalar(select(User).where(User.email == "casecheck@example.test")) is None

    user = User(
        email="cascadecheck@example.test",
        hashed_password="not-a-real-password-hash",
        display_name="Cascade Test",
    )
    event = Event(
        owner=user,
        name="Cascade Test",
        event_type="wedding",
        profile={},
        total_budget=Decimal("0.30"),
    )
    event.budget_categories.append(
        BudgetCategory(name="Test", allocated=Decimal("0.10"), spent=Decimal("0.20"))
    )
    db.add(event)
    db.commit()
    event_id = event.id
    user_id = user.id

    db.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
    db.commit()
    assert db.scalar(select(Event).where(Event.id == event_id)) is None
    assert db.scalar(
        select(BudgetCategory).where(BudgetCategory.event_id == event_id)
    ) is None


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to a dedicated, disposable PostgreSQL database.",
)
def test_postgresql_event_concurrent_updates_reject_stale_write(db):
    from sqlalchemy import select
    from sqlalchemy.orm.exc import StaleDataError

    from app.models.models import Event, User
    from tests.conftest import TestSessionLocal

    user = User(
        email="concurrency@example.test",
        hashed_password="not-a-real-password-hash",
        display_name="Concurrency Test",
    )
    event = Event(
        owner=user,
        name="Concurrency Test",
        event_type="wedding",
        profile={},
        total_budget=100,
    )
    db.add(event)
    db.commit()
    event_id = event.id
    first_session = TestSessionLocal()
    second_session = TestSessionLocal()
    try:
        first_copy = first_session.scalar(select(Event).where(Event.id == event_id))
        second_copy = second_session.scalar(select(Event).where(Event.id == event_id))
        first_copy.total_budget = 125
        first_session.commit()
        assert first_copy.version == 2

        second_copy.total_budget = 150
        with pytest.raises(StaleDataError):
            second_session.flush()
        second_session.rollback()
        assert second_session.scalar(
            select(Event.total_budget).where(Event.id == event_id)
        ) == 125
    finally:
        first_session.close()
        second_session.close()
