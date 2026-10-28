"""Integration tests for auth endpoints."""
import pytest


class TestSignup:
    def test_signup_success(self, client):
        resp = client.post("/api/auth/signup", json={
            "email": "user@test.com",
            "password": "Valid@1234",
            "display_name": "Test User",
        })
        assert resp.status_code == 202
        assert "user_id" not in resp.json()
        assert resp.json()["message"] == (
            "If the address was available, the account was created. Sign in to continue."
        )

    def test_signup_duplicate_email(self, client):
        data = {"email": "dup@test.com", "password": "Valid@1234", "display_name": "A"}
        first = client.post("/api/auth/signup", json=data)
        resp = client.post("/api/auth/signup", json=data)
        assert resp.status_code == first.status_code == 202
        assert resp.json() == first.json()

    def test_signup_weak_password_rejected(self, client):
        resp = client.post("/api/auth/signup", json={
            "email": "weak@test.com",
            "password": "password",
            "display_name": "Weak",
        })
        assert resp.status_code == 400

    def test_signup_short_password_rejected(self, client):
        resp = client.post("/api/auth/signup", json={
            "email": "short@test.com",
            "password": "Ab1",
            "display_name": "Short",
        })
        assert resp.status_code == 400

    def test_signup_invalid_email_rejected(self, client):
        resp = client.post("/api/auth/signup", json={
            "email": "not-an-email",
            "password": "Valid@1234",
            "display_name": "Bad Email",
        })
        assert resp.status_code == 400


class TestLogin:
    def test_login_success(self, client):
        client.post("/api/auth/signup", json={
            "email": "login@test.com", "password": "Valid@1234", "display_name": "L"
        })
        resp = client.post("/api/auth/login", json={
            "email": "login@test.com", "password": "Valid@1234"
        })
        assert resp.status_code == 200

    def test_login_wrong_password(self, client):
        client.post("/api/auth/signup", json={
            "email": "wrong@test.com", "password": "Valid@1234", "display_name": "W"
        })
        resp = client.post("/api/auth/login", json={
            "email": "wrong@test.com", "password": "WrongPass@1"
        })
        assert resp.status_code == 401

    def test_login_backoff_increases_after_failures(self, client, monkeypatch):
        client.post("/api/auth/signup", json={
            "email": "backoff@test.com", "password": "Valid@1234", "display_name": "B"
        })
        delays = []

        async def record_sleep(delay):
            delays.append(delay)

        monkeypatch.setattr("app.routes.auth.asyncio.sleep", record_sleep)
        for _ in range(3):
            resp = client.post("/api/auth/login", json={
                "email": "backoff@test.com", "password": "WrongPass@1"
            })
            assert resp.status_code == 401

        assert delays == [2.0, 4.0]

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "email": "nobody@test.com", "password": "Valid@1234"
        })
        assert resp.status_code == 401

    def test_get_me_authenticated(self, auth_client):
        resp = auth_client.get("/api/auth/me")
        assert resp.status_code == 200
        assert "email" in resp.json()

    def test_get_me_unauthenticated(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    @pytest.mark.parametrize(
        "payload",
        [
            {"sub": "user-1", "type": "refresh"},
            {"type": "access"},
            ["not", "an", "object"],
        ],
    )
    def test_get_me_rejects_invalid_access_claims(self, client, monkeypatch, payload):
        monkeypatch.setattr(
            "app.services.auth_service.decode_access_token",
            lambda _token: payload,
        )

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 401

    def test_error_response_has_no_stack_trace(self, client):
        """Errors must never expose internal details."""
        resp = client.post("/api/auth/login", json={
            "email": "nobody@test.com", "password": "Valid@1234"
        })
        body = resp.text
        assert "traceback" not in body.lower()
        assert "sqlalchemy" not in body.lower()
        assert "file \"" not in body.lower()

    def test_validation_errors_are_generic_and_have_request_id(self, client):
        resp = client.post("/api/auth/signup", json={
            "email": "bad-input@test.com",
            "password": "Valid@1234",
            "display_name": "Bad Input",
            "unexpected": "details",
        })

        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid request"
        assert resp.json()["request_id"] == resp.headers["x-request-id"]
        assert "unexpected" not in resp.text

    def test_logout(self, auth_client):
        resp = auth_client.post("/api/auth/logout")
        assert resp.status_code == 200


class TestDataIsolation:
    def test_user_cannot_see_other_users_event(self, client):
        # Create user 1 and their event
        client.post("/api/auth/signup", json={
            "email": "u1@test.com", "password": "Valid@1234", "display_name": "U1"
        })
        client.post("/api/auth/login", json={
            "email": "u1@test.com", "password": "Valid@1234"
        })
        resp = client.post("/api/events", json={
            "name": "U1 Event", "event_type": "wedding",
            "profile": {
                "occasion": "Wedding", "budget": 100000, "guest_count": 50,
                "event_date": "2027-01-01", "experience_level": "simple",
                "priorities": [], "must_haves": [], "atmosphere": "",
                "age_groups": [], "cultural_preferences": "",
                "accessibility_needs": "", "venue_limits": ""
            }
        })
        assert resp.status_code == 201
        event_id = resp.json()["id"]

        # Log out user 1 and create user 2
        client.post("/api/auth/logout")
        client.post("/api/auth/signup", json={
            "email": "u2@test.com", "password": "Valid@1234", "display_name": "U2"
        })
        client.post("/api/auth/login", json={
            "email": "u2@test.com", "password": "Valid@1234"
        })

        # User 2 should not see user 1's event
        resp2 = client.get(f"/api/events/{event_id}")
        assert resp2.status_code == 404
