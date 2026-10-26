"""
Chat assistant route – context-aware AI chat for a specific event.
AI responses with structured JSON actions are validated before saving.
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.models import User
from app.services.auth_service import get_current_user
from app.services.event_service import (
    get_budget_categories,
    get_chat_history,
    get_event,
    get_tasks,
    save_chat_message,
)
from app.services.ai_service import call_ai, extract_json_from_response, is_ai_fallback
from app.services.prompts import CHAT_SYSTEM, CHAT_USER
from app.validators.schemas import AIIdeas, ChatMessageRequest, ChatMessageResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events/{event_id}/chat", tags=["chat"])


@router.get("", response_model=list[ChatMessageResponse])
async def get_history(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    messages = get_chat_history(event_id, current_user.id, db)
    return list(reversed(messages))  # chronological order


@router.post("", response_model=ChatMessageResponse)
async def send_message(
    event_id: str,
    body: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatMessageResponse:
    event = get_event(event_id, current_user.id, db)
    categories = get_budget_categories(event_id, current_user.id, db)
    tasks = get_tasks(event_id, current_user.id, db)

    budget_json = json.dumps(
        [{"name": c.name, "allocated": c.allocated, "spent": c.spent} for c in categories],
        indent=2,
    )
    tasks_json = json.dumps(
        [
            {"title": t.title, "status": t.status, "due_date": t.due_date, "priority": t.priority}
            for t in tasks[:10]
        ],
        indent=2,
    )

    user_prompt = CHAT_USER.format(
        profile_json=json.dumps(event.profile, indent=2),
        budget_json=budget_json,
        tasks_json=tasks_json,
        user_message=body.message,
    )

    # Save user message
    save_chat_message(event_id, "user", body.message, db)

    ai_text = await call_ai(CHAT_SYSTEM, user_prompt, use_cache=False)

    if is_ai_fallback(ai_text):
        assistant_msg = save_chat_message(event_id, "assistant", ai_text, db)
        db.commit()
        db.refresh(assistant_msg)
        return assistant_msg

    # Persist assistant message
    assistant_msg = save_chat_message(event_id, "assistant", ai_text, db)
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg


@router.get("/ideas")
async def get_ideas(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Generate personalized theme/decor/menu/activity ideas."""
    from app.services.prompts import IDEAS_SYSTEM, IDEAS_USER
    from app.services.event_service import get_budget_categories

    event = get_event(event_id, current_user.id, db)
    categories = get_budget_categories(event_id, current_user.id, db)
    total_allocated = sum(c.allocated for c in categories)
    total_spent = sum(c.spent for c in categories)
    remaining = event.total_budget - total_spent

    user_prompt = IDEAS_USER.format(
        profile_json=json.dumps(event.profile, indent=2),
        currency=current_user.currency,
        remaining_budget=remaining,
    )

    ai_text = await call_ai(IDEAS_SYSTEM, user_prompt, use_cache=True)

    if is_ai_fallback(ai_text):
        raise HTTPException(status_code=503, detail=ai_text)

    raw = extract_json_from_response(ai_text)
    if not raw:
        raise HTTPException(status_code=502, detail="AI returned unexpected format. Please retry.")
    try:
        return AIIdeas.model_validate(raw).model_dump()
    except Exception as e:
        log.warning("AI ideas schema validation failed: %s", type(e).__name__)
        raise HTTPException(status_code=502, detail="AI response did not match expected format.")
