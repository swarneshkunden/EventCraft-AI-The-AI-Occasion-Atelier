"""SQLAlchemy ORM models for the Event Planner application."""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ── Enumerations ──────────────────────────────────────────────────────────────


class EventType(str, enum.Enum):
    wedding = "wedding"
    birthday = "birthday"
    community = "community"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    blocked = "blocked"


class VendorType(str, enum.Enum):
    venue = "venue"
    caterer = "caterer"
    photographer = "photographer"
    decorator = "decorator"
    entertainment = "entertainment"
    transport = "transport"
    other = "other"


# ── Models ────────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    events: Mapped[list["Event"]] = relationship(
        "Event", back_populates="owner", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )


Index("uq_users_email_lower", func.lower(User.email), unique=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_owner_created_at", "owner_id", "created_at"),)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(
        Enum(EventType), nullable=False, default=EventType.wedding
    )
    # Event profile stored as JSON for flexibility
    profile: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict
    )
    total_budget: Mapped[float] = mapped_column(
        Numeric(14, 2, asdecimal=False), nullable=False, default=0.0
    )
    event_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    guest_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_cache: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    owner: Mapped["User"] = relationship("User", back_populates="events")
    budget_categories: Mapped[list["BudgetCategory"]] = relationship(
        "BudgetCategory", back_populates="event", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="event", cascade="all, delete-orphan"
    )
    vendors: Mapped[list["Vendor"]] = relationship(
        "Vendor", back_populates="event", cascade="all, delete-orphan"
    )
    guests: Mapped[list["Guest"]] = relationship(
        "Guest", back_populates="event", cascade="all, delete-orphan"
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="event", cascade="all, delete-orphan"
    )


class BudgetCategory(Base):
    __tablename__ = "budget_categories"
    __table_args__ = (Index("ix_budget_categories_event_sort", "event_id", "sort_order"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    allocated: Mapped[float] = mapped_column(
        Numeric(14, 2, asdecimal=False), nullable=False, default=0.0
    )
    spent: Mapped[float] = mapped_column(
        Numeric(14, 2, asdecimal=False), nullable=False, default=0.0
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    event: Mapped["Event"] = relationship("Event", back_populates="budget_categories")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_event_priority_due_date", "event_id", "priority", "due_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        Enum(TaskStatus), nullable=False, default=TaskStatus.pending
    )
    due_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Dependency IDs stored as JSON array of task IDs
    depends_on: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    event: Mapped["Event"] = relationship("Event", back_populates="tasks")


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_type: Mapped[str] = mapped_column(Enum(VendorType), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    quoted_price: Mapped[float | None] = mapped_column(
        Numeric(14, 2, asdecimal=False), nullable=True
    )
    guests_covered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inclusions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extra_charges: Mapped[str] = mapped_column(Text, nullable=False, default="")
    open_questions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # AI-generated checklist and questions stored as JSON
    ai_checklist: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list
    )
    ai_questions: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    event: Mapped["Event"] = relationship("Event", back_populates="vendors")


class Guest(Base):
    __tablename__ = "guests"
    __table_args__ = (Index("ix_guests_event_name", "event_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    rsvp_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending | confirmed | declined
    dietary_needs: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    accessibility_needs: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    event: Mapped["Event"] = relationship("Event", back_populates="guests")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_event_created_at", "event_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    event: Mapped["Event"] = relationship("Event", back_populates="chat_messages")


class PlanChangeProposal(Base):
    __tablename__ = "plan_change_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    options: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    baseline: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    selected_option_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    added_task_ids: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list
    )
    after_state: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlanChangeAudit(Base):
    __tablename__ = "plan_change_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    proposal_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("plan_change_proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_fields: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
