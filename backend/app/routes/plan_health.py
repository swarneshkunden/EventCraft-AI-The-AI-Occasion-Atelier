"""Plan-health scoring and user-approved crisis changes."""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.config.settings import get_settings
from app.models.models import BudgetCategory, PlanChangeProposal, Task, User, Vendor
from app.services.ai_service import call_ai, extract_json_from_response, is_ai_fallback
from app.services.auth_service import get_current_user
from app.services.event_service import get_event
from app.services.plan_health_service import (
    accept_crisis_proposal,
    calculate_plan_health,
    create_crisis_proposal,
    decline_crisis_proposal,
    parse_known_crisis,
    undo_crisis_proposal,
)
from app.services.prompts import CRISIS_INTENT_SYSTEM, CRISIS_INTENT_USER
from app.validators.schemas import (
    AcceptCrisisProposalRequest,
    CrisisIntent,
    CrisisRequest,
)

log = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(
    prefix="/api/events/{event_id}/plan-health",
    tags=["plan-health"],
)


def _event_data(event_id: str, user_id: str, db: Session):
    event = get_event(event_id, user_id, db)
    categories = db.query(BudgetCategory).filter(BudgetCategory.event_id == event_id).all()
    tasks = db.query(Task).filter(Task.event_id == event_id).all()
    vendors = db.query(Vendor).filter(Vendor.event_id == event_id).all()
    return event, categories, tasks, vendors


@router.get("")
async def get_plan_health(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    event, categories, tasks, vendors = _event_data(event_id, current_user.id, db)
    return calculate_plan_health(
        event.total_budget,
        event.guest_count,
        event.event_date,
        categories,
        tasks,
        vendors,
    )


@router.post("/crisis", status_code=201)
async def propose_crisis_response(
    event_id: str,
    body: CrisisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    event = get_event(event_id, current_user.id, db)
    intent = parse_known_crisis(body.description, event.event_date)
    ai_used = False

    if intent is None and settings.GEMINI_API_KEY:
        prompt = CRISIS_INTENT_USER.format(
            description_json=json.dumps({"scenario": body.description}, ensure_ascii=True)
        )
        ai_text = await call_ai(CRISIS_INTENT_SYSTEM, prompt, use_cache=False)
        if not is_ai_fallback(ai_text):
            raw = extract_json_from_response(ai_text)
            if raw is not None:
                try:
                    intent = CrisisIntent.model_validate(raw)
                    ai_used = True
                except ValidationError as exc:
                    log.warning("Crisis intent schema validation failed: %s", type(exc).__name__)

    if intent is None:
        intent = CrisisIntent(kind="general")

    proposal = create_crisis_proposal(
        event,
        current_user.id,
        intent,
        ai_used,
        db,
    )
    db.commit()
    return {
        "proposal_id": proposal.id,
        "status": proposal.status,
        "interpretation": (
            f"AI classified this as {intent.kind.replace('_', ' ')}."
            if ai_used
            else f"Using a deterministic {intent.kind.replace('_', ' ')} response."
        ),
        "ai_used": ai_used,
        "options": [
            {
                "id": option["id"],
                "label": option["label"],
                "tradeoff": option["tradeoff"],
                "diff": option["diff"],
            }
            for option in proposal.options
        ],
    }


@router.post("/proposals/{proposal_id}/accept")
async def accept_proposal(
    event_id: str,
    proposal_id: str,
    body: AcceptCrisisProposalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_event(event_id, current_user.id, db)
    proposal = db.query(PlanChangeProposal).filter(
        PlanChangeProposal.id == proposal_id,
        PlanChangeProposal.event_id == event_id,
        PlanChangeProposal.owner_id == current_user.id,
    ).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    accept_crisis_proposal(proposal, body.option_id, db)
    db.commit()
    return {
        "status": proposal.status,
        "selected_option_id": proposal.selected_option_id,
        "undo_available": True,
    }


@router.post("/proposals/{proposal_id}/undo")
async def undo_proposal(
    event_id: str,
    proposal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_event(event_id, current_user.id, db)
    proposal = db.query(PlanChangeProposal).filter(
        PlanChangeProposal.id == proposal_id,
        PlanChangeProposal.event_id == event_id,
        PlanChangeProposal.owner_id == current_user.id,
    ).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    undo_crisis_proposal(proposal, db)
    db.commit()
    return {"status": proposal.status, "undo_available": False}


@router.post("/proposals/{proposal_id}/decline")
async def decline_proposal(
    event_id: str,
    proposal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_event(event_id, current_user.id, db)
    proposal = db.query(PlanChangeProposal).filter(
        PlanChangeProposal.id == proposal_id,
        PlanChangeProposal.event_id == event_id,
        PlanChangeProposal.owner_id == current_user.id,
    ).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found.")
    decline_crisis_proposal(proposal)
    db.commit()
    return {"status": proposal.status}
