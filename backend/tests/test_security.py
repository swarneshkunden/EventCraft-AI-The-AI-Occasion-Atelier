"""Test that rate limiting and security headers work."""
import asyncio
import json

import pytest
from sqlalchemy.exc import OperationalError
from starlette.requests import Request


class TestSecurityHeaders:
    def test_security_headers_present(self, client):
        resp = client.get("/api/health")
        assert "x-content-type-options" in resp.headers
        assert "x-frame-options" in resp.headers
        assert "x-request-id" in resp.headers

    def test_x_frame_options_is_deny(self, client):
        resp = client.get("/api/health")
        assert resp.headers["x-frame-options"] == "DENY"

    def test_content_security_policy_blocks_inline_scripts(self, client):
        response = client.get("/api/health")
        csp = response.headers["content-security-policy"]
        assert "script-src 'self';" in csp
        assert "'unsafe-inline'" not in csp.split("script-src", 1)[1].split(";", 1)[0]
        assert "object-src 'none'" in csp


class TestDeploymentHealth:
    def test_healthz_checks_database(self, client):
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_root_serves_spa(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "EventCraft AI" in response.text
        assert response.headers["cache-control"] == "no-cache"

    def test_static_assets_are_revalidated(self, client):
        response = client.get("/src/app.js")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"

    def test_production_rejects_ephemeral_sqlite(self):
        from app.config.settings import Settings

        with pytest.raises(ValueError, match="durable PostgreSQL"):
            Settings(
                APP_ENV="production",
                APP_SECRET_KEY="a-secure-test-key-with-at-least-32-characters",
                DATABASE_URL="sqlite:///./eventplanner.db",
            )

    def test_production_rejects_example_signing_secret(self):
        from app.config.settings import Settings

        with pytest.raises(ValueError, match="newly generated APP_SECRET_KEY"):
            Settings(
                APP_ENV="production",
                APP_SECRET_KEY="replace-with-a-secure-random-32-byte-secret-key-123456",
                DATABASE_URL="postgresql+psycopg://eventcraft:password@localhost/eventplanner",
                ALLOWED_ORIGINS="https://eventcraft.example",
            )

    def test_production_requires_secure_cors_origins(self):
        from app.config.settings import Settings

        with pytest.raises(ValueError, match="HTTPS origins"):
            Settings(
                APP_ENV="production",
                APP_SECRET_KEY="fresh-random-test-secret-that-is-at-least-32-characters",
                DATABASE_URL="postgresql+psycopg://eventcraft:password@localhost/eventplanner",
                ALLOWED_ORIGINS="http://eventcraft.example",
            )

    def test_production_accepts_https_origins_and_normalizes_trailing_slash(self):
        from app.config.settings import Settings

        settings = Settings(
            APP_ENV="production",
            APP_SECRET_KEY="fresh-random-test-secret-that-is-at-least-32-characters",
            DATABASE_URL="postgresql+psycopg://eventcraft:password@localhost/eventplanner",
            ALLOWED_ORIGINS="https://eventcraft.example/",
        )

        assert settings.allowed_origins_list() == ["https://eventcraft.example"]

    def test_database_error_response_does_not_expose_sql_or_connection_details(self, caplog):
        from app.middleware.error_handlers import sqlalchemy_exception_handler

        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/events",
                "headers": [],
                "query_string": b"",
                "server": ("testserver", 80),
                "client": ("127.0.0.1", 12345),
                "scheme": "http",
                "http_version": "1.1",
            }
        )
        request.state.request_id = "db-error-test"
        exc = OperationalError(
            "SELECT private_column FROM events",
            {},
            Exception("connection to private-host with password private-password"),
        )

        response = asyncio.run(sqlalchemy_exception_handler(request, exc))

        body = json.loads(response.body)
        assert body == {
            "detail": "Something went wrong",
            "request_id": "db-error-test",
        }
        assert "private_column" not in response.body.decode()
        assert "private-host" not in response.body.decode()
        assert "private-password" not in response.body.decode()
        assert "private-host" not in caplog.text
        assert "private-password" not in caplog.text


class TestRateLimiting:
    def test_auth_rate_limit_window_is_capped_at_five_minutes(self):
        from pydantic import ValidationError
        from app.config.settings import Settings

        settings = Settings(
            APP_SECRET_KEY="fresh-random-test-secret-that-is-at-least-32-characters",
        )
        assert settings.RATE_AUTH_WINDOW_SECONDS == 300
        assert settings.RATE_AUTH_ACCOUNT_WINDOW_SECONDS == 300

        with pytest.raises(ValidationError):
            Settings(
                APP_SECRET_KEY="fresh-random-test-secret-that-is-at-least-32-characters",
                RATE_AUTH_WINDOW_SECONDS=301,
            )

        with pytest.raises(ValidationError):
            Settings(
                APP_SECRET_KEY="fresh-random-test-secret-that-is-at-least-32-characters",
                RATE_AUTH_ACCOUNT_WINDOW_SECONDS=301,
            )

    def test_session_checks_do_not_consume_auth_attempt_limit(self, client, monkeypatch):
        from app.config import get_settings

        monkeypatch.setattr(get_settings(), "RATE_AUTH_MAX_REQUESTS", 1)

        for _ in range(3):
            assert client.get("/api/auth/me").status_code == 401

        response = client.post("/api/auth/signup", json={
            "email": "new-user@test.com",
            "password": "Valid@1234",
            "display_name": "New User",
        })

        assert response.status_code == 202

    def test_auth_rate_limit_triggers(self, client, monkeypatch):
        """After enough failed requests, rate limit should kick in."""
        from app.config import get_settings
        settings = get_settings()
        monkeypatch.setattr(settings, "RATE_AUTH_MAX_REQUESTS", 3)
        monkeypatch.setattr(settings, "RATE_AUTH_WINDOW_SECONDS", 3600)

        async def skip_backoff(_delay):
            return None

        monkeypatch.setattr("app.routes.auth.asyncio.sleep", skip_backoff)
        for _ in range(3):
            resp = client.post("/api/auth/login", json={"email": "x@x.com", "password": "P"})
            assert resp.status_code == 401

        resp = client.post("/api/auth/login", json={"email": "x@x.com", "password": "P"})
        assert resp.status_code == 429
        assert resp.headers["retry-after"] == "3600"
        assert resp.json()["request_id"] == resp.headers["x-request-id"]

    def test_ai_short_window_limit_triggers(self, client, monkeypatch):
        from app.config import get_settings
        settings = get_settings()
        monkeypatch.setattr(settings, "RATE_AI_MAX_REQUESTS", 1)
        monkeypatch.setattr(settings, "RATE_AI_DAILY_MAX_REQUESTS", 10)

        path = "/api/events/missing-event/budget/ai-split"
        assert client.post(path).status_code == 401
        limited = client.post(path)
        assert limited.status_code == 429
        assert limited.headers["retry-after"] == str(settings.RATE_AI_WINDOW_SECONDS)

    def test_ai_daily_limit_triggers(self, client, monkeypatch):
        from app.config import get_settings
        settings = get_settings()
        monkeypatch.setattr(settings, "RATE_AI_MAX_REQUESTS", 10)
        monkeypatch.setattr(settings, "RATE_AI_DAILY_MAX_REQUESTS", 1)

        path = "/api/events/missing-event/budget/ai-split"
        assert client.post(path).status_code == 401
        limited = client.post(path)
        assert limited.status_code == 429
        assert limited.headers["retry-after"] == str(settings.RATE_AI_DAILY_WINDOW_SECONDS)

    @pytest.mark.parametrize("path", [
        "/api/events/1/budget/ai-split",
        "/api/events/1/budget/scenario",
        "/api/events/1/tasks/generate",
        "/api/events/1/vendors/1/generate-questions",
        "/api/events/1/chat/ideas",
        "/api/events/1/chat",
        "/api/events/1/plan-health/crisis",
    ])
    def test_ai_endpoints_are_classified(self, path):
        from app.middleware.rate_limit import RateLimitMiddleware
        assert RateLimitMiddleware._is_ai_endpoint(path, "POST")
