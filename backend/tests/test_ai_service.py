"""Tests for Gemini model configuration and safe provider diagnostics."""
import asyncio
import logging

import httpx
import pytest

from app.config.settings import Settings


@pytest.mark.parametrize(
    "retired_model",
    ["gemini-2.0-flash", "gemini-2.0-flash-001"],
)
def test_retired_gemini_models_are_upgraded(retired_model):
    settings = Settings(
        APP_SECRET_KEY="fresh-random-test-secret-that-is-at-least-32-characters",
        GEMINI_MODEL=retired_model,
    )

    assert settings.GEMINI_MODEL == "gemini-3.8-flash"


def test_gemini_model_default_is_current():
    settings = Settings(
        APP_SECRET_KEY="fresh-random-test-secret-that-is-at-least-32-characters",
    )

    assert settings.GEMINI_MODEL == "gemini-3.8-flash"


def test_gemini_http_failure_logs_status_without_api_key(monkeypatch, caplog):
    from app.services import ai_service

    api_key = "test-key-that-must-not-be-logged"
    monkeypatch.setattr(ai_service.settings, "GEMINI_API_KEY", api_key)
    monkeypatch.setattr(ai_service.settings, "GEMINI_MAX_RETRIES", 1)

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, json, headers):
            request = httpx.Request("POST", url)
            response = httpx.Response(404, request=request)
            raise httpx.HTTPStatusError("provider error", request=request, response=response)

    monkeypatch.setattr(ai_service.httpx, "AsyncClient", lambda **kwargs: FailingClient())

    with caplog.at_level(logging.WARNING, logger="app.services.ai_service"):
        result = asyncio.run(ai_service._call_gemini("system", "user"))

    assert result == ai_service._AI_FALLBACK
    assert "HTTP status 404" in caplog.text
    assert api_key not in caplog.text


def test_gemini_503_falls_back_to_available_flash_lite(monkeypatch):
    from app.services import ai_service

    monkeypatch.setattr(ai_service.settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ai_service.settings, "GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setattr(ai_service.settings, "GEMINI_MAX_RETRIES", 1)
    requested_models = []

    class FailingPrimaryClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, json, headers):
            model_name = url.split("/models/", 1)[1].split(":", 1)[0]
            requested_models.append(model_name)
            request = httpx.Request("POST", url)
            if model_name == "gemini-3.8-flash":
                response = httpx.Response(503, request=request)
                raise httpx.HTTPStatusError("provider unavailable", request=request, response=response)
            return httpx.Response(
                200,
                json={"candidates": [{"content": {"parts": [{"text": "Fallback answer"}]}}]},
                request=request,
            )

    monkeypatch.setattr(ai_service.httpx, "AsyncClient", lambda **kwargs: FailingPrimaryClient())

    result = asyncio.run(ai_service._call_gemini("system", "user"))

    assert result == "Fallback answer"
    assert requested_models == ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
