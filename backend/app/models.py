"""SQLAlchemy ORM model. The schema itself is owned by Alembic migrations —
this file must stay in sync with alembic/versions/, but never creates tables."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain import Category, Priority, Status


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _enum(enum_cls: type, name: str) -> SAEnum:
    # Store the lowercase values ("in_progress"), not the Python member names.
    return SAEnum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class Base(DeclarativeBase):
    pass


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    reporter_contact: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[Category] = mapped_column(_enum(Category, "complaint_category"))
    priority: Mapped[Priority] = mapped_column(_enum(Priority, "complaint_priority"))
    status: Mapped[Status] = mapped_column(
        _enum(Status, "complaint_status"), default=Status.OPEN, server_default="open"
    )
    ai_summary: Mapped[str | None] = mapped_column(String(140), nullable=True)
    triaged_by: Mapped[str] = mapped_column(String(32), nullable=False)
    triage_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )

    __table_args__ = (
        # Enforced in the database as well as in the API layer.
        CheckConstraint("length(text) BETWEEN 10 AND 2000", name="ck_complaints_text_length"),
        CheckConstraint("length(location) BETWEEN 3 AND 200", name="ck_complaints_location_length"),
        CheckConstraint("triage_latency_ms >= 0", name="ck_complaints_latency_nonnegative"),
        CheckConstraint(
            "triaged_by IN ('llm:groq', 'llm:ollama', 'rules', 'rules:fallback', 'simulated')",
            name="ck_complaints_triaged_by",
        ),
        # Serves the dashboard filter: WHERE status = ? AND priority = ?
        Index("ix_complaints_status_priority", "status", "priority"),
        # Serves the default dashboard sort: ORDER BY created_at DESC LIMIT/OFFSET
        Index("ix_complaints_created_at", "created_at"),
    )
