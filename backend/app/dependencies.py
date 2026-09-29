"""FastAPI dependency wiring. Routes receive services — never a Session."""

from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.container import Container
from app.errors import RateLimitExceeded
from app.providers.cache import ping as redis_ping
from app.repositories.complaint_repository import ComplaintRepository
from app.services.complaint_service import ComplaintService
from app.services.health_service import ReadinessService
from app.services.stats_service import StatsService


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_session(c: Container = Depends(get_container)) -> Iterator[Session]:
    session = c.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_repository(session: Session = Depends(get_session)) -> ComplaintRepository:
    return ComplaintRepository(session)


def get_complaint_service(
    repo: ComplaintRepository = Depends(get_repository),
    c: Container = Depends(get_container),
) -> ComplaintService:
    return ComplaintService(repo, c.triage_service, c.stats_cache)


def get_stats_service(
    repo: ComplaintRepository = Depends(get_repository),
    c: Container = Depends(get_container),
) -> StatsService:
    return StatsService(repo, c.stats_cache)


def get_readiness_service(c: Container = Depends(get_container)) -> ReadinessService:
    def database_ok() -> bool:
        with c.session_factory() as session:
            return ComplaintRepository(session).ping()

    return ReadinessService({"database": database_ok, "redis": lambda: redis_ping(c.redis)})


def client_ip(request: Request, c: Container) -> str:
    if c.settings.trust_proxy_headers:
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, c: Container = Depends(get_container)) -> None:
    decision = c.rate_limiter.hit(client_ip(request, c))
    if not decision.allowed:
        raise RateLimitExceeded(decision.retry_after_s)
