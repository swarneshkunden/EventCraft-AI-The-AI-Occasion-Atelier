"""Deterministic, explainable plan-health scoring."""
from datetime import date
from typing import TypedDict

from app.models.models import (
    BudgetCategory,
    Task,
    TaskStatus,
    Vendor,
)
from app.services.plan_utils import enum_value, parse_iso_date


class PlanHealthDeduction(TypedDict):
    key: str
    points: int
    reason: str
    next_step: str


class PlanHealthResult(TypedDict):
    score: int
    label: str
    days_until_event: int | None
    deductions: list[PlanHealthDeduction]
    summary: str


def _add_deduction(
    deductions: list[PlanHealthDeduction],
    key: str,
    points: int,
    reason: str,
    next_step: str,
) -> None:
    """Append a deduction when its score is non-zero."""
    if points > 0:
        deductions.append(
            {
                "key": key,
                "points": points,
                "reason": reason,
                "next_step": next_step,
            }
        )


def _budget_deductions(
    total_budget: float,
    spent: float,
    allocated: float,
) -> list[PlanHealthDeduction]:
    """Describe budget overrun, over-allocation, or spending pressure."""
    deductions: list[PlanHealthDeduction] = []
    if total_budget <= 0:
        return deductions
    if spent > total_budget:
        _add_deduction(
            deductions,
            "budget_overrun",
            25,
            f"Recorded spending exceeds the total budget by {round(spent - total_budget, 2):,.2f}.",
            "Review committed costs before approving new spending.",
        )
    elif allocated > total_budget:
        _add_deduction(
            deductions,
            "budget_overallocated",
            15,
            f"Budget categories allocate {allocated - total_budget:,.2f} more than the event budget.",
            "Rebalance category allocations to fit the total budget.",
        )
    elif spent >= total_budget * 0.9:
        _add_deduction(
            deductions,
            "budget_pressure",
            10,
            "At least 90% of the total budget is already recorded as spent.",
            "Check remaining commitments and protect a contingency buffer.",
        )
    return deductions


def _task_deductions(
    tasks: list[Task],
    incomplete: list[Task],
    overdue: list[Task],
    blocked: list[Task],
    missing_quotes: list[Vendor],
) -> list[PlanHealthDeduction]:
    """Describe task and vendor quote risks in the plan."""
    deductions: list[PlanHealthDeduction] = []
    if overdue:
        _add_deduction(
            deductions,
            "overdue_tasks",
            min(20, len(overdue) * 5),
            f"{len(overdue)} unfinished task(s) have a due date before today.",
            "Review overdue tasks and reset realistic owners and dates.",
        )
    if blocked:
        _add_deduction(
            deductions,
            "blocked_tasks",
            min(15, len(blocked) * 5),
            f"{len(blocked)} task(s) are marked blocked.",
            "Resolve each prerequisite before progressing dependent work.",
        )
    if _has_dependency_cycle(tasks):
        _add_deduction(
            deductions,
            "dependency_cycle",
            15,
            "The task dependencies contain a cycle, so at least one task cannot become ready.",
            "Edit dependencies to create a forward-only sequence.",
        )
    if not tasks:
        _add_deduction(
            deductions,
            "missing_timeline",
            10,
            "No timeline tasks are recorded for this event.",
            "Create a first milestone list to make the plan actionable.",
        )
    if missing_quotes:
        _add_deduction(
            deductions,
            "unverified_quotes",
            min(15, len(missing_quotes) * 5),
            f"{len(missing_quotes)} vendor(s) have no quote on file; prices need verification.",
            "Request written quotes and confirm availability directly with each vendor.",
        )
    return deductions


def _date_deductions(
    event_date: str | None,
    today: date,
    incomplete: list[Task],
) -> tuple[int | None, list[PlanHealthDeduction]]:
    """Describe past dates or deadline pressure and return days remaining."""
    deductions: list[PlanHealthDeduction] = []
    target_date = parse_iso_date(event_date)
    if target_date is None:
        return None, deductions
    days_until = (target_date - today).days
    if days_until < 0:
        _add_deduction(
            deductions,
            "past_event_date",
            15,
            "The event date has passed but the plan is still active.",
            "Confirm the event date or archive the completed plan.",
        )
    elif days_until <= 30 and incomplete:
        points = 10 if days_until <= 7 else 7 if days_until <= 14 else 5
        _add_deduction(
            deductions,
            "tight_deadline",
            points,
            f"The event is {days_until} day(s) away with {len(incomplete)} unfinished task(s).",
            "Prioritize essential tasks and confirm vendor commitments.",
        )
    return days_until, deductions


def _venue_deductions(
    guest_count: int,
    vendors: list[Vendor],
) -> list[PlanHealthDeduction]:
    """Describe venue quotes whose stated capacity is below the guest target."""
    undersized_venues = [
        vendor
        for vendor in vendors
        if enum_value(vendor.vendor_type) == "venue"
        and vendor.guests_covered is not None
        and vendor.guests_covered < guest_count
    ]
    if not undersized_venues:
        return []
    return [
        {
            "key": "venue_capacity",
            "points": 15,
            "reason": (
                f"{len(undersized_venues)} venue quote(s) list capacity below "
                f"the {guest_count}-guest target."
            ),
            "next_step": "Verify room capacity and safe occupancy with the venue before confirming.",
        }
    ]


def _has_dependency_cycle(tasks: list[Task]) -> bool:
    """Detect cycles among task dependencies."""
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
        """Check whether this task reaches an active task in the traversal."""
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
) -> PlanHealthResult:
    today = today or date.today()
    spent = round(sum(float(category.spent or 0) for category in categories), 2)
    allocated = round(sum(float(category.allocated or 0) for category in categories), 2)
    total_budget = round(float(total_budget), 2)
    incomplete = [task for task in tasks if enum_value(task.status) != TaskStatus.completed.value]
    overdue = [
        task for task in incomplete
        if (due := parse_iso_date(task.due_date)) is not None and due < today
    ]
    blocked = [task for task in tasks if enum_value(task.status) == TaskStatus.blocked.value]
    missing_quotes = [vendor for vendor in vendors if vendor.quoted_price is None]
    deductions = _budget_deductions(total_budget, spent, allocated)
    deductions.extend(_task_deductions(tasks, incomplete, overdue, blocked, missing_quotes))
    days_until, date_risks = _date_deductions(event_date, today, incomplete)
    deductions.extend(date_risks)
    deductions.extend(_venue_deductions(guest_count, vendors))

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
