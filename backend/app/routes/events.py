"""Event CRUD routes."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.models import User
from app.services.auth_service import get_current_user
from app.services.event_service import (
    create_event,
    delete_event,
    get_event,
    list_events,
    update_event,
)
from app.validators.schemas import EventCreateRequest, EventResponse, EventUpdateRequest

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])


@router.post("", status_code=201, response_model=EventResponse)
async def create(
    body: EventCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventResponse:
    event = create_event(current_user.id, body, db)
    db.commit()
    db.refresh(event)
    return event


@router.get("", response_model=list[EventResponse])
async def list_all(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    return list_events(current_user.id, db)


@router.get("/{event_id}", response_model=EventResponse)
async def get_one(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventResponse:
    return get_event(event_id, current_user.id, db)


@router.patch("/{event_id}", response_model=EventResponse)
async def update(
    event_id: str,
    body: EventUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventResponse:
    event = update_event(event_id, current_user.id, body, db)
    db.commit()
    db.refresh(event)
    return event


@router.delete("/{event_id}", status_code=204)
async def delete(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    delete_event(event_id, current_user.id, db)
    db.commit()
