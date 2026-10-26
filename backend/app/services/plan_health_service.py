"""Deterministic plan-health scoring and reviewable crisis proposals."""
import re
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.models import (
    BudgetCategory,
    Event,
    PlanChangeAudit,
    PlanChangeProposal,
    Task,
    TaskStatus,
    Vendor,
)
from app.validators.schemas import CrisisIntent


def _value(value):
    return value.value if hasattr(value, "value") else value


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _has_dependency_cycle(tasks: list[Task]) -> bool:
    by_title = {task.title: task.title for task in tasks}
    graph = {
        task.title: [
            dependency
            for dependency in (task.depends_on or [])
            if dependency in by_title
        ]
        for task in tasks
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(title: str) -> bool:
        if title in visiting:
            return True
        if title in visited:
            return False
        visiting.add(title)
        if any(visit(dependency) for dependency in graph[title]):
            return True
        visiting.remove(title)
        visited.add(title)
        return False

    return any(visit(title) for title in graph)


def calculate_plan_health(
    total_budget: float,
    guest_count: int,
    event_date: str | None,
    categories: list[BudgetCategory],
    tasks: list[Task],
    vendors: list[Vendor],
    today: date | None = None,
) -> dict:
    today = today or date.today()
    spent = round(sum(float(category.spent or 0) for category in categories), 2)
    allocated = round(sum(float(category.allocated or 0) for category in categories), 2)
    total_budget = round(float(total_budget), 2)
    incomplete = [task for task in tasks if _value(task.status) != TaskStatus.completed.value]
    overdue = [
        task for task in incomplete
        if (due := _date(task.due_date)) is not None and due < today
    ]
    blocked = [task for task in tasks if _value(task.status) == TaskStatus.blocked.value]
    missing_quotes = [vendor for vendor in vendors if vendor.quoted_price is None]
    deductions: list[dict] = []

    def add(key: str, points: int, reason: str, next_step: str) -> None:
        if points > 0:
            deductions.append({
                "key": key,
                "points": points,
                "reason": reason,
                "next_step": next_step,
            })

    if total_budget > 0:
        if spent > total_budget:
            add(
                "budget_overrun",
                25,
                f"Recorded spending exceeds the total budget by {round(spent - total_budget, 2):,.2f}.",
                "Review committed costs before approving new spending.",
            )
        elif allocated > total_budget:
            add(
                "budget_overallocated",
                15,
                f"Budget categories allocate {allocated - total_budget:,.2f} more than the event budget.",
                "Rebalance category allocations to fit the total budget.",
            )
        elif spent >= total_budget * 0.9:
            add(
                "budget_pressure",
                10,
                "At least 90% of the total budget is already recorded as spent.",
                "Check remaining commitments and protect a contingency buffer.",
            )

    if overdue:
        add(
            "overdue_tasks",
            min(20, len(overdue) * 5),
            f"{len(overdue)} unfinished task(s) have a due date before today.",
            "Review overdue tasks and reset realistic owners and dates.",
        )
    if blocked:
        add(
            "blocked_tasks",
            min(15, len(blocked) * 5),
            f"{len(blocked)} task(s) are marked blocked.",
            "Resolve each prerequisite before progressing dependent work.",
        )
    if _has_dependency_cycle(tasks):
        add(
            "dependency_cycle",
            15,
            "The task dependencies contain a cycle, so at least one task cannot become ready.",
            "Edit dependencies to create a forward-only sequence.",
        )
    if not tasks:
        add(
            "missing_timeline",
            10,
            "No timeline tasks are recorded for this event.",
            "Create a first milestone list to make the plan actionable.",
        )
    if missing_quotes:
        add(
            "unverified_quotes",
            min(15, len(missing_quotes) * 5),
            f"{len(missing_quotes)} vendor(s) have no quote on file; prices need verification.",
            "Request written quotes and confirm availability directly with each vendor.",
        )

    days_until = None
    target_date = _date(event_date)
    if target_date is not None:
        days_until = (target_date - today).days
        if days_until < 0:
            add(
                "past_event_date",
                15,
                "The event date has passed but the plan is still active.",
                "Confirm the event date or archive the completed plan.",
            )
        elif days_until <= 30 and incomplete:
            points = 10 if days_until <= 7 else 7 if days_until <= 14 else 5
            add(
                "tight_deadline",
                points,
                f"The event is {days_until} day(s) away with {len(incomplete)} unfinished task(s).",
                "Prioritize essential tasks and confirm vendor commitments.",
            )

    undersized_venues = [
        vendor for vendor in vendors
        if _value(vendor.vendor_type) == "venue"
        and vendor.guests_covered is not None
        and vendor.guests_covered < guest_count
    ]
    if undersized_venues:
        add(
            "venue_capacity",
            15,
            f"{len(undersized_venues)} venue quote(s) list capacity below the {guest_count}-guest target.",
            "Verify room capacity and safe occupancy with the venue before confirming.",
        )

    score = max(0, 100 - sum(item["points"] for item in deductions))
    label = "On track" if score >= 85 else "Needs attention" if score >= 60 else "At risk"
    return {
        "score": score,
        "label": label,
        "days_until_event": days_until,
        "deductions": deductions,
        "summary": (
            "No tracked risks were found." if not deductions
            else f"{len(deductions)} plan risk area(s) need review."
        ),
    }


def parse_known_crisis(description: str, event_date: str | None) -> CrisisIntent | None:
    """Recognize supported changes with deterministic rules before any AI call."""
    text = description.casefold()
    if "cater" in text and re.search(r"\b(cancel(?:ed|led)?|withdrawn|dropped)\b", text):
        return CrisisIntent(kind="caterer_cancelled")
    if re.search(r"\b(rain|raining|weather|storm|outdoor)\b", text):
        return CrisisIntent(kind="weather_risk")

    if re.search(r"\b(guest|guests|attendee|attendees|headcount|people)\b", text):
        range_match = re.search(r"\bfrom\s+(\d+)\s+to\s+(\d+)\b", text)
        target_match = re.search(r"\bto\s+(\d+)\b", text)
        if range_match or target_match:
            target_count = int(range_match.group(2) if range_match else target_match.group(1))
            return CrisisIntent(kind="guest_count_change", new_guest_count=target_count)

    if event_date and re.search(r"\b(move|moved|advance|advanced|earlier|up)\b", text):
        match = re.search(r"\b(\d{1,3})\s*(day|days|week|weeks|month|months)\b", text)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            days = amount * (30 if unit.startswith("month") else 7 if unit.startswith("week") else 1)
            if 1 <= days <= 365:
                return CrisisIntent(kind="date_advanced", days_advanced=days)
    return None


def _deadline(event: Event, days_before: int) -> str:
    target = _date(event.event_date)
    candidate = target - timedelta(days=days_before) if target else date.today() + timedelta(days=1)
    return max(candidate, date.today()).isoformat()


def _option(
    option_id: str,
    label: str,
    tradeoff: str,
    changes: dict,
    diff: dict,
) -> dict:
    return {
        "id": option_id,
        "label": label,
        "tradeoff": tradeoff,
        "diff": diff,
        "changes": changes,
    }


def build_crisis_options(
    event: Event,
    intent: CrisisIntent,
    categories: list[BudgetCategory],
    tasks: list[Task],
    vendors: list[Vendor],
) -> list[dict]:
    today = date.today()
    open_tasks = [task for task in tasks if _value(task.status) != TaskStatus.completed.value]

    if intent.kind == "guest_count_change":
        new_count = intent.new_guest_count
        old_count = event.guest_count
        catering = next(
            (category for category in categories if "cater" in category.name.casefold()),
            None,
        )
        budget_updates = []
        budget_diff = []
        if catering and old_count > 0:
            new_allocation = round(float(catering.allocated) * new_count / old_count, 2)
            note = (catering.notes or "").strip()
            estimate_note = "Estimated from the current per-guest assumption; not a confirmed quote."
            if estimate_note.casefold() not in note.casefold():
                note = f"{note}\n{estimate_note}".strip()
            budget_updates.append({
                "id": catering.id,
                "allocated": new_allocation,
                "notes": note,
            })
            budget_diff.append({
                "name": catering.name,
                "before": float(catering.allocated),
                "after": new_allocation,
                "estimated": True,
            })
        review_task = {
            "title": f"Reconfirm venue capacity and catering for {new_count} guests",
            "description": "New guest count is a planning input. Confirm capacity and pricing directly.",
            "category": "guest_management",
            "due_date": _deadline(event, 21),
            "priority": 1,
            "depends_on": [],
        }
        return [
            _option(
                "scale_estimate",
                "Scale the catering estimate",
                "Uses the existing per-guest budget assumption; this is an estimate, not a quote.",
                {
                    "guest_count": new_count,
                    "budget_updates": budget_updates,
                    "task_updates": [],
                    "vendor_updates": [],
                    "tasks_to_add": [],
                },
                {
                    "guest_count": {"before": old_count, "after": new_count},
                    "budget": budget_diff,
                    "tasks": [],
                    "vendors": [],
                },
            ),
            _option(
                "hold_budget_review",
                "Keep budget unchanged and verify capacity",
                "Preserves current category allocations until new written quotes are confirmed.",
                {
                    "guest_count": new_count,
                    "budget_updates": [],
                    "task_updates": [],
                    "vendor_updates": [],
                    "tasks_to_add": [review_task],
                },
                {
                    "guest_count": {"before": old_count, "after": new_count},
                    "budget": [],
                    "tasks": [{"title": review_task["title"], "before": None, "after": review_task["due_date"]}],
                    "vendors": [],
                },
            ),
        ]

    if intent.kind == "date_advanced":
        old_date = _date(event.event_date)
        if not old_date or not intent.days_advanced:
            raise HTTPException(status_code=400, detail="A valid event date is required for this change.")
        new_date = old_date - timedelta(days=intent.days_advanced)
        if new_date <= today:
            raise HTTPException(
                status_code=400,
                detail="That change would move the event to today or earlier. Review the date and try again.",
            )
        shifts = []
        shift_diff = []
        for task in open_tasks:
            due = _date(task.due_date)
            if due:
                shifted = due - timedelta(days=intent.days_advanced)
                shifts.append({"id": task.id, "due_date": shifted.isoformat()})
                shift_diff.append({
                    "title": task.title,
                    "before": due.isoformat(),
                    "after": shifted.isoformat(),
                })
        review_task = {
            "title": "Review compressed timeline and vendor deadlines",
            "description": "The event date moved earlier. Confirm every fixed deadline with its owner.",
            "category": "logistics",
            "due_date": _deadline(event, max(1, (new_date - today).days - 1)),
            "priority": 1,
            "depends_on": [],
        }
        return [
            _option(
                "shift_open_tasks",
                "Shift unfinished task dates with the event",
                "Preserves each task's current lead time; shifted dates may need owner confirmation.",
                {
                    "event_date": new_date.isoformat(),
                    "guest_count": None,
                    "budget_updates": [],
                    "task_updates": shifts,
                    "vendor_updates": [],
                    "tasks_to_add": [],
                },
                {
                    "event_date": {"before": old_date.isoformat(), "after": new_date.isoformat()},
                    "budget": [],
                    "tasks": shift_diff,
                    "vendors": [],
                },
            ),
            _option(
                "keep_task_dates",
                "Change event date and add a timeline review",
                "Keeps existing task dates intact; some may now fall after the event and need manual review.",
                {
                    "event_date": new_date.isoformat(),
                    "guest_count": None,
                    "budget_updates": [],
                    "task_updates": [],
                    "vendor_updates": [],
                    "tasks_to_add": [review_task],
                },
                {
                    "event_date": {"before": old_date.isoformat(), "after": new_date.isoformat()},
                    "budget": [],
                    "tasks": [{"title": review_task["title"], "before": None, "after": review_task["due_date"]}],
                    "vendors": [],
                },
            ),
        ]

    if intent.kind == "caterer_cancelled":
        caterers = [vendor for vendor in vendors if _value(vendor.vendor_type) == "caterer"]
        vendor_updates = [
            {"id": vendor.id, "is_selected": False}
            for vendor in caterers if vendor.is_selected
        ]
        vendor_diff = [
            {"id": vendor.id, "before": bool(vendor.is_selected), "after": False}
            for vendor in caterers if vendor.is_selected
        ]
        option_tasks = [
            {
                "title": "Confirm replacement caterer shortlist",
                "description": "Contact alternatives and verify availability, menu, capacity and written terms.",
                "category": "catering",
                "due_date": _deadline(event, 30),
                "priority": 1,
                "depends_on": [],
            },
            {
                "title": "Request and compare replacement catering quotes",
                "description": "Compare written quotes and label all prices as estimates until confirmed.",
                "category": "catering",
                "due_date": _deadline(event, 21),
                "priority": 1,
                "depends_on": [],
            },
        ]
        return [
            _option(
                "replace_caterer",
                "Mark the selected caterer unselected and find a replacement",
                "Creates an urgent sourcing task; replacement prices and availability need verification.",
                {
                    "event_date": None,
                    "guest_count": None,
                    "budget_updates": [],
                    "task_updates": [],
                    "vendor_updates": vendor_updates,
                    "tasks_to_add": [option_tasks[0]],
                },
                {
                    "event_date": None,
                    "budget": [],
                    "tasks": [{"title": option_tasks[0]["title"], "before": None, "after": option_tasks[0]["due_date"]}],
                    "vendors": vendor_diff,
                },
            ),
            _option(
                "compare_quotes",
                "Keep current budget and compare replacement quotes",
                "Leaves all budget estimates unchanged until a replacement quote is verified.",
                {
                    "event_date": None,
                    "guest_count": None,
                    "budget_updates": [],
                    "task_updates": [],
                    "vendor_updates": vendor_updates,
                    "tasks_to_add": [option_tasks[1]],
                },
                {
                    "event_date": None,
                    "budget": [],
                    "tasks": [{"title": option_tasks[1]["title"], "before": None, "after": option_tasks[1]["due_date"]}],
                    "vendors": vendor_diff,
                },
            ),
        ]

    weather_tasks = [
        {
            "title": "Confirm an indoor weather-safe backup venue",
            "description": "Check availability, capacity, accessibility and cancellation terms directly.",
            "category": "venue",
            "due_date": _deadline(event, 14),
            "priority": 1,
            "depends_on": [],
        },
        {
            "title": "Prepare a rain contingency and guest communication plan",
            "description": "Confirm the trigger, owner, setup timing and guest update channel.",
            "category": "logistics",
            "due_date": _deadline(event, 7),
            "priority": 2,
            "depends_on": [],
        },
    ]
    if intent.kind == "weather_risk":
        return [
            _option(
                "indoor_backup",
                "Secure an indoor backup",
                "Prioritizes venue capacity and accessibility; availability must be verified.",
                {
                    "event_date": None,
                    "guest_count": None,
                    "budget_updates": [],
                    "task_updates": [],
                    "vendor_updates": [],
                    "tasks_to_add": [weather_tasks[0]],
                },
                {
                    "event_date": None,
                    "budget": [],
                    "tasks": [{"title": weather_tasks[0]["title"], "before": None, "after": weather_tasks[0]["due_date"]}],
                    "vendors": [],
                },
            ),
            _option(
                "guest_contingency",
                "Prepare a guest communication plan",
                "Keeps the current venue decision open while creating a clear contingency owner.",
                {
                    "event_date": None,
                    "guest_count": None,
                    "budget_updates": [],
                    "task_updates": [],
                    "vendor_updates": [],
                    "tasks_to_add": [weather_tasks[1]],
                },
                {
                    "event_date": None,
                    "budget": [],
                    "tasks": [{"title": weather_tasks[1]["title"], "before": None, "after": weather_tasks[1]["due_date"]}],
                    "vendors": [],
                },
            ),
        ]

    generic_tasks = [
        {
            "title": "Review the reported change with the event team",
            "description": "Confirm the affected decisions and assign an owner before changing the plan.",
            "category": "logistics",
            "due_date": _deadline(event, 14),
            "priority": 1,
            "depends_on": [],
        },
        {
            "title": "Check budget, timeline and vendor impact",
            "description": "Verify changes against written quotes and current task dependencies.",
            "category": "logistics",
            "due_date": _deadline(event, 7),
            "priority": 2,
            "depends_on": [],
        },
    ]
    return [
        _option(
            f"general_review_{index + 1}",
            label,
            tradeoff,
            {
                "event_date": None,
                "guest_count": None,
                "budget_updates": [],
                "task_updates": [],
                "vendor_updates": [],
                "tasks_to_add": [task],
            },
            {
                "event_date": None,
                "budget": [],
                "tasks": [{"title": task["title"], "before": None, "after": task["due_date"]}],
                "vendors": [],
            },
        )
        for index, (task, label, tradeoff) in enumerate([
            (
                generic_tasks[0],
                "Add a team review task",
                "Makes no plan assumptions; requires a human to clarify the reported change.",
            ),
            (
                generic_tasks[1],
                "Add a cross-check task",
                "Adds a verification step without changing estimates or commitments.",
            ),
        ])
    ]


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
                {"id": item.id, "due_date": item.due_date, "status": str(_value(item.status))}
                for item in tasks
            ],
            key=lambda item: item["id"],
        ),
        "vendors": sorted(
            [{"id": item.id, "is_selected": bool(item.is_selected)} for item in vendors],
            key=lambda item: item["id"],
        ),
    }


def _event_records(event_id: str, db: Session):
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
    proposal.accepted_at = datetime.now(timezone.utc)
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
    proposal.undone_at = datetime.now(timezone.utc)
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
