"""All SQL lives here, and nowhere else."""

from typing import Literal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.domain import Category, Priority, Status
from app.models import Complaint

GroupColumn = Literal["category", "priority", "status"]


class ComplaintRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def ping(self) -> bool:
        self._s.execute(text("SELECT 1"))
        return True

    def add(self, complaint: Complaint) -> Complaint:
        self._s.add(complaint)
        self._s.commit()
        self._s.refresh(complaint)
        return complaint

    def add_if_absent(self, complaint: Complaint) -> bool:
        """Used by the seed command: insert only if the id is new. Returns True if inserted."""
        if self._s.get(Complaint, complaint.id) is not None:
            return False
        self._s.add(complaint)
        self._s.commit()
        return True

    def get(self, complaint_id: UUID) -> Complaint | None:
        return self._s.get(Complaint, complaint_id)

    def get_for_update(self, complaint_id: UUID) -> Complaint | None:
        stmt = select(Complaint).where(Complaint.id == complaint_id).with_for_update()
        return self._s.scalars(stmt).first()

    def update_status(self, complaint: Complaint, status: Status) -> Complaint:
        complaint.status = status
        self._s.commit()
        self._s.refresh(complaint)
        return complaint

    def list(
        self,
        *,
        category: Category | None,
        priority: Priority | None,
        status: Status | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Complaint], int]:
        filters = []
        if category is not None:
            filters.append(Complaint.category == category)
        if priority is not None:
            filters.append(Complaint.priority == priority)
        if status is not None:
            filters.append(Complaint.status == status)

        total = self._s.scalar(select(func.count()).select_from(Complaint).where(*filters)) or 0
        rows = self._s.scalars(
            select(Complaint)
            .where(*filters)
            .order_by(Complaint.created_at.desc(), Complaint.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total

    def count_by(self, column: GroupColumn) -> dict:
        col = getattr(Complaint, column)
        rows = self._s.execute(select(col, func.count()).group_by(col)).all()
        return {key: count for key, count in rows}
