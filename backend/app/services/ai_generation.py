"""Single, schema-validated entry point for structured AI generation.

Every AI feature that expects JSON goes through ``generate_model`` so retries,
fallback detection, JSON extraction, and schema validation behave identically
and are fixed in exactly one place.
"""
import logging
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.errors import AIResponseError, AIUnavailableError
from app.services.ai_service import call_ai, extract_json_from_response, is_ai_fallback

log = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

AI_SOURCE_RESPONSES = {
    200: {
        "headers": {
            "X-AI-Source": {
                "description": (
                    "Whether the payload came from the AI provider or from a "
                    "deterministic fallback used during an outage."
                ),
                "schema": {"type": "string", "enum": ["ai", "fallback"]},
            }
        }
    }
}


async def generate_model(
    system_prompt: str,
    user_prompt: str,
    schema: type[ModelT],
    *,
    use_cache: bool = True,
    label: str = "AI",
) -> ModelT:
    """Return validated AI output, or raise a typed, client-safe error."""
    ai_text = await call_ai(system_prompt, user_prompt, use_cache=use_cache)

    if is_ai_fallback(ai_text):
        log.warning("%s: provider unavailable, returning graceful error", label)
        raise AIUnavailableError()

    raw = extract_json_from_response(ai_text)
    if raw is None:
        log.warning("%s: response was not valid JSON", label)
        raise AIResponseError()

    try:
        return schema.model_validate(raw)
    except ValidationError as exc:
        log.warning("%s: response failed schema validation (%s)", label, type(exc).__name__)
        raise AIResponseError() from None


async def generate_with_fallback(
    system_prompt: str,
    user_prompt: str,
    schema: type[ModelT],
    fallback: Callable[[], ModelT],
    *,
    use_cache: bool = True,
    label: str = "AI",
) -> tuple[ModelT, bool]:
    """Return ``(output, used_ai)``, degrading to defaults if the provider is down.

    Malformed provider output still raises ``AIResponseError``: a broken response
    is a contract problem worth surfacing, while an outage is not the user's fault.
    """
    try:
        output = await generate_model(
            system_prompt,
            user_prompt,
            schema,
            use_cache=use_cache,
            label=label,
        )
    except AIUnavailableError:
        log.warning("%s: provider unavailable, using deterministic fallback", label)
        return fallback(), False
    return output, True


def mark_source(response: object, used_ai: bool) -> None:
    """Record whether a response was AI-generated or a deterministic fallback."""
    headers = getattr(response, "headers", None)
    if headers is not None:
        headers["X-AI-Source"] = "ai" if used_ai else "fallback"
