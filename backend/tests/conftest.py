"""Shared pytest fixtures."""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use in-memory SQLite for tests
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-for-testing-only-not-real")
os.environ.setdefault("GEMINI_API_KEY", "test-fake-key")
os.environ.setdefault("APP_ENV", "test")
if os.environ.get("TEST_DATABASE_URL"):
    test_database_url = os.environ["TEST_DATABASE_URL"].strip()
    if test_database_url.startswith("postgresql://"):
        test_database_url = test_database_url.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
    elif test_database_url.startswith("postgres://"):
        test_database_url = test_database_url.replace(
            "postgres://", "postgresql+psycopg://", 1
        )
    os.environ["DATABASE_URL"] = test_database_url
    os.environ["DATABASE_URL_DIRECT"] = os.environ["DATABASE_URL"]
else:
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import event
from sqlalchemy.pool import StaticPool

from app.config.database import Base, get_db
from app.main import app
from app.middleware.rate_limit import get_rate_limit_store

TEST_DATABASE_URL = os.environ["DATABASE_URL"]
test_engine_options = {"pool_pre_ping": True}
if TEST_DATABASE_URL.startswith("sqlite"):
    test_engine_options["connect_args"] = {"check_same_thread": False}
    if TEST_DATABASE_URL.endswith(":memory:"):
        test_engine_options["poolclass"] = StaticPool
else:
    test_engine_options.update(pool_size=2, max_overflow=0)

TEST_ENGINE = create_engine(TEST_DATABASE_URL, **test_engine_options)
if TEST_DATABASE_URL.startswith("sqlite"):
    @event.listens_for(TEST_ENGINE, "connect")
    def _enable_test_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

TestSessionLocal = sessionmaker(bind=TEST_ENGINE, autocommit=False, autoflush=False)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=TEST_ENGINE)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture(scope="function")
def client(db):
    store = get_rate_limit_store()
    store._store.clear()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def registered_user(client):
    """Create a user and return their auth headers."""
    resp = client.post("/api/auth/signup", json={
        "email": "test@example.com",
        "password": "Test@1234",
        "display_name": "Test User",
    })
    assert resp.status_code == 202
    login = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "Test@1234",
    })
    assert login.status_code == 200
    return {"email": "test@example.com", "password": "Test@1234"}


@pytest.fixture
def auth_client(client, registered_user):
    """TestClient already has auth cookies from signup."""
    return client


@pytest.fixture
def sample_event(auth_client):
    resp = auth_client.post("/api/events", json={
        "name": "Test Wedding",
        "event_type": "wedding",
        "profile": {
            "occasion": "Wedding",
            "budget": 500000,
            "guest_count": 100,
            "event_date": "2027-06-15",
            "experience_level": "moderate",
            "priorities": ["catering"],
            "must_haves": ["flowers"],
            "atmosphere": "festive",
            "age_groups": ["adults"],
            "cultural_preferences": "",
            "accessibility_needs": "",
            "venue_limits": "",
        }
    })
    assert resp.status_code == 201
    return resp.json()
