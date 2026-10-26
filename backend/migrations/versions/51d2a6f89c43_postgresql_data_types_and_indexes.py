"""Use PostgreSQL-native structured and money types with lookup indexes.

Revision ID: 51d2a6f89c43
Revises: 0f5a78aeb321
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "51d2a6f89c43"
down_revision: Union[str, None] = "0f5a78aeb321"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_MONEY_COLUMNS = {
    "events": (("total_budget", False),),
    "budget_categories": (("allocated", False), ("spent", False)),
    "vendors": (("quoted_price", True),),
}
_JSON_COLUMNS = {
    "events": ("profile", "ai_cache"),
    "tasks": ("depends_on",),
    "vendors": ("ai_checklist", "ai_questions"),
    "plan_change_proposals": ("options", "baseline", "added_task_ids", "after_state"),
    "plan_change_audits": ("changed_fields",),
}
_INDEXES = (
    ("ix_events_owner_created_at", "events", ["owner_id", "created_at"]),
    ("ix_budget_categories_event_sort", "budget_categories", ["event_id", "sort_order"]),
    ("ix_tasks_event_priority_due_date", "tasks", ["event_id", "priority", "due_date"]),
    ("ix_guests_event_name", "guests", ["event_id", "name"]),
    ("ix_chat_messages_event_created_at", "chat_messages", ["event_id", "created_at"]),
)


def _alter_money_columns(to_numeric: bool) -> None:
    connection = op.get_bind()
    is_postgresql = connection.dialect.name == "postgresql"
    for table, columns in _MONEY_COLUMNS.items():
        for column, nullable in columns:
            if is_postgresql:
                source_type = sa.Float() if to_numeric else sa.Numeric(14, 2, asdecimal=False)
                target_type = sa.Numeric(14, 2, asdecimal=False) if to_numeric else sa.Float()
                cast_type = "numeric(14,2)" if to_numeric else "double precision"
                op.alter_column(
                    table,
                    column,
                    existing_type=source_type,
                    type_=target_type,
                    existing_nullable=nullable,
                    postgresql_using=f'"{column}"::{cast_type}',
                )
            else:
                source_type = sa.Float() if to_numeric else sa.Numeric(14, 2, asdecimal=False)
                target_type = sa.Numeric(14, 2, asdecimal=False) if to_numeric else sa.Float()
                with op.batch_alter_table(table) as batch_op:
                    batch_op.alter_column(
                        column,
                        existing_type=source_type,
                        type_=target_type,
                        existing_nullable=nullable,
                    )


def _alter_json_columns(to_jsonb: bool) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    for table, columns in _JSON_COLUMNS.items():
        for column in columns:
            op.alter_column(
                table,
                column,
                existing_type=postgresql.JSONB() if not to_jsonb else sa.JSON(),
                type_=postgresql.JSONB() if to_jsonb else sa.JSON(),
                existing_nullable=column == "after_state",
                postgresql_using=(
                    f'"{column}"::jsonb' if to_jsonb else f'"{column}"::json'
                ),
            )


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.add_column("events", sa.Column("version", sa.Integer(), nullable=True))
        op.execute("UPDATE events SET version = 1 WHERE version IS NULL")
        with op.batch_alter_table("events") as batch_op:
            batch_op.alter_column("version", nullable=False)
    else:
        op.add_column(
            "events",
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
        op.alter_column("events", "version", server_default=None)

    _alter_money_columns(to_numeric=True)
    _alter_json_columns(to_jsonb=True)

    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_index(
        "uq_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    _alter_json_columns(to_jsonb=False)
    _alter_money_columns(to_numeric=False)
    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_column("version")
