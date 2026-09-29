"""Domain errors. Services raise these; main.py maps them to HTTP responses."""

from uuid import UUID

from app.domain import Status


class DomainError(Exception):
    """Base class for errors the API translates into a 4xx response."""


class ComplaintNotFound(DomainError):
    def __init__(self, complaint_id: UUID) -> None:
        super().__init__(f"Complaint {complaint_id} not found")
        self.complaint_id = complaint_id


class InvalidTransition(DomainError):
    def __init__(self, current: Status, target: Status) -> None:
        super().__init__(f"Invalid status transition: {current.value} -> {target.value}")
        self.current = current
        self.target = target


class RateLimitExceeded(DomainError):
    def __init__(self, retry_after_s: int) -> None:
        super().__init__("Rate limit exceeded. Please try again later.")
        self.retry_after_s = retry_after_s
