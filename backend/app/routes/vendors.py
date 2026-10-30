"""Vendor routes – CRUD plus AI checklist/questions generation."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.models import BudgetCategory, User
from app.services.ai_fallbacks import fallback_vendor_questions
from app.services.ai_generation import (
    AI_SOURCE_RESPONSES,
    generate_with_fallback,
    mark_source,
)
from app.services.auth_service import get_current_user
from app.services.event_service import (
    create_vendor,
    delete_vendor,
    get_event,
    get_vendor,
    get_vendors,
    set_vendor_ai_data,
    update_vendor,
)
from app.services.prompts import VENDOR_QUESTIONS_SYSTEM, VENDOR_QUESTIONS_USER
from app.validators.schemas import AIVendorQuestions, VendorCreate, VendorResponse, VendorUpdate

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


@router.post(
    "/{vendor_id}/generate-questions",
    response_model=VendorResponse,
    responses=AI_SOURCE_RESPONSES,
)
async def generate_questions(
    event_id: str,
    vendor_id: str,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VendorResponse:
    """Generate AI checklist and questions for this vendor type."""
    event = get_event(event_id, current_user.id, db)
    vendor = get_vendor(event_id, vendor_id, current_user.id, db)

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

    validated, used_ai = await generate_with_fallback(
        VENDOR_QUESTIONS_SYSTEM,
        user_prompt,
        AIVendorQuestions,
        lambda: fallback_vendor_questions(event, vendor.vendor_type),
        use_cache=True,
        label="Vendor questions",
    )
    mark_source(response, used_ai)

    vendor = set_vendor_ai_data(vendor, validated.checklist, validated.questions, db)
    db.commit()
    db.refresh(vendor)
    return vendor
