"""HTTP only: parse, validate, serialise, status codes. No business rules, no SQL."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import enforce_rate_limit, get_complaint_service
from app.domain import Category, Priority, Status
from app.schemas import ComplaintCreate, ComplaintOut, ComplaintPage, ErrorResponse, StatusUpdate
from app.services.complaint_service import ComplaintService

router = APIRouter(prefix="/api/complaints", tags=["complaints"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ComplaintOut,
    responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    dependencies=[Depends(enforce_rate_limit)],
)
def create_complaint(
    body: ComplaintCreate, service: ComplaintService = Depends(get_complaint_service)
) -> ComplaintOut:
    return service.submit(body)


@router.get(
    "/{complaint_id}", response_model=ComplaintOut, responses={404: {"model": ErrorResponse}}
)
def get_complaint(
    complaint_id: UUID, service: ComplaintService = Depends(get_complaint_service)
) -> ComplaintOut:
    return service.get(complaint_id)


@router.get("", response_model=ComplaintPage, responses={400: {"model": ErrorResponse}})
def list_complaints(
    category: Category | None = None,
    priority: Priority | None = None,
    status_: Status | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintPage:
    return service.list(
        category=category, priority=priority, status=status_, page=page, page_size=page_size
    )


@router.patch(
    "/{complaint_id}/status",
    response_model=ComplaintOut,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def update_status(
    complaint_id: UUID,
    body: StatusUpdate,
    service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintOut:
    return service.change_status(complaint_id, body.status)
