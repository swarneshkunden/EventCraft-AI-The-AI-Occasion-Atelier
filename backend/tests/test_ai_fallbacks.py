"""Tests for deterministic AI fallbacks and the fallback wrapper."""
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.errors import AIResponseError
from app.services import ai_fallbacks, ai_generation


def _event(**overrides):
    defaults = {
        "total_budget": 500_000.0,
        "event_date": "2027-06-01",
        "event_type": "wedding",
    }
    return SimpleNamespace(**{**defaults, **overrides})


def test_budget_fallback_respects_total_budget():
    split = ai_fallbacks.fallback_budget_split(_event(total_budget=100_000))

    assert split.categories
    assert sum(category.allocated for category in split.categories) == pytest.approx(100_000)
    assert all("unavailable" in category.notes for category in split.categories)


def test_budget_fallback_handles_missing_budget():
    split = ai_fallbacks.fallback_budget_split(_event(total_budget=None))

    assert all(category.allocated == 0 for category in split.categories)


def test_task_fallback_reverse_plans_from_event_date():
    tasks = ai_fallbacks.fallback_task_list(_event(event_date="2027-06-01")).tasks

    assert len(tasks) >= 6
    assert all(task.due_date for task in tasks)
    assert [task.due_date for task in tasks] == sorted(task.due_date for task in tasks)


def test_task_fallback_without_event_date_uses_a_safe_horizon():
    tasks = ai_fallbacks.fallback_task_list(_event(event_date=None)).tasks

    assert tasks


def test_vendor_fallback_is_type_specific_and_never_empty():
    caterer = ai_fallbacks.fallback_vendor_questions(_event(), "caterer")
    unknown = ai_fallbacks.fallback_vendor_questions(_event(), "fire-eater")

    assert any("dish" in item.lower() for item in caterer.questions)
    assert unknown.checklist and unknown.questions


def test_ideas_fallback_covers_every_section():
    ideas = ai_fallbacks.fallback_ideas(_event(event_type="birthday"))

    assert ideas.themes and ideas.decor and ideas.menu and ideas.activities
    assert "birthday party" in ideas.themes[0].description


class _Payload(BaseModel):
    name: str


async def _generate_with_fallback(monkeypatch, response):
    async def fake_generate_model(*_args, **_kwargs):
        if response is None:
            raise ai_generation.AIUnavailableError()
        return response

    monkeypatch.setattr(ai_generation, "generate_model", fake_generate_model)
    return await ai_generation.generate_with_fallback(
        "system",
        "user",
        _Payload,
        lambda: _Payload(name="fallback"),
        label="Test",
    )


@pytest.mark.asyncio
async def test_generate_with_fallback_uses_ai_output(monkeypatch):
    result, used_ai = await _generate_with_fallback(monkeypatch, _Payload(name="ai"))

    assert result.name == "ai"
    assert used_ai is True


@pytest.mark.asyncio
async def test_generate_with_fallback_degrades_on_outage(monkeypatch):
    result, used_ai = await _generate_with_fallback(monkeypatch, None)

    assert result.name == "fallback"
    assert used_ai is False


@pytest.mark.asyncio
async def test_generate_with_fallback_still_raises_on_malformed_output(monkeypatch):
    async def fake_generate_model(*_args, **_kwargs):
        raise AIResponseError()

    monkeypatch.setattr(ai_generation, "generate_model", fake_generate_model)

    with pytest.raises(AIResponseError):
        await ai_generation.generate_with_fallback(
            "system", "user", _Payload, lambda: _Payload(name="fallback")
        )


def test_mark_source_sets_header():
    response = SimpleNamespace(headers={})

    ai_generation.mark_source(response, True)
    assert response.headers["X-AI-Source"] == "ai"

    ai_generation.mark_source(response, False)
    assert response.headers["X-AI-Source"] == "fallback"
