"""
Gemini AI service with retry/backoff, response caching, and schema validation.
The API key is ONLY used here – never exposed to the frontend.
"""
import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from threading import Lock
from typing import Any

import httpx

from app.config.settings import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
_cache_lock = Lock()

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"

_AI_FALLBACK = (
    "⚠️ The AI assistant is temporarily unavailable. "
    "Please try again in a moment. Your data is safe."
)


def _make_cache_key(model_name: str, prompt: str) -> str:
    combined = f"{model_name}:{prompt}"
    return hashlib.sha256(combined.encode()).hexdigest()


def _get_cached(cache_key: str) -> str | None:
    now = time.monotonic()
    with _cache_lock:
        entry = _cache.get(cache_key)
        if entry is None:
            return None
        if now - entry["ts"] >= settings.AI_CACHE_TTL_SECONDS:
            del _cache[cache_key]
            return None
        _cache.move_to_end(cache_key)
        return entry["response"]


def _set_cache(cache_key: str, response: str) -> None:
    now = time.monotonic()
    with _cache_lock:
        expired = [
            key
            for key, entry in _cache.items()
            if now - entry["ts"] >= settings.AI_CACHE_TTL_SECONDS
        ]
        for key in expired:
            del _cache[key]

        _cache[cache_key] = {"response": response, "ts": now}
        _cache.move_to_end(cache_key)
        while len(_cache) > settings.AI_CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)


def _build_url(model_name: str | None = None) -> str:
    return f"{_GEMINI_BASE}/{model_name or settings.GEMINI_MODEL}:generateContent"


def _build_payload(system_prompt: str, user_prompt: str) -> dict:
    return {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "topP": 0.9,
            "maxOutputTokens": 4096,
        },
    }


async def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    """Low-level Gemini call with exponential backoff retries."""
    payload = _build_payload(system_prompt, user_prompt)
    headers = {"X-Goog-Api-Key": settings.GEMINI_API_KEY, "Content-Type": "application/json"}
    model_names = [settings.GEMINI_MODEL]
    if settings.GEMINI_MODEL != _GEMINI_FALLBACK_MODEL:
        model_names.append(_GEMINI_FALLBACK_MODEL)
    last_err: Exception | None = None
    for model_index, model_name in enumerate(model_names):
        if model_index:
            log.warning("Trying Gemini fallback model after primary model failure")

        for attempt in range(settings.GEMINI_MAX_RETRIES):
            if attempt > 0:
                delay = settings.GEMINI_RETRY_BACKOFF_BASE ** attempt
                log.warning(
                    "Gemini retry %d/%d after %.1fs",
                    attempt,
                    settings.GEMINI_MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)

            try:
                async with httpx.AsyncClient(timeout=settings.GEMINI_TIMEOUT_SECONDS) as client:
                    resp = await client.post(
                        _build_url(model_name),
                        json=payload,
                        headers=headers,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    if not isinstance(text, str) or not text.strip():
                        raise ValueError("Gemini returned empty text")
                    return text
            except httpx.HTTPStatusError as e:
                last_err = e
                status = e.response.status_code
                log.warning("Gemini attempt %d failed with HTTP status %d", attempt + 1, status)
                if status != 429 and status < 500:
                    log.error("Gemini rejected the request with HTTP status %d", status)
                    return _AI_FALLBACK
            except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as e:
                last_err = e
                log.warning("Gemini attempt %d failed: %s", attempt + 1, type(e).__name__)

    if isinstance(last_err, httpx.HTTPStatusError):
        log.error("Gemini models failed with HTTP status %d", last_err.response.status_code)
    else:
        log.error("Gemini models failed: %s", type(last_err).__name__ if last_err else "unknown error")
    return _AI_FALLBACK


async def call_ai(system_prompt: str, user_prompt: str, use_cache: bool = True) -> str:
    """
    Public entry point. Returns AI text or a graceful fallback.
    Caches identical prompts to avoid redundant API calls.
    """
    cache_key = _make_cache_key(system_prompt, user_prompt)

    if use_cache:
        cached = _get_cached(cache_key)
        if cached:
            log.debug("Cache hit for AI call")
            return cached

    result = await _call_gemini(system_prompt, user_prompt)

    if result != _AI_FALLBACK and use_cache:
        _set_cache(cache_key, result)

    return result


def extract_json_from_response(text: str) -> Any:
    """
    Extract JSON from AI response – handles markdown code fences.
    Returns parsed object or None on failure.
    """
    # Strip markdown fences
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (``` markers)
        inner = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        text = inner.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON within the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        # Also try array
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    return None


def is_ai_fallback(text: str) -> bool:
    return text == _AI_FALLBACK
