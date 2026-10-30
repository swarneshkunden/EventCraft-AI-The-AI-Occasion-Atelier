"""Persist, accept, undo, and decline crisis proposals."""
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.models import (
    BudgetCategory,
    Event,
    PlanChangeAudit,
    PlanChangeProposal,
    Task,
    Vendor,
)
from app.services.crisis_options_service import build_crisis_options
from app.services.plan_utils import enum_value
from app.validators.schemas import CrisisIntent


def capture_event_state(
    event: Event,
    categories: list[BudgetCategory],
    tasks: list[Task],
    vendors: list[Vendor],
) -> dict:
    profile = event.profile or {}
    return {
        "event_date": event.event_date,
        "guest_count": event.guest_count,
        "profile": {
            key: {"present": key in profile, "value": profile.get(key)}
            for key in ("event_date", "guest_count")
        },
        "budget": sorted(
            [
                {
                    "id": item.id,
                    "allocated": round(float(item.allocated), 2),
                    "spent": round(float(item.spent), 2),
                    "notes": item.notes or "",
                }
                for item in categories
            ],
            key=lambda item: item["id"],
        ),
        "tasks": sorted(
            [
                {"id": item.id, "due_date": item.due_date, "status": str(enum_value(item.status))}
                for item in tasks
            ],
            key=lambda item: item["id"],
        ),
        "vendors": sorted(
            [{"id": item.id, "is_selected": bool(item.is_selected)} for item in vendors],
            key=lambda item: item["id"],
        ),
    }

def _event_records(
    event_id: str,
    db: Session,
) -> tuple[list[BudgetCategory], list[Task], list[Vendor]]:
    """Fetch the budget, task, and vendor records for an event."""
    categories = db.query(BudgetCategory).filter(BudgetCategory.event_id == event_id).all()
    tasks = db.query(Task).filter(Task.event_id == event_id).all()
    vendors = db.query(Vendor).filter(Vendor.event_id == event_id).all()
    return categories, tasks, vendors

def create_crisis_proposal(
    event: Event,
    owner_id: str,
    intent: CrisisIntent,
    ai_used: bool,
    db: Session,
) -> PlanChangeProposal:
    categories, tasks, vendors = _event_records(event.id, db)
    proposal = PlanChangeProposal(
        event_id=event.id,
        owner_id=owner_id,
        options=build_crisis_options(event, intent, categories, tasks, vendors),
        baseline=capture_event_state(event, categories, tasks, vendors),
    )
    db.add(proposal)
    db.flush()
    proposal.options = [dict(option, ai_interpreted=ai_used) for option in proposal.options]
    return proposal

def accept_crisis_proposal(
    proposal: PlanChangeProposal,
    option_id: str,
    db: Session,
) -> PlanChangeProposal:
    if proposal.status != "pending":
        raise HTTPException(status_code=409, detail="This proposal is no longer available.")
    event = db.query(Event).filter(Event.id == proposal.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
    categories, tasks, vendors = _event_records(event.id, db)
    if capture_event_state(event, categories, tasks, vendors) != proposal.baseline:
        raise HTTPException(
            status_code=409,
            detail="The plan changed after this proposal was created. Generate a fresh proposal.",
        )
    selected = next((item for item in proposal.options if item["id"] == option_id), None)
    if not selected:
        raise HTTPException(status_code=400, detail="Select one of the available options.")
    changes = selected["changes"]

    if changes.get("event_date") is not None:
        event.event_date = changes["event_date"]
        profile = dict(event.profile or {})
        profile["event_date"] = event.event_date
        event.profile = profile
    if changes.get("guest_count") is not None:
        event.guest_count = changes["guest_count"]
        profile = dict(event.profile or {})
        profile["guest_count"] = event.guest_count
        event.profile = profile

    category_map = {item.id: item for item in categories}
    for update in changes["budget_updates"]:
        category = category_map.get(update["id"])
        if category:
            category.allocated = update["allocated"]
            category.notes = update["notes"]
    task_map = {item.id: item for item in tasks}
    for update in changes["task_updates"]:
        task = task_map.get(update["id"])
        if task:
            task.due_date = update["due_date"]
    vendor_map = {item.id: item for item in vendors}
    for update in changes["vendor_updates"]:
        vendor = vendor_map.get(update["id"])
        if vendor:
            vendor.is_selected = update["is_selected"]

    added_ids = []
    for task_data in changes["tasks_to_add"]:
        task = Task(event_id=event.id, **task_data)
        db.add(task)
        db.flush()
        added_ids.append(task.id)

    categories, tasks, vendors = _event_records(event.id, db)
    proposal.after_state = capture_event_state(event, categories, tasks, vendors)
    proposal.added_task_ids = added_ids
    proposal.status = "accepted"
    proposal.selected_option_id = option_id
    proposal.accepted_at = datetime.now(UTC)
    changed_fields = sorted({
        field
        for field, condition in (
            ("event_date", changes.get("event_date") is not None),
            ("guest_count", changes.get("guest_count") is not None),
            ("budget", bool(changes["budget_updates"])),
            ("tasks", bool(changes["task_updates"] or changes["tasks_to_add"])),
            ("vendors", bool(changes["vendor_updates"])),
        )
        if condition
    })
    db.add(PlanChangeAudit(
        proposal_id=proposal.id,
        event_id=event.id,
        owner_id=proposal.owner_id,
        action="accepted",
        changed_fields=changed_fields,
    ))
    db.flush()
    return proposal

def undo_crisis_proposal(proposal: PlanChangeProposal, db: Session) -> PlanChangeProposal:
    if proposal.status != "accepted" or not proposal.after_state:
        raise HTTPException(status_code=409, detail="Only an accepted proposal can be undone.")
    event = db.query(Event).filter(Event.id == proposal.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")
    categories, tasks, vendors = _event_records(event.id, db)
    if capture_event_state(event, categories, tasks, vendors) != proposal.after_state:
        raise HTTPException(
            status_code=409,
            detail="The plan changed after this proposal was accepted. Undo would overwrite newer work.",
        )

    baseline = proposal.baseline
    event.event_date = baseline["event_date"]
    event.guest_count = baseline["guest_count"]
    profile = dict(event.profile or {})
    for key, entry in baseline["profile"].items():
        if entry["present"]:
            profile[key] = entry["value"]
        else:
            profile.pop(key, None)
    event.profile = profile

    category_map = {item.id: item for item in categories}
    for snapshot in baseline["budget"]:
        category = category_map.get(snapshot["id"])
        if category:
            category.allocated = snapshot["allocated"]
            category.spent = snapshot["spent"]
            category.notes = snapshot["notes"]
    task_map = {item.id: item for item in tasks}
    for snapshot in baseline["tasks"]:
        task = task_map.get(snapshot["id"])
        if task:
            task.due_date = snapshot["due_date"]
            task.status = snapshot["status"]
    vendor_map = {item.id: item for item in vendors}
    for snapshot in baseline["vendors"]:
        vendor = vendor_map.get(snapshot["id"])
        if vendor:
            vendor.is_selected = snapshot["is_selected"]
    if proposal.added_task_ids:
        db.query(Task).filter(
            Task.event_id == event.id,
            Task.id.in_(proposal.added_task_ids),
        ).delete(synchronize_session=False)

    proposal.status = "undone"
    proposal.undone_at = datetime.now(UTC)
    fields = {
        field
        for field, condition in (
            ("event_date", baseline["event_date"] != proposal.after_state["event_date"]),
            ("guest_count", baseline["guest_count"] != proposal.after_state["guest_count"]),
            ("budget", baseline["budget"] != proposal.after_state["budget"]),
            ("tasks", baseline["tasks"] != proposal.after_state["tasks"]),
            ("vendors", baseline["vendors"] != proposal.after_state["vendors"]),
        )
        if condition
    }
    db.add(PlanChangeAudit(
        proposal_id=proposal.id,
        event_id=event.id,
        owner_id=proposal.owner_id,
        action="undone",
        changed_fields=sorted(fields),
    ))
    db.flush()
    return proposal

def decline_crisis_proposal(proposal: PlanChangeProposal) -> PlanChangeProposal:
    if proposal.status != "pending":
        raise HTTPException(status_code=409, detail="This proposal is no longer available.")
    proposal.status = "declined"
    return proposal
