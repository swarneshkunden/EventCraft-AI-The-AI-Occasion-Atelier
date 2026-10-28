"""Database URL configuration and Neon TLS requirements."""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from app.config import database
from app.config.settings import Settings, normalize_database_url

_SECRET = "database-config-test-secret-with-at-least-32-characters"


def test_postgresql_url_selects_psycopg_and_keeps_query_options():
    url = "postgresql://app:secret@localhost/events?sslmode=require&connect_timeout=5"

    assert normalize_database_url(url) == (
        "postgresql+psycopg://app:secret@localhost/events"
        "?sslmode=require&connect_timeout=5"
    )


def test_neon_runtime_and_direct_urls_require_ssl():
    with pytest.raises(ValueError, match="sslmode=require"):
        Settings(
            APP_SECRET_KEY=_SECRET,
            DATABASE_URL_DIRECT="postgresql://app:secret@ep-example.us-east-1.aws.neon.tech/db",
        )

    settings = Settings(
        APP_SECRET_KEY=_SECRET,
        DATABASE_URL=(
            "postgresql://app:secret@ep-example-pooler.us-east-1.aws.neon.tech/db"
            "?sslmode=require"
        ),
        DATABASE_URL_DIRECT=(
            "postgresql://app:secret@ep-example.us-east-1.aws.neon.tech/db"
            "?sslmode=require"
        ),
    )
    assert settings.DATABASE_URL.startswith("postgresql+psycopg://")
    assert "sslmode=require" in settings.DATABASE_URL
    assert settings.DATABASE_URL_DIRECT.startswith("postgresql+psycopg://")


def test_production_neon_runtime_requires_pooled_hostname():
    with pytest.raises(ValueError, match="pooled hostname"):
        Settings(
            APP_ENV="production",
            APP_SECRET_KEY=_SECRET,
            DATABASE_URL=(
                "postgresql://app:secret@ep-example.us-east-1.aws.neon.tech/db"
                "?sslmode=require"
            ),
            ALLOWED_ORIGINS="https://eventcraft.example",
        )


def test_sqlite_enforces_case_insensitive_email_uniqueness(db):
    from app.models.models import User

    db.add(
        User(
            email="CaseCheck@example.test",
            hashed_password="not-a-real-password-hash",
            display_name="First",
        )
    )
    db.commit()
    db.add(
        User(
            email="casecheck@example.test",
            hashed_password="not-a-real-password-hash",
            display_name="Duplicate",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert db.scalar(select(User).where(User.email == "CaseCheck@example.test")) is not None


def test_sqlite_test_connections_enforce_foreign_keys(db):
    if db.bind.dialect.name == "sqlite":
        assert db.connection().exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1


def test_database_transaction_rollback_removes_uncommitted_user(db):
    from app.models.models import User

    user = User(
        email="rollback@example.test",
        hashed_password="not-a-real-password-hash",
        display_name="Rollback Test",
    )
    db.add(user)
    db.flush()
    user_id = user.id
    db.rollback()

    assert db.scalar(select(User).where(User.id == user_id)) is None


def test_db_dependency_rolls_back_and_closes_after_request_error(monkeypatch):
    calls = []

    class FakeSession:
        def rollback(self):
            calls.append("rollback")

        def close(self):
            calls.append("close")

    session = FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    dependency = database.get_db()

    assert next(dependency) is session
    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))

    assert calls == ["rollback", "close"]


def test_db_session_commits_success_and_rolls_back_failure(monkeypatch):
    calls = []

    class FakeSession:
        def commit(self):
            calls.append("commit")

        def rollback(self):
            calls.append("rollback")

        def close(self):
            calls.append("close")

    session = FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)

    with database.db_session() as current:
        assert current is session
    assert calls == ["commit", "close"]

    calls.clear()
    with pytest.raises(RuntimeError, match="operation failed"):
        with database.db_session():
            raise RuntimeError("operation failed")
    assert calls == ["rollback", "close"]


def test_sqlite_concurrent_event_edit_rejects_stale_write(tmp_path):
    from app.config.database import Base
    from app.models.models import Event, User

    engine = create_engine(f"sqlite:///{tmp_path / 'optimistic-lock.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with sessions.begin() as session:
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
            session.add(event)
        event_id = event.id

        first_session = sessions()
        second_session = sessions()
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
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
