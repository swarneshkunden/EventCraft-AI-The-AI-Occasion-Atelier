"""Budget routes – category management and AI split generation."""

import json

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.errors import InvalidRequestError
from app.models.models import User
from app.services.ai_fallbacks import fallback_budget_split
from app.services.ai_generation import (
    AI_SOURCE_RESPONSES,
    generate_model,
    generate_with_fallback,
    mark_source,
)
from app.services.auth_service import get_current_user
from app.services.event_service import (
    get_budget_categories,
    get_event,
    get_tasks,
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
        raise InvalidRequestError("Too many categories (max 20)")
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


@router.post(
    "/ai-split",
    response_model=list[BudgetCategoryResponse],
    responses=AI_SOURCE_RESPONSES,
)
async def generate_ai_split(
    event_id: str,
    response: Response,
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

    validated, used_ai = await generate_with_fallback(
        BUDGET_SPLIT_SYSTEM,
        user_prompt,
        AIBudgetSplit,
        lambda: fallback_budget_split(event),
        use_cache=True,
        label="Budget split",
    )
    mark_source(response, used_ai)

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


@router.post("/scenario", response_model=AIReplanDiff)
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

    validated = await generate_model(
        REPLAN_SYSTEM,
        user_prompt,
        AIReplanDiff,
        use_cache=False,
        label="Budget scenario",
    )
    return validated.model_dump()
