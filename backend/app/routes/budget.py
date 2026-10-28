"""Budget routes – category management and AI split generation."""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.config.settings import get_settings
from app.models.models import User
from app.services.ai_service import call_ai, extract_json_from_response, is_ai_fallback
from app.services.auth_service import get_current_user
from app.services.event_service import (
    get_budget_categories,
    get_event,
    set_budget_categories,
    update_budget_category,
)
from app.services.prompts import BUDGET_SPLIT_SYSTEM, BUDGET_SPLIT_USER, REPLAN_SYSTEM, REPLAN_USER
from app.validators.schemas import (
    AIBudgetSplit,
    AIReplanDiff,
    BudgetCategoryCreate,
    BudgetCategoryResponse,
    BudgetCategoryUpdate,
    ScenarioRequest,
)

log = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/events/{event_id}/budget", tags=["budget"])


@router.get("", response_model=list[BudgetCategoryResponse])
async def get_categories(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    return get_budget_categories(event_id, current_user.id, db)


@router.put("", response_model=list[BudgetCategoryResponse])
async def set_categories(
    event_id: str,
    body: list[BudgetCategoryCreate],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    if len(body) > 20:
        raise HTTPException(status_code=400, detail="Too many categories (max 20)")
    categories = set_budget_categories(event_id, current_user.id, body, db)
    db.commit()
    return categories


@router.patch("/{cat_id}", response_model=BudgetCategoryResponse)
async def update_category(
    event_id: str,
    cat_id: str,
    body: BudgetCategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetCategoryResponse:
    cat = update_budget_category(event_id, cat_id, current_user.id, body, db)
    db.commit()
    db.refresh(cat)
    return cat


@router.post("/ai-split", response_model=list[BudgetCategoryResponse])
async def generate_ai_split(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    """Ask AI to propose a budget split based on the event profile."""
    event = get_event(event_id, current_user.id, db)

    user_prompt = BUDGET_SPLIT_USER.format(
        profile_json=json.dumps(event.profile, indent=2),
        currency=current_user.currency,
        budget=event.total_budget,
    )

    ai_text = await call_ai(BUDGET_SPLIT_SYSTEM, user_prompt, use_cache=True)

    if is_ai_fallback(ai_text):
        raise HTTPException(status_code=503, detail=ai_text)

    raw = extract_json_from_response(ai_text)
    if not raw:
        raise HTTPException(status_code=502, detail="AI returned unexpected format. Please retry.")

    try:
        validated = AIBudgetSplit.model_validate(raw)
    except ValidationError as exc:
        log.warning("AI budget split schema validation failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="AI response did not match expected format.",
        ) from None

    # Clamp total to event budget
    total_allocated = sum(c.allocated for c in validated.categories)
    if total_allocated > event.total_budget:
        scale = event.total_budget / total_allocated
        for c in validated.categories:
            c.allocated = round(c.allocated * scale, 2)

    category_creates = [
        BudgetCategoryCreate(name=c.name, allocated=c.allocated, notes=c.notes)
        for c in validated.categories
    ]
    categories = set_budget_categories(event_id, current_user.id, category_creates, db)
    db.commit()
    return categories


@router.post("/scenario", response_model=dict)
async def run_scenario(
    event_id: str,
    body: ScenarioRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Re-plan the budget and tasks based on a scenario description
    (e.g. 'budget dropped 50%', 'guest count +30').
    Returns a before/after diff with trade-off options.
    """
    event = get_event(event_id, current_user.id, db)
    categories = get_budget_categories(event_id, current_user.id, db)

    from app.services.event_service import get_tasks
    tasks = get_tasks(event_id, current_user.id, db)

    budget_json = json.dumps(
        [{"name": c.name, "allocated": c.allocated, "spent": c.spent} for c in categories],
        indent=2,
    )
    tasks_json = json.dumps(
        [{"title": t.title, "status": t.status, "due_date": t.due_date} for t in tasks[:15]],
        indent=2,
    )

    user_prompt = REPLAN_USER.format(
        budget_json=budget_json,
        tasks_json=tasks_json,
        change_description=body.description,
        profile_json=json.dumps(event.profile, indent=2),
    )

    ai_text = await call_ai(REPLAN_SYSTEM, user_prompt, use_cache=False)

    if is_ai_fallback(ai_text):
        raise HTTPException(status_code=503, detail=ai_text)

    raw = extract_json_from_response(ai_text)
    if not raw:
        raise HTTPException(status_code=502, detail="AI returned unexpected format. Please retry.")

    try:
        validated = AIReplanDiff.model_validate(raw)
        return validated.model_dump()
    except ValidationError as exc:
        log.warning("AI replan schema validation failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="AI response did not match expected format.",
        ) from None
