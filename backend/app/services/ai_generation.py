"""Single, schema-validated entry point for structured AI generation.

Every AI feature that expects JSON goes through ``generate_model`` so retries,
fallback detection, JSON extraction, and schema validation behave identically
and are fixed in exactly one place.
"""
import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.errors import AIResponseError, AIUnavailableError
from app.services.ai_service import call_ai, extract_json_from_response, is_ai_fallback

log = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)


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
