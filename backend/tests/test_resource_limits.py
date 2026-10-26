"""Tests for bounded in-process caches and rate-limit state."""
import asyncio

import pytest


@pytest.fixture(autouse=True)
def clear_ai_cache():
    from app.services import ai_service

    with ai_service._cache_lock:
        ai_service._cache.clear()
    yield
    with ai_service._cache_lock:
        ai_service._cache.clear()


def test_ai_cache_expires_entries(monkeypatch):
    from app.services import ai_service

    clock = [100.0]
    monkeypatch.setattr(ai_service.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(ai_service.settings, "AI_CACHE_TTL_SECONDS", 10)

    ai_service._set_cache("prompt", "response")
    clock[0] += 10

    assert ai_service._get_cached("prompt") is None
    assert "prompt" not in ai_service._cache

def test_ai_cache_evicts_least_recently_used_entry(monkeypatch):
    from app.services import ai_service
    from app.services import ai_service
    monkeypatch.setattr(ai_service.settings, "AI_CACHE_MAX_ENTRIES", 2)
    monkeypatch.setattr(ai_service.settings, "AI_CACHE_MAX_ENTRIES", 2)

    ai_service._set_cache("first", "1")
    ai_service._set_cache("second", "2")
    assert ai_service._get_cached("first") == "1"
    ai_service._set_cache("third", "3")

    assert list(ai_service._cache) == ["first", "third"]


def test_rate_limit_store_caps_tracked_keys(monkeypatch):
    from app.middleware import rate_limit

    monkeypatch.setattr(rate_limit.settings, "RATE_MAX_TRACKED_KEYS", 2)
    store = rate_limit._SlidingWindowStore()

    async def exercise():
        for key in ("first", "second", "third"):
            assert await store.is_allowed(key, 60, 10)

    asyncio.run(exercise())

    assert list(store._store) == ["second", "third"]


def test_auth_failure_backoff_expires(monkeypatch):
    from app.middleware import rate_limit

    clock = [100.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(rate_limit.settings, "RATE_AUTH_ACCOUNT_WINDOW_SECONDS", 10)
    store = rate_limit._SlidingWindowStore()

    async def exercise():
        assert await store.record_auth_failure("account:one") == 1
        delay = await store.get_auth_failure_delay("account:one")
        clock[0] += 10
        expired_delay = await store.get_auth_failure_delay("account:one")
        return delay, expired_delay

    delay, expired_delay = asyncio.run(exercise())

    assert delay == rate_limit.settings.RATE_AUTH_BACKOFF_BASE
    assert expired_delay == 0
    assert "account:one" not in store._store
