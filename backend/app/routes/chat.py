"""Chat assistant route – context-aware AI chat for a specific event."""
import json

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.models import User
from app.services.ai_fallbacks import fallback_ideas
from app.services.ai_generation import (
    AI_SOURCE_RESPONSES,
    generate_with_fallback,
    mark_source,
)
from app.services.ai_service import call_ai
from app.services.auth_service import get_current_user
from app.services.event_service import (
    get_budget_categories,
    get_chat_history,
    get_event,
    get_tasks,
    save_chat_message,
)
from app.services.prompts import CHAT_SYSTEM, CHAT_USER, IDEAS_SYSTEM, IDEAS_USER
from app.validators.schemas import AIIdeas, ChatMessageRequest, ChatMessageResponse

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

    # Persist the assistant reply, including the provider's graceful fallback text.
    assistant_msg = save_chat_message(event_id, "assistant", ai_text, db)
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg


@router.get("/ideas", response_model=AIIdeas, responses=AI_SOURCE_RESPONSES)
async def get_ideas(
    event_id: str,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Generate personalized theme/decor/menu/activity ideas."""
    event = get_event(event_id, current_user.id, db)
    categories = get_budget_categories(event_id, current_user.id, db)
    total_spent = sum(c.spent for c in categories)
    remaining = event.total_budget - total_spent

    user_prompt = IDEAS_USER.format(
        profile_json=json.dumps(event.profile, indent=2),
        currency=current_user.currency,
        remaining_budget=remaining,
    )

    validated, used_ai = await generate_with_fallback(
        IDEAS_SYSTEM,
        user_prompt,
        AIIdeas,
        lambda: fallback_ideas(event),
        use_cache=True,
        label="Ideas",
    )
    mark_source(response, used_ai)
    return validated.model_dump()
