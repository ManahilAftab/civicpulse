"""Pydantic models for the HTTP contract. FastAPI generates the OpenAPI schema
from these, and the frontend's typed client is generated from that schema."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain import Category, Priority, Status


class ComplaintCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=10, max_length=2000)
    location: str = Field(min_length=3, max_length=200)
    reporter_contact: str | None = Field(default=None, max_length=200)


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    text: str
    location: str
    reporter_contact: str | None
    category: Category
    priority: Priority
    status: Status
    ai_summary: str | None
    triaged_by: str
    triage_latency_ms: int
    created_at: datetime
    updated_at: datetime


class ComplaintPage(BaseModel):
    items: list[ComplaintOut]
    total: int
    page: int
    page_size: int


class StatusUpdate(BaseModel):
    status: Status


class StatsOut(BaseModel):
    total: int
    by_category: dict[Category, int]
    by_priority: dict[Priority, int]
    by_status: dict[Status, int]


class TriageOutcomeOut(BaseModel):
    at: datetime
    provider: str
    triaged_by: str
    latency_ms: int
    fallback: bool
    cache_hit: bool
    error_class: str | None = None


class TriageCacheStats(BaseModel):
    hits: int
    misses: int
    hit_rate: float


class ProvidersOut(BaseModel):
    active_provider: str
    fallback_provider: str
    recent: list[TriageOutcomeOut]
    cache: TriageCacheStats


class FieldError(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    detail: str
    errors: list[FieldError] | None = None


class HealthOut(BaseModel):
    status: str


class ReadyOut(BaseModel):
    status: str
    failed: list[str] = []
