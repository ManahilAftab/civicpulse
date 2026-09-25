"""Complaint business rules: submission (validate -> triage -> persist), lookup,
listing, and status changes through the state machine."""

from uuid import UUID, uuid4

from app.domain import ALLOWED_TRANSITIONS, Category, Priority, Status
from app.errors import ComplaintNotFound, InvalidTransition
from app.models import Complaint
from app.providers.cache import StatsCache
from app.repositories.complaint_repository import ComplaintRepository
from app.schemas import ComplaintCreate, ComplaintOut, ComplaintPage
from app.services.triage_service import TriageService


def ensure_transition(current: Status, target: Status) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(current, target)


class ComplaintService:
    def __init__(
        self, repo: ComplaintRepository, triage: TriageService, stats_cache: StatsCache
    ) -> None:
        self._repo = repo
        self._triage = triage
        self._stats_cache = stats_cache

    def submit(self, data: ComplaintCreate) -> ComplaintOut:
        # The id exists before triage so a fallback WARNING can name the complaint.
        complaint_id = uuid4()
        outcome = self._triage.triage(data.text, data.location, complaint_id=complaint_id)
        complaint = Complaint(
            id=complaint_id,
            text=data.text,
            location=data.location,
            reporter_contact=data.reporter_contact,
            category=outcome.result.category,
            priority=outcome.result.priority,
            status=Status.OPEN,
            ai_summary=outcome.result.summary,
            triaged_by=outcome.triaged_by,
            triage_latency_ms=outcome.latency_ms,
        )
        saved = self._repo.add(complaint)
        self._stats_cache.invalidate()  # after commit, so a reader can't re-cache old counts
        return ComplaintOut.model_validate(saved)

    def get(self, complaint_id: UUID) -> ComplaintOut:
        complaint = self._repo.get(complaint_id)
        if complaint is None:
            raise ComplaintNotFound(complaint_id)
        return ComplaintOut.model_validate(complaint)

    def list(
        self,
        *,
        category: Category | None,
        priority: Priority | None,
        status: Status | None,
        page: int,
        page_size: int,
    ) -> ComplaintPage:
        items, total = self._repo.list(
            category=category, priority=priority, status=status, page=page, page_size=page_size
        )
        return ComplaintPage(
            items=[ComplaintOut.model_validate(c) for c in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    def change_status(self, complaint_id: UUID, target: Status) -> ComplaintOut:
        complaint = self._repo.get_for_update(complaint_id)  # row lock: two operators, one winner
        if complaint is None:
            raise ComplaintNotFound(complaint_id)
        ensure_transition(complaint.status, target)
        updated = self._repo.update_status(complaint, target)
        self._stats_cache.invalidate()
        return ComplaintOut.model_validate(updated)
