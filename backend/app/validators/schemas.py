"""Pydantic schemas for all API request/response validation."""
import re
from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ── Shared helpers ────────────────────────────────────────────────────────────

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RSVP_STATUSES = {"pending", "confirmed", "declined"}
_VENDOR_TYPES = {"venue", "caterer", "photographer", "decorator", "entertainment", "transport", "other"}
_EVENT_TYPES = {"wedding", "birthday", "community"}


def _validate_date_string(v: str | None) -> str | None:
    if v is None:
        return v
    if not _DATE_RE.match(v):
        raise ValueError("Date must be in YYYY-MM-DD format")
    date.fromisoformat(v)
    return v


class StrictModel(BaseModel):
    model_config = {"extra": "forbid"}


class _OrmBase(StrictModel):
    model_config = {"from_attributes": True, "extra": "forbid"}


# ── Auth ──────────────────────────────────────────────────────────────────────

class SignupRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)
    currency: str = Field(default="INR", max_length=10)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("display_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("Display name cannot be blank")
        return value


class LoginRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class TokenResponse(StrictModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(_OrmBase):
    id: str
    email: str
    display_name: str
    currency: str


# ── Events ────────────────────────────────────────────────────────────────────

class EventProfile(StrictModel):
    """Structured answers from the intake wizard."""
    occasion: str = Field(max_length=200)
    budget: float = Field(gt=0, le=1_000_000_000, allow_inf_nan=False)
    guest_count: int = Field(ge=1, le=100_000)
    event_date: Optional[str] = None
    experience_level: str = Field(default="moderate", pattern="^(premium|moderate|simple)$")
    priorities: list[str] = Field(default_factory=list, max_length=10)
    must_haves: list[str] = Field(default_factory=list, max_length=20)
    atmosphere: str = Field(default="", max_length=500)
    age_groups: list[str] = Field(default_factory=list, max_length=10)
    cultural_preferences: str = Field(default="", max_length=500)
    accessibility_needs: str = Field(default="", max_length=500)
    venue_limits: str = Field(default="", max_length=500)
    location: str = Field(default="", max_length=500)

    @field_validator("event_date", mode="before")
    @classmethod
    def _validate_date(cls, v: str | None) -> str | None:
        value = _validate_date_string(v)
        if value and date.fromisoformat(value) < date.today():
            raise ValueError("Event date cannot be in the past")
        return value

    @field_validator("priorities", "must_haves", "age_groups", mode="before")
    @classmethod
    def _limit_item_length(cls, v: list) -> list:
        for item in v:
            if len(str(item)) > 200:
                raise ValueError("Item too long (max 200 chars)")
        return v


class EventCreateRequest(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    event_type: str = Field(default="wedding")
    profile: EventProfile

    @field_validator("event_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in _EVENT_TYPES:
            raise ValueError(f"event_type must be one of {_EVENT_TYPES}")
        return v


class EventUpdateRequest(StrictModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    event_type: Optional[str] = None
    profile: Optional[EventProfile] = None

    @field_validator("event_type")
    @classmethod
    def _valid_event_type(cls, value: str | None) -> str | None:
        if value is not None and value not in _EVENT_TYPES:
            raise ValueError(f"event_type must be one of {_EVENT_TYPES}")
        return value


class EventResponse(_OrmBase):
    id: str
    name: str
    event_type: str
    profile: dict
    total_budget: float
    event_date: Optional[str]
    guest_count: int
    is_demo: bool
    created_at: Any
    updated_at: Any


# ── Budget ────────────────────────────────────────────────────────────────────

class BudgetCategoryCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    allocated: float = Field(ge=0, le=1_000_000_000, allow_inf_nan=False)
    spent: float = Field(default=0.0, ge=0, le=1_000_000_000, allow_inf_nan=False)
    notes: str = Field(default="", max_length=2000)
    sort_order: int = Field(default=0, ge=0)


class BudgetCategoryUpdate(StrictModel):
    allocated: Optional[float] = Field(default=None, ge=0, le=1_000_000_000, allow_inf_nan=False)
    spent: Optional[float] = Field(default=None, ge=0, le=1_000_000_000, allow_inf_nan=False)
    notes: Optional[str] = Field(default=None, max_length=2000)


class BudgetCategoryResponse(_OrmBase):
    id: str
    name: str
    allocated: float
    spent: float
    notes: str
    sort_order: int


class ScenarioRequest(StrictModel):
    description: str = Field(min_length=1, max_length=1000)


class CrisisRequest(StrictModel):
    description: str = Field(min_length=3, max_length=500)

    @field_validator("description")
    @classmethod
    def _strip_description(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Description must contain at least 3 characters")
        return value


class CrisisIntent(StrictModel):
    kind: Literal[
        "guest_count_change", "date_advanced", "caterer_cancelled", "weather_risk", "general"
    ]
    new_guest_count: int | None = Field(default=None, ge=1, le=100_000)
    days_advanced: int | None = Field(default=None, ge=1, le=365)

    @model_validator(mode="after")
    def _require_intent_details(self) -> "CrisisIntent":
        if self.kind == "guest_count_change" and self.new_guest_count is None:
            raise ValueError("Guest count is required")
        if self.kind == "date_advanced" and self.days_advanced is None:
            raise ValueError("Number of days is required")
        return self


class AcceptCrisisProposalRequest(StrictModel):
    option_id: str = Field(min_length=1, max_length=40)


# ── Tasks ─────────────────────────────────────────────────────────────────────

class TaskCreate(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=2000)
    category: str = Field(default="general", max_length=100)
    due_date: Optional[str] = None
    priority: int = Field(default=5, ge=1, le=10)
    depends_on: list[str] = Field(default_factory=list)

    @field_validator("due_date", mode="before")
    @classmethod
    def _validate_date(cls, v: str | None) -> str | None:
        return _validate_date_string(v)


class TaskUpdate(StrictModel):
    status: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str | None) -> str | None:
        if v is not None and v not in {"pending", "in_progress", "completed", "blocked"}:
            raise ValueError("Invalid task status")
        return v

    @field_validator("due_date", mode="before")
    @classmethod
    def _validate_date(cls, v: str | None) -> str | None:
        return _validate_date_string(v)


class TaskResponse(_OrmBase):
    id: str
    title: str
    description: str
    status: str
    due_date: Optional[str]
    depends_on: list
    priority: int
    category: str
    completed_at: Any


# ── Vendors ───────────────────────────────────────────────────────────────────

class VendorCreate(StrictModel):
    vendor_type: str
    name: str = Field(min_length=1, max_length=200)
    contact: str = Field(default="", max_length=200)
    quoted_price: Optional[float] = Field(default=None, ge=0, le=1_000_000_000, allow_inf_nan=False)
    guests_covered: Optional[int] = Field(default=None, ge=0, le=100_000)
    inclusions: str = Field(default="", max_length=2000)
    extra_charges: str = Field(default="", max_length=2000)
    open_questions: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=2000)

    @field_validator("vendor_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in _VENDOR_TYPES:
            raise ValueError(f"vendor_type must be one of {_VENDOR_TYPES}")
        return v


class VendorUpdate(StrictModel):
    quoted_price: Optional[float] = Field(default=None, ge=0, le=1_000_000_000, allow_inf_nan=False)
    guests_covered: Optional[int] = Field(default=None, ge=0, le=100_000)
    inclusions: Optional[str] = Field(default=None, max_length=2000)
    extra_charges: Optional[str] = Field(default=None, max_length=2000)
    open_questions: Optional[str] = Field(default=None, max_length=2000)
    notes: Optional[str] = Field(default=None, max_length=2000)
    is_selected: Optional[bool] = None


class VendorResponse(_OrmBase):
    id: str
    vendor_type: str
    name: str
    contact: str
    quoted_price: Optional[float]
    guests_covered: Optional[int]
    inclusions: str
    extra_charges: str
    open_questions: str
    notes: str
    is_selected: bool
    ai_checklist: list
    ai_questions: list


# ── Guests ────────────────────────────────────────────────────────────────────

class GuestCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=30)
    rsvp_status: str = Field(default="pending")
    dietary_needs: str = Field(default="", max_length=200)
    accessibility_needs: str = Field(default="", max_length=200)

    @field_validator("rsvp_status")
    @classmethod
    def _valid_rsvp(cls, v: str) -> str:
        if v not in _RSVP_STATUSES:
            raise ValueError(f"rsvp_status must be one of {_RSVP_STATUSES}")
        return v

    @field_validator("email", mode="before")
    @classmethod
    def _validate_email_format(cls, v: str) -> str:
        if v and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email format")
        return v


class GuestUpdate(StrictModel):
    rsvp_status: Optional[str] = None
    dietary_needs: Optional[str] = Field(default=None, max_length=200)
    accessibility_needs: Optional[str] = Field(default=None, max_length=200)

    @field_validator("rsvp_status")
    @classmethod
    def _valid_rsvp(cls, v: str | None) -> str | None:
        if v is not None and v not in _RSVP_STATUSES:
            raise ValueError(f"rsvp_status must be one of {_RSVP_STATUSES}")
        return v


class GuestResponse(_OrmBase):
    id: str
    name: str
    email: str
    phone: str
    rsvp_status: str
    dietary_needs: str
    accessibility_needs: str


class GuestListResponse(StrictModel):
    guests: list[GuestResponse]
    total: int
    page: int
    page_size: int


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatMessageRequest(StrictModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatMessageResponse(_OrmBase):
    id: str
    role: str
    content: str
    created_at: Any


# ── AI structured output schemas (validated before saving) ────────────────────

class AIBudgetCategory(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    allocated: float = Field(ge=0, le=1_000_000_000, allow_inf_nan=False)
    notes: str = Field(default="", max_length=2000)


class AIBudgetSplit(StrictModel):
    """Expected JSON shape when AI proposes a budget split."""
    categories: list[AIBudgetCategory] = Field(min_length=1, max_length=20)


class AITask(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=2000)
    category: str = Field(default="general", max_length=100)
    due_date: str | None = None
    priority: int = Field(default=5, ge=1, le=10)
    depends_on: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("due_date")
    @classmethod
    def _valid_due_date(cls, value: str | None) -> str | None:
        return _validate_date_string(value)


class AITaskList(StrictModel):
    """Expected JSON shape when AI generates tasks."""
    tasks: list[AITask] = Field(min_length=1, max_length=30)


class AIReplanBudgetChange(StrictModel):
    category_name: str = Field(min_length=1, max_length=100)
    old_allocated: float = Field(ge=0, le=1_000_000_000, allow_inf_nan=False)
    new_allocated: float = Field(ge=0, le=1_000_000_000, allow_inf_nan=False)
    reason: str = Field(max_length=1000)


class AIReplanTaskChange(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    old_due_date: str | None = None
    new_due_date: str | None = None
    new_status: str | None = Field(default=None, pattern="^(pending|in_progress|completed|blocked)$")
    reason: str = Field(max_length=1000)

    @field_validator("old_due_date", "new_due_date")
    @classmethod
    def _valid_dates(cls, value: str | None) -> str | None:
        return _validate_date_string(value)


class AIReplanDiff(StrictModel):
    """Expected JSON shape when AI re-plans after a change."""
    summary: str = Field(min_length=1, max_length=2000)
    budget_changes: list[AIReplanBudgetChange] = Field(max_length=20)
    task_changes: list[AIReplanTaskChange] = Field(max_length=30)
    trade_offs: list[str] = Field(max_length=10)

    @field_validator("trade_offs")
    @classmethod
    def _limit_tradeoffs(cls, values: list[str]) -> list[str]:
        if any(len(value) > 500 for value in values):
            raise ValueError("Trade-offs may not exceed 500 characters")
        return values


class AIVendorQuestions(StrictModel):
    checklist: list[str] = Field(min_length=1, max_length=20)
    questions: list[str] = Field(min_length=1, max_length=20)

    @field_validator("checklist", "questions")
    @classmethod
    def _limit_text_items(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 500 for value in values):
            raise ValueError("AI text items must be 1-500 characters")
        return values


class AIIdea(StrictModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(min_length=1, max_length=500)
    estimated_cost: str = Field(min_length=1, max_length=200)
    cheaper_alternative: str | None = Field(default=None, max_length=500)


class AIIdeas(StrictModel):
    themes: list[AIIdea] = Field(max_length=10)
    decor: list[AIIdea] = Field(max_length=10)
    menu: list[AIIdea] = Field(max_length=10)
    activities: list[AIIdea] = Field(max_length=10)
