"""
Demo event seeder – creates a sample Wedding event for evaluators.
Budget: INR 8,00,000 | Guests: 200 | Event: 4 months from today
"""
import json
import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.models import BudgetCategory, ChatMessage, Event, Guest, Task, Vendor
from app.services.auth_service import hash_password
from app.models.models import User

log = logging.getLogger(__name__)

_DEMO_EMAIL = "demo@eventplanner.example"
_DEMO_PASSWORD = "Demo@1234"  # displayed on UI; not a secret


def _event_date() -> str:
    return (date.today() + timedelta(days=120)).isoformat()


def seed_demo_event(db: Session) -> Event:
    """
    Idempotent: skips if demo event already exists.
    Returns the demo event.
    """
    existing = db.query(Event).filter(Event.is_demo == True).first()
    if existing:
        return existing

    # Create or fetch demo user
    user = db.query(User).filter(User.email == _DEMO_EMAIL).first()
    if not user:
        user = User(
            email=_DEMO_EMAIL,
            hashed_password=hash_password(_DEMO_PASSWORD),
            display_name="Demo User",
            currency="INR",
        )
        db.add(user)
        db.flush()

    ev_date = _event_date()

    profile = {
        "occasion": "Wedding celebration",
        "budget": 800000,
        "guest_count": 200,
        "event_date": ev_date,
        "experience_level": "moderate",
        "priorities": ["catering", "photography"],
        "must_haves": ["Live music", "Vegetarian menu", "Outdoor ceremony"],
        "atmosphere": "Warm, family-oriented, with traditional elements",
        "age_groups": ["children", "adults", "elders"],
        "cultural_preferences": "North Indian traditions, some modern touches",
        "accessibility_needs": "Wheelchair access required for 3 guests",
        "venue_limits": "Maximum 250 capacity indoor hall preferred",
    }

    event = Event(
        owner_id=user.id,
        name="Priya & Arjun's Wedding",
        event_type="wedding",
        profile=profile,
        total_budget=800000,
        event_date=ev_date,
        guest_count=200,
        is_demo=True,
    )
    db.add(event)
    db.flush()

    # Budget categories
    categories = [
        BudgetCategory(event_id=event.id, name="Venue", allocated=180000, spent=0, sort_order=0,
                       notes="Estimated (assumption), not a confirmed price."),
        BudgetCategory(event_id=event.id, name="Catering", allocated=240000, spent=0, sort_order=1,
                       notes="Estimated (assumption), not a confirmed price. ₹1,200/person × 200 guests."),
        BudgetCategory(event_id=event.id, name="Photography & Video", allocated=80000, spent=0, sort_order=2,
                       notes="Estimated (assumption), not a confirmed price."),
        BudgetCategory(event_id=event.id, name="Decor & Flowers", allocated=100000, spent=0, sort_order=3,
                       notes="Estimated (assumption), not a confirmed price."),
        BudgetCategory(event_id=event.id, name="Entertainment & Music", allocated=60000, spent=0, sort_order=4,
                       notes="Estimated (assumption), not a confirmed price."),
        BudgetCategory(event_id=event.id, name="Invitations & Stationery", allocated=15000, spent=0, sort_order=5,
                       notes="Estimated (assumption), not a confirmed price."),
        BudgetCategory(event_id=event.id, name="Attire & Grooming", allocated=60000, spent=0, sort_order=6,
                       notes="Estimated (assumption), not a confirmed price."),
        BudgetCategory(event_id=event.id, name="Logistics & Transport", allocated=25000, spent=0, sort_order=7,
                       notes="Estimated (assumption), not a confirmed price."),
        BudgetCategory(event_id=event.id, name="Miscellaneous Buffer", allocated=40000, spent=0, sort_order=8,
                       notes="5% buffer for unexpected costs."),
    ]
    for cat in categories:
        db.add(cat)
    db.flush()

    # Sample tasks
    today = date.today()

    def days_before(n: int) -> str:
        return (date.fromisoformat(ev_date) - timedelta(days=n)).isoformat()

    tasks_data = [
        ("Finalise venue and sign contract", "venue", days_before(100), 1, []),
        ("Confirm catering headcount and menu", "catering", days_before(90), 2, ["Finalise venue and sign contract"]),
        ("Book photographer and videographer", "photography", days_before(90), 2, ["Finalise venue and sign contract"]),
        ("Send save-the-date messages", "guest_management", days_before(90), 3, ["Finalise venue and sign contract"]),
        ("Design and order invitations", "stationery", days_before(75), 4, ["Send save-the-date messages"]),
        ("Confirm entertainment / live music", "entertainment", days_before(75), 3, ["Finalise venue and sign contract"]),
        ("Send formal invitations", "guest_management", days_before(60), 4, ["Design and order invitations"]),
        ("Finalize decor plan with decorator", "decor", days_before(60), 3, ["Finalise venue and sign contract"]),
        ("Collect RSVP responses", "guest_management", days_before(30), 5, ["Send formal invitations"]),
        ("Confirm final headcount with caterer", "catering", days_before(21), 2, ["Collect RSVP responses"]),
        ("Arrange transport for guests", "logistics", days_before(21), 4, ["Confirm final headcount with caterer"]),
        ("Coordinate with all vendors – final briefing", "logistics", days_before(7), 1, []),
        ("Prepare day-of timeline sheet", "logistics", days_before(3), 2, ["Coordinate with all vendors – final briefing"]),
    ]

    for title, category, due_date, priority, depends_on in tasks_data:
        t = Task(
            event_id=event.id,
            title=title,
            category=category,
            due_date=due_date,
            priority=priority,
            depends_on=depends_on,
        )
        db.add(t)
    db.flush()

    # Sample vendors
    vendors_data = [
        {
            "vendor_type": "venue",
            "name": "Green Garden Banquets",
            "contact": "+91 98765 00001",
            "quoted_price": None,
            "notes": "Needs verification – price not confirmed",
            "ai_checklist": [
                "Confirm availability on event date (Needs verification)",
                "Check maximum capacity (verify it fits 200 guests)",
                "Verify parking facilities",
                "Confirm wheelchair accessibility",
            ],
            "ai_questions": [
                "What is the rental cost for a full-day booking for 200 guests?",
                "Is outside catering allowed?",
                "What is the cancellation / refund policy?",
            ],
        },
        {
            "vendor_type": "caterer",
            "name": "Annapurna Caterers",
            "contact": "+91 98765 00002",
            "quoted_price": None,
            "notes": "Needs verification – price not confirmed",
            "ai_checklist": [
                "Confirm per-plate cost (Needs verification)",
                "Verify vegetarian menu options are available",
                "Check if they handle setup and cleanup",
                "Confirm FSSAI license",
            ],
            "ai_questions": [
                "What is the per-plate cost for a vegetarian wedding menu for 200 guests?",
                "Can you accommodate guests with dietary restrictions?",
                "Do you provide serving staff?",
            ],
        },
    ]

    for vd in vendors_data:
        v = Vendor(event_id=event.id, **{k: vd[k] for k in vd if k not in ("ai_checklist", "ai_questions")})
        v.ai_checklist = vd["ai_checklist"]
        v.ai_questions = vd["ai_questions"]
        db.add(v)

    # Sample guests
    sample_guests = [
        {"name": "Ravi Sharma", "email": "ravi@example.com", "rsvp_status": "confirmed"},
        {"name": "Sunita Verma", "email": "sunita@example.com", "rsvp_status": "pending"},
        {"name": "Ankit Patel", "rsvp_status": "declined"},
    ]
    for g in sample_guests:
        db.add(Guest(event_id=event.id, **g))

    # Welcome chat message
    db.add(ChatMessage(
        event_id=event.id,
        role="assistant",
        content=(
            "👋 Welcome to the demo event — **Priya & Arjun's Wedding**!\n\n"
            "This is a pre-filled sample with budget categories, a task timeline, "
            "and vendor entries so you can explore all features.\n\n"
            "Try asking me: *\"What should we focus on this week?\"* or "
            "*\"What happens if we reduce the guest count to 150?\"*"
        ),
    ))

    db.commit()
    log.info("Demo event seeded (event_id=%s)", event.id)
    return event
