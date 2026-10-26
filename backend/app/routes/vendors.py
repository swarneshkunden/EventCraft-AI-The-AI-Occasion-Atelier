"""Vendor routes – CRUD plus AI checklist/questions generation."""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.config.settings import get_settings
from app.models.models import BudgetCategory, User
from app.services.auth_service import get_current_user
from app.services.event_service import (
    create_vendor,
    delete_vendor,
    get_event,
    get_vendors,
    set_vendor_ai_data,
    update_vendor,
)
from app.services.ai_service import call_ai, extract_json_from_response, is_ai_fallback
from app.services.prompts import VENDOR_QUESTIONS_SYSTEM, VENDOR_QUESTIONS_USER
from app.validators.schemas import AIVendorQuestions, VendorCreate, VendorResponse, VendorUpdate

log = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/events/{event_id}/vendors", tags=["vendors"])


@router.get("", response_model=list[VendorResponse])
async def list_vendors(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    return get_vendors(event_id, current_user.id, db)


@router.post("", status_code=201, response_model=VendorResponse)
async def create(
    event_id: str,
    body: VendorCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VendorResponse:
    vendor = create_vendor(event_id, current_user.id, body, db)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.patch("/{vendor_id}", response_model=VendorResponse)
async def update(
    event_id: str,
    vendor_id: str,
    body: VendorUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VendorResponse:
    vendor = update_vendor(event_id, vendor_id, current_user.id, body, db)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.delete("/{vendor_id}", status_code=204)
async def delete(
    event_id: str,
    vendor_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    delete_vendor(event_id, vendor_id, current_user.id, db)
    db.commit()


@router.post("/{vendor_id}/generate-questions", response_model=VendorResponse)
async def generate_questions(
    event_id: str,
    vendor_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VendorResponse:
    """Generate AI checklist and questions for this vendor type."""
    event = get_event(event_id, current_user.id, db)
    vendors = get_vendors(event_id, current_user.id, db)
    vendor = next((v for v in vendors if v.id == vendor_id), None)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Find budget for this vendor type
    budget_for_type = (
        db.query(BudgetCategory)
        .filter(BudgetCategory.event_id == event_id)
        .all()
    )
    cat_budget = next(
        (c.allocated for c in budget_for_type if vendor.vendor_type.lower() in c.name.lower()),
        0,
    )

    user_prompt = VENDOR_QUESTIONS_USER.format(
        vendor_type=vendor.vendor_type,
        event_type=event.event_type,
        guest_count=event.guest_count,
        currency=current_user.currency,
        category_budget=cat_budget,
    )

    ai_text = await call_ai(VENDOR_QUESTIONS_SYSTEM, user_prompt, use_cache=True)

    if is_ai_fallback(ai_text):
        raise HTTPException(status_code=503, detail=ai_text)

    raw = extract_json_from_response(ai_text)
    if not raw:
        raise HTTPException(status_code=502, detail="AI returned unexpected format. Please retry.")

    try:
        validated = AIVendorQuestions.model_validate(raw)
    except Exception as e:
        log.warning("AI vendor response schema validation failed: %s", type(e).__name__)
        raise HTTPException(status_code=502, detail="AI response did not match expected format.")

    vendor = set_vendor_ai_data(vendor, validated.checklist, validated.questions, db)
    db.commit()
    db.refresh(vendor)
    return vendor
