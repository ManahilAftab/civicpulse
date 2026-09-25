"""create complaints table

Revision ID: 0001
Revises:
Create Date: 2026-09-25
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

category = postgresql.ENUM(
    "water",
    "electricity",
    "sanitation",
    "roads",
    "streetlights",
    "other",
    name="complaint_category",
    create_type=False,
)
priority = postgresql.ENUM("high", "normal", "low", name="complaint_priority", create_type=False)
status = postgresql.ENUM(
    "open", "in_progress", "resolved", "rejected", name="complaint_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (category, priority, status):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "complaints",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("reporter_contact", sa.String(200), nullable=True),
        sa.Column("category", category, nullable=False),
        sa.Column("priority", priority, nullable=False),
        sa.Column("status", status, nullable=False, server_default="open"),
        sa.Column("ai_summary", sa.String(140), nullable=True),
        sa.Column("triaged_by", sa.String(32), nullable=False),
        sa.Column("triage_latency_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("length(text) BETWEEN 10 AND 2000", name="ck_complaints_text_length"),
        sa.CheckConstraint(
            "length(location) BETWEEN 3 AND 200", name="ck_complaints_location_length"
        ),
        sa.CheckConstraint("triage_latency_ms >= 0", name="ck_complaints_latency_nonnegative"),
        sa.CheckConstraint(
            "triaged_by IN ('llm:groq', 'llm:ollama', 'rules', 'rules:fallback', 'simulated')",
            name="ck_complaints_triaged_by",
        ),
    )
    # Dashboard filter: WHERE status = ? AND priority = ? (status-only filters use the prefix)
    op.create_index("ix_complaints_status_priority", "complaints", ["status", "priority"])
    # Dashboard default sort and pagination: ORDER BY created_at DESC LIMIT ? OFFSET ?
    op.create_index("ix_complaints_created_at", "complaints", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_complaints_created_at", table_name="complaints")
    op.drop_index("ix_complaints_status_priority", table_name="complaints")
    op.drop_table("complaints")
    bind = op.get_bind()
    for enum in (status, priority, category):
        enum.drop(bind, checkfirst=True)
