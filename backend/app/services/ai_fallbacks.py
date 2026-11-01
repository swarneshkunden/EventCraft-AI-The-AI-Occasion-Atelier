"""Deterministic, profile-based defaults used when the AI provider is down.

These keep the headline planning features usable during a demo or an outage.
They are clearly labelled estimates, never presented as confirmed prices.
"""

from datetime import date, timedelta

from app.models.models import Event
from app.services.plan_utils import enum_value, parse_iso_date
from app.validators.schemas import (
    AIBudgetCategory,
    AIBudgetSplit,
    AIIdea,
    AIIdeas,
    AITask,
    AITaskList,
    AIVendorQuestions,
)

_ESTIMATE = "Deterministic estimate generated because the AI assistant was unavailable."

# Category name -> share of the total budget. Ordered most-to-least important.
_BUDGET_SHARES: tuple[tuple[str, float], ...] = (
    ("Venue", 0.28),
    ("Catering", 0.32),
    ("Decor & Flowers", 0.12),
    ("Photography", 0.10),
    ("Entertainment", 0.06),
    ("Transport", 0.04),
    ("Misc / Buffer", 0.08),
)

_EVENT_FLAVOUR: dict[str, str] = {
    "wedding": "ceremony",
    "birthday": "birthday party",
    "community": "community gathering",
}


def fallback_budget_split(event: Event) -> AIBudgetSplit:
    """Split the event budget across sensible categories, never exceeding it."""
    total = max(float(event.total_budget or 0), 0.0)
    categories = [
        AIBudgetCategory(
            name=name,
            allocated=round(total * share, 2),
            notes=_ESTIMATE,
        )
        for name, share in _BUDGET_SHARES
    ]
    return AIBudgetSplit(categories=categories)


def _milestone(title: str, days_before: int, event_date: date, priority: int) -> AITask:
    due = event_date - timedelta(days=days_before)
    return AITask(
        title=title,
        description=f"Confirm details for the {title.lower()} milestone.",
        category="planning",
        due_date=max(due, date.today()).isoformat(),
        priority=priority,
        depends_on=[],
    )


def fallback_task_list(event: Event) -> AITaskList:
    """Build a standard reverse-planned milestone list from the event date."""
    target = parse_iso_date(event.event_date) or (date.today() + timedelta(days=180))
    flavour = _EVENT_FLAVOUR.get(str(enum_value(event.event_type)), "event")
    milestones = [
        _milestone(f"Set the {flavour} budget and headcount", 120, target, 1),
        _milestone("Shortlist and book the venue", 100, target, 1),
        _milestone("Confirm catering and menu tasting", 75, target, 2),
        _milestone("Send invitations and track RSVPs", 60, target, 2),
        _milestone("Book photography and entertainment", 45, target, 3),
        _milestone("Finalise decor and flowers", 30, target, 3),
        _milestone("Confirm final guest count with vendors", 14, target, 1),
        _milestone("Share the run sheet with the event team", 3, target, 2),
    ]
    return AITaskList(tasks=milestones)


_VENDOR_CHECKLIST: dict[str, tuple[str, ...]] = {
    "venue": (
        "Confirm capacity for the expected guest count",
        "Check parking, power backup, and accessibility",
        "Ask about setup and teardown windows",
    ),
    "caterer": (
        "Confirm per-plate price and minimum headcount",
        "Ask for a tasting before the final payment",
        "Agree on serving staff, crockery, and cleanup",
    ),
    "photographer": (
        "Review a full recent gallery, not just highlights",
        "Confirm hours covered and overtime rate",
        "Agree on delivery timelines for edited photos",
    ),
    "decorator": (
        "Confirm what is rented versus bought",
        "Ask for the setup schedule and a site walkthrough",
        "Agree on who removes the decor afterwards",
    ),
    "entertainment": (
        "Confirm performance length and breaks",
        "Check sound equipment and power requirements",
        "Agree on the song or act list in advance",
    ),
    "transport": (
        "Confirm vehicle count and seating capacity",
        "Ask about fuel, tolls, and driver allowance",
        "Agree on pickup and drop timings",
    ),
    "other": (
        "Confirm the exact scope of work in writing",
        "Agree on the payment schedule and cancellation terms",
        "Collect a single point of contact for the event day",
    ),
}

_VENDOR_QUESTIONS: dict[str, tuple[str, ...]] = {
    "venue": (
        "Is the quoted price inclusive of taxes and service charges?",
        "What is the cancellation and rescheduling policy?",
        "How many hours of access are included?",
    ),
    "caterer": (
        "How many dishes are included per course?",
        "Can you accommodate dietary restrictions and children?",
        "What is the payment and cancellation policy?",
    ),
    "photographer": (
        "How many edited photos are included?",
        "Who is the backup photographer if you are unavailable?",
        "Do you charge extra for travel or raw files?",
    ),
    "decorator": (
        "What is included in the quoted package?",
        "How much notice do you need for changes?",
        "What happens if an item is unavailable on the day?",
    ),
    "entertainment": (
        "How long is the performance and are breaks included?",
        "Do you provide your own sound and lighting?",
        "What is the cancellation policy?",
    ),
    "transport": (
        "Is the price per vehicle or per trip?",
        "What happens if the event runs late?",
        "Are tolls, parking, and driver meals included?",
    ),
    "other": (
        "What exactly is included in the quoted price?",
        "What is your cancellation and refund policy?",
        "Who is our point of contact on the event day?",
    ),
}


def fallback_vendor_questions(event: Event, vendor_type: str) -> AIVendorQuestions:
    """Return a standard checklist for the vendor type without the provider."""
    key = str(enum_value(vendor_type)).lower()
    checklist = _VENDOR_CHECKLIST.get(key, _VENDOR_CHECKLIST["other"])
    questions = _VENDOR_QUESTIONS.get(key, _VENDOR_QUESTIONS["other"])
    return AIVendorQuestions(checklist=list(checklist), questions=list(questions))


def fallback_ideas(event: Event) -> AIIdeas:
    """Offer a small, budget-aware idea set without calling the provider."""
    flavour = _EVENT_FLAVOUR.get(str(enum_value(event.event_type)), "event")
    return AIIdeas(
        themes=[
            AIIdea(
                name="Warm ivory and gold",
                description=f"A calm, timeless palette for the {flavour}.",
                estimated_cost="Low — reuses existing linens and lighting",
                cheaper_alternative="Ivory paper lanterns instead of floral centrepieces",
            )
        ],
        decor=[
            AIIdea(
                name="Statement entrance",
                description="One focal arrangement at the entrance instead of decor everywhere.",
                estimated_cost="Medium",
                cheaper_alternative="Rental archway dressed with local greenery",
            )
        ],
        menu=[
            AIIdea(
                name="Family-style sharing menu",
                description="Fewer courses served in larger shared platters.",
                estimated_cost="Medium",
                cheaper_alternative="Buffet with two mains and one dessert",
            )
        ],
        activities=[
            AIIdea(
                name="Guest memory wall",
                description="Guests write a note for the hosts instead of a guest book.",
                estimated_cost="Low",
                cheaper_alternative="Reuse card stock and a borrowed instant camera",
            )
        ],
    )
