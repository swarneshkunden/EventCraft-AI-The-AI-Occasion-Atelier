"""Resolve user-described event disruptions into validated crisis intents."""
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import ValidationError

from app.services.crisis_rules import parse_known_crisis
from app.validators.schemas import CrisisIntent

log = logging.getLogger(__name__)


async def resolve_crisis_intent(
    description: str,
    event_date: str | None,
    *,
    api_key: str,
    ai_call: Callable[..., Awaitable[str]],
    json_extractor: Callable[[str], Any],
    fallback_check: Callable[[str], bool],
    system_prompt: str,
    user_prompt_template: str,
) -> tuple[CrisisIntent, bool]:
    """Resolve a disruption deterministically or with validated AI classification."""
    intent = parse_known_crisis(description, event_date)
    if intent is not None:
        return intent, False

    if not api_key:
        return CrisisIntent(kind="general"), False

    prompt = user_prompt_template.format(
        description_json=json.dumps({"scenario": description}, ensure_ascii=True)
    )
    ai_text = await ai_call(system_prompt, prompt, use_cache=False)
    if not fallback_check(ai_text):
        raw = json_extractor(ai_text)
        if raw is not None:
            try:
                return CrisisIntent.model_validate(raw), True
            except ValidationError as exc:
                log.warning("Crisis intent schema validation failed: %s", type(exc).__name__)

    return CrisisIntent(kind="general"), False
