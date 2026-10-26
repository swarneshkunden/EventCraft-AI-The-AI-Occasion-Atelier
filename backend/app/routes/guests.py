"""Guest routes – CRUD, CSV import, pagination."""
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.models.models import User
from app.services.auth_service import get_current_user
from app.services.csv_service import parse_guest_csv
from app.services.event_service import (
    bulk_import_guests,
    create_guest,
    delete_guest,
    get_guests_paginated,
    update_guest,
)
from app.validators.schemas import GuestCreate, GuestListResponse, GuestResponse, GuestUpdate

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events/{event_id}/guests", tags=["guests"])


@router.get("", response_model=GuestListResponse)
async def list_guests(
    event_id: str,
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GuestListResponse:
    guests, total = get_guests_paginated(event_id, current_user.id, db, page, page_size)
    return GuestListResponse(guests=guests, total=total, page=page, page_size=page_size)


@router.post("", status_code=201, response_model=GuestResponse)
async def add_guest(
    event_id: str,
    body: GuestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GuestResponse:
    guest = create_guest(event_id, current_user.id, body, db)
    db.commit()
    db.refresh(guest)
    return guest


@router.patch("/{guest_id}", response_model=GuestResponse)
async def update(
    event_id: str,
    guest_id: str,
    body: GuestUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GuestResponse:
    guest = update_guest(event_id, guest_id, current_user.id, body, db)
    db.commit()
    db.refresh(guest)
    return guest


@router.delete("/{guest_id}", status_code=204)
async def delete(
    event_id: str,
    guest_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    delete_guest(event_id, guest_id, current_user.id, db)
    db.commit()


@router.post("/import-csv")
async def import_csv(
    event_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rows = await parse_guest_csv(file)
    imported, skipped = bulk_import_guests(event_id, current_user.id, rows, db)
    db.commit()
    return {"imported": imported, "skipped": skipped, "message": f"Imported {imported} guests."}
