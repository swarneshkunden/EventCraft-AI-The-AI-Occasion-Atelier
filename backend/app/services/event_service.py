"""
Event service – CRUD and business logic for events, budget, tasks, vendors, guests.
All DB writes use parameterized queries through the ORM.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.models import (
    BudgetCategory,
    ChatMessage,
    Event,
    EventType,
    Guest,
    Task,
    TaskStatus,
    Vendor,
    VendorType,
)
from app.validators.schemas import (
    BudgetCategoryCreate,
    BudgetCategoryUpdate,
    EventCreateRequest,
    EventProfile,
    EventUpdateRequest,
    GuestCreate,
    GuestUpdate,
    TaskCreate,
    TaskUpdate,
    VendorCreate,
    VendorUpdate,
)

log = logging.getLogger(__name__)


# ── Authorization guard ───────────────────────────────────────────────────────

def _assert_owner(event: Optional[Event], user_id: str) -> Event:
    if not event or event.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


# ── Events ────────────────────────────────────────────────────────────────────

def create_event(user_id: str, data: EventCreateRequest, db: Session) -> Event:
    event = Event(
        owner_id=user_id,
        name=data.name,
        event_type=data.event_type,
        profile=data.profile.model_dump(),
        total_budget=data.profile.budget,
        event_date=data.profile.event_date,
        guest_count=data.profile.guest_count,
    )
    db.add(event)
    db.flush()
    return event


def get_event(event_id: str, user_id: str, db: Session) -> Event:
    event = db.query(Event).filter(Event.id == event_id).first()
    return _assert_owner(event, user_id)


def list_events(user_id: str, db: Session) -> list[Event]:
    return (
        db.query(Event)
        .filter(Event.owner_id == user_id)
        .order_by(Event.created_at.desc())
        .all()
    )


def update_event(event_id: str, user_id: str, data: EventUpdateRequest, db: Session) -> Event:
    event = get_event(event_id, user_id, db)
    if data.name is not None:
        event.name = data.name
    if data.event_type is not None:
        event.event_type = data.event_type
    if data.profile:
        merged = {**event.profile, **data.profile.model_dump(exclude_none=True)}
        event.profile = merged
        event.total_budget = merged.get("budget", event.total_budget)
        event.guest_count = merged.get("guest_count", event.guest_count)
        event.event_date = merged.get("event_date", event.event_date)
    db.flush()
    return event


def delete_event(event_id: str, user_id: str, db: Session) -> None:
    event = get_event(event_id, user_id, db)
    db.delete(event)


# ── Budget ────────────────────────────────────────────────────────────────────

def set_budget_categories(
    event_id: str, user_id: str, categories: list[BudgetCategoryCreate], db: Session
) -> list[BudgetCategory]:
    event = get_event(event_id, user_id, db)
    # Delete existing and replace (atomic operation)
    db.query(BudgetCategory).filter(BudgetCategory.event_id == event_id).delete()
    records = []
    for i, cat in enumerate(categories):
        record = BudgetCategory(
            event_id=event_id,
            name=cat.name,
            allocated=cat.allocated,
            spent=cat.spent,
            notes=cat.notes,
            sort_order=i,
        )
        db.add(record)
        records.append(record)
    db.flush()
    return records


def get_budget_categories(event_id: str, user_id: str, db: Session) -> list[BudgetCategory]:
    get_event(event_id, user_id, db)  # ownership check
    return (
        db.query(BudgetCategory)
        .filter(BudgetCategory.event_id == event_id)
        .order_by(BudgetCategory.sort_order)
        .all()
    )


def update_budget_category(
    event_id: str, cat_id: str, user_id: str, data: BudgetCategoryUpdate, db: Session
) -> BudgetCategory:
    get_event(event_id, user_id, db)
    cat = db.query(BudgetCategory).filter(
        BudgetCategory.id == cat_id, BudgetCategory.event_id == event_id
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    if data.allocated is not None:
        cat.allocated = data.allocated
    if data.spent is not None:
        cat.spent = data.spent
    if data.notes is not None:
        cat.notes = data.notes
    db.flush()
    return cat


# ── Tasks ─────────────────────────────────────────────────────────────────────

def bulk_create_tasks(event_id: str, user_id: str, task_dicts: list[dict], db: Session) -> list[Task]:
    get_event(event_id, user_id, db)
    # Clear existing AI-generated tasks before bulk create
    db.query(Task).filter(Task.event_id == event_id).delete()
    records = []
    for t in task_dicts:
        record = Task(
            event_id=event_id,
            title=t.get("title", "")[:300],
            description=t.get("description", "")[:2000],
            category=t.get("category", "general")[:100],
            due_date=t.get("due_date"),
            priority=int(t.get("priority", 5)),
            depends_on=t.get("depends_on", []),
        )
        db.add(record)
        records.append(record)
    db.flush()
    return records


def create_task(event_id: str, user_id: str, data: TaskCreate, db: Session) -> Task:
    get_event(event_id, user_id, db)
    task = Task(
        event_id=event_id,
        title=data.title[:300],
        description=data.description[:2000],
        category=data.category[:100],
        due_date=data.due_date,
        priority=data.priority,
        depends_on=data.depends_on,
    )
    db.add(task)
    db.flush()
    return task


def get_tasks(event_id: str, user_id: str, db: Session) -> list[Task]:
    get_event(event_id, user_id, db)
    return (
        db.query(Task)
        .filter(Task.event_id == event_id)
        .order_by(Task.priority, Task.due_date)
        .all()
    )


def update_task(event_id: str, task_id: str, user_id: str, data: TaskUpdate, db: Session) -> Task:
    get_event(event_id, user_id, db)
    task = db.query(Task).filter(Task.id == task_id, Task.event_id == event_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    old_status = task.status
    if data.status:
        task.status = data.status
        if data.status == TaskStatus.completed and old_status != TaskStatus.completed:
            task.completed_at = datetime.now(timezone.utc)
        elif data.status != TaskStatus.completed:
            task.completed_at = None
    if data.due_date is not None:
        task.due_date = data.due_date

    # Cascade: mark dependent tasks as blocked if this task is blocked/delayed
    if data.status in ("blocked",):
        _cascade_block(task.title, event_id, db)

    db.flush()
    return task


def _cascade_block(blocked_title: str, event_id: str, db: Session) -> None:
    """Mark tasks that depend on the blocked task as blocked too."""
    dependent_tasks = db.query(Task).filter(Task.event_id == event_id).all()
    for t in dependent_tasks:
        if blocked_title in (t.depends_on or []):
            t.status = TaskStatus.blocked


def compute_task_readiness(tasks: list[Task]) -> list[dict]:
    """
    Returns tasks annotated with is_ready (all dependencies completed).
    """
    completed_titles = {t.title for t in tasks if t.status == TaskStatus.completed}
    result = []
    for t in tasks:
        deps = t.depends_on or []
        unmet = [d for d in deps if d not in completed_titles]
        result.append({
            "task": t,
            "is_ready": len(unmet) == 0 and t.status not in (TaskStatus.completed, TaskStatus.blocked),
            "blocked_by": unmet,
        })
    return result


# ── Vendors ───────────────────────────────────────────────────────────────────

def create_vendor(event_id: str, user_id: str, data: VendorCreate, db: Session) -> Vendor:
    get_event(event_id, user_id, db)
    vendor = Vendor(
        event_id=event_id,
        vendor_type=data.vendor_type,
        name=data.name,
        contact=data.contact,
        quoted_price=data.quoted_price,
        guests_covered=data.guests_covered,
        inclusions=data.inclusions,
        extra_charges=data.extra_charges,
        open_questions=data.open_questions,
        notes=data.notes,
    )
    db.add(vendor)
    db.flush()
    return vendor


def get_vendors(event_id: str, user_id: str, db: Session) -> list[Vendor]:
    get_event(event_id, user_id, db)
    return db.query(Vendor).filter(Vendor.event_id == event_id).all()


def update_vendor(
    event_id: str, vendor_id: str, user_id: str, data: VendorUpdate, db: Session
) -> Vendor:
    get_event(event_id, user_id, db)
    vendor = db.query(Vendor).filter(
        Vendor.id == vendor_id, Vendor.event_id == event_id
    ).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(vendor, field, value)
    db.flush()
    return vendor


def delete_vendor(event_id: str, vendor_id: str, user_id: str, db: Session) -> None:
    get_event(event_id, user_id, db)
    vendor = db.query(Vendor).filter(
        Vendor.id == vendor_id, Vendor.event_id == event_id
    ).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    db.delete(vendor)


def set_vendor_ai_data(vendor: Vendor, checklist: list, questions: list, db: Session) -> Vendor:
    vendor.ai_checklist = checklist
    vendor.ai_questions = questions
    db.flush()
    return vendor


# ── Guests ────────────────────────────────────────────────────────────────────

def create_guest(event_id: str, user_id: str, data: GuestCreate, db: Session) -> Guest:
    get_event(event_id, user_id, db)
    guest = Guest(event_id=event_id, **data.model_dump())
    db.add(guest)
    db.flush()
    # Update guest count on event
    _sync_guest_count(event_id, db)
    return guest


def get_guests_paginated(
    event_id: str, user_id: str, db: Session, page: int = 1, page_size: int = 50
) -> tuple[list[Guest], int]:
    get_event(event_id, user_id, db)
    q = db.query(Guest).filter(Guest.event_id == event_id)
    total = q.count()
    guests = q.offset((page - 1) * page_size).limit(page_size).all()
    return guests, total


def update_guest(
    event_id: str, guest_id: str, user_id: str, data: GuestUpdate, db: Session
) -> Guest:
    get_event(event_id, user_id, db)
    guest = db.query(Guest).filter(Guest.id == guest_id, Guest.event_id == event_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(guest, field, value)
    db.flush()
    return guest


def delete_guest(event_id: str, guest_id: str, user_id: str, db: Session) -> None:
    get_event(event_id, user_id, db)
    guest = db.query(Guest).filter(Guest.id == guest_id, Guest.event_id == event_id).first()
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    db.delete(guest)
    db.flush()
    _sync_guest_count(event_id, db)


def bulk_import_guests(
    event_id: str, user_id: str, rows: list[dict], db: Session
) -> tuple[int, int]:
    """Bulk insert guest rows. Returns (imported_count, skipped_count)."""
    get_event(event_id, user_id, db)
    imported = skipped = 0
    for row in rows:
        try:
            schema = GuestCreate(**row)
            guest = Guest(event_id=event_id, **schema.model_dump())
            db.add(guest)
            imported += 1
        except Exception:
            skipped += 1
    db.flush()
    _sync_guest_count(event_id, db)
    return imported, skipped


def _sync_guest_count(event_id: str, db: Session) -> None:
    count = db.query(Guest).filter(Guest.event_id == event_id).count()
    db.query(Event).filter(Event.id == event_id).update({"guest_count": count})


# ── Chat ──────────────────────────────────────────────────────────────────────

def save_chat_message(event_id: str, role: str, content: str, db: Session) -> ChatMessage:
    msg = ChatMessage(event_id=event_id, role=role, content=content)
    db.add(msg)
    db.flush()
    return msg


def get_chat_history(event_id: str, user_id: str, db: Session, limit: int = 50) -> list[ChatMessage]:
    get_event(event_id, user_id, db)
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.event_id == event_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
