"""Unit tests for the shared, schema-validated AI generation pipeline."""
import pytest
from pydantic import BaseModel

from app.errors import AIResponseError, AIUnavailableError
from app.services import ai_generation
from app.services.ai_service import _AI_FALLBACK


class _Payload(BaseModel):
    name: str
    amount: float


async def _run(monkeypatch, response, *, use_cache=True):
    calls = []

    async def fake_call_ai(system_prompt, user_prompt, use_cache=True):
        calls.append({"use_cache": use_cache})
        return response

    monkeypatch.setattr(ai_generation, "call_ai", fake_call_ai)
    result = await ai_generation.generate_model(
        "system", "user", _Payload, use_cache=use_cache, label="Test"
    )
    return result, calls


@pytest.mark.asyncio
async def test_generate_model_returns_validated_output(monkeypatch):
    result, calls = await _run(monkeypatch, '{"name": "Venue", "amount": 1000}')

    assert result == _Payload(name="Venue", amount=1000)
    assert calls == [{"use_cache": True}]


@pytest.mark.asyncio
async def test_generate_model_forwards_cache_preference(monkeypatch):
    _, calls = await _run(monkeypatch, '{"name": "Venue", "amount": 1}', use_cache=False)

    assert calls == [{"use_cache": False}]


@pytest.mark.asyncio
async def test_generate_model_raises_unavailable_on_provider_fallback(monkeypatch):
    with pytest.raises(AIUnavailableError) as excinfo:
        await _run(monkeypatch, _AI_FALLBACK)

    assert excinfo.value.status_code == 503


@pytest.mark.asyncio
async def test_generate_model_raises_response_error_on_invalid_json(monkeypatch):
    with pytest.raises(AIResponseError) as excinfo:
        await _run(monkeypatch, "This is not JSON at all.")

    assert excinfo.value.status_code == 502


@pytest.mark.asyncio
async def test_generate_model_raises_response_error_on_schema_mismatch(monkeypatch):
    with pytest.raises(AIResponseError):
        await _run(monkeypatch, '{"name": "Venue", "amount": "not-a-number"}')


@pytest.mark.asyncio
async def test_generate_model_raises_response_error_on_missing_field(monkeypatch):
    with pytest.raises(AIResponseError):
        await _run(monkeypatch, '{"name": "Venue"}')


@pytest.mark.asyncio
async def test_generate_model_accepts_fenced_json(monkeypatch):
    result, _ = await _run(monkeypatch, '```json\n{"name": "Decor", "amount": 500}\n```')

    assert result.name == "Decor"
