"""Deterministic crisis response-option construction."""
from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException

from app.models.models import BudgetCategory, Event, Task, TaskStatus, Vendor
from app.services.plan_utils import enum_value, parse_iso_date
from app.validators.schemas import CrisisIntent


def _deadline(event: Event, days_before: int) -> str:
    target = parse_iso_date(event.event_date)
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
) -> list[dict[str, Any]]:
    """Build deterministic proposal options appropriate to the crisis intent."""
    if intent.kind == "guest_count_change":
        return _guest_count_options(event, intent, categories)
    if intent.kind == "date_advanced":
        return _date_advanced_options(event, intent, tasks)
    if intent.kind == "caterer_cancelled":
        return _caterer_cancelled_options(event, vendors)
    if intent.kind == "weather_risk":
        return _weather_options(event)
    return _general_options(event)


def _guest_count_options(
    event: Event,
    intent: CrisisIntent,
    categories: list[BudgetCategory],
) -> list[dict[str, Any]]:
    """Create alternatives for a changed guest count."""
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


def _date_advanced_options(
    event: Event,
    intent: CrisisIntent,
    tasks: list[Task],
) -> list[dict[str, Any]]:
    """Create alternatives for an earlier event date."""
    today = date.today()
    open_tasks = [task for task in tasks if enum_value(task.status) != TaskStatus.completed.value]
    old_date = parse_iso_date(event.event_date)

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
        due = parse_iso_date(task.due_date)
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


def _caterer_cancelled_options(
    event: Event,
    vendors: list[Vendor],
) -> list[dict[str, Any]]:
    """Create alternatives after a caterer cancels."""
    caterers = [vendor for vendor in vendors if enum_value(vendor.vendor_type) == "caterer"]

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


def _weather_options(event: Event) -> list[dict[str, Any]]:
    """Create review steps for weather-related disruption."""
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


def _general_options(event: Event) -> list[dict[str, Any]]:
    """Create non-destructive review options for an unfamiliar disruption."""
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
