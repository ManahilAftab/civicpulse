from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.dependencies import get_readiness_service
from app.schemas import HealthOut, ReadyOut
from app.services.health_service import ReadinessService

router = APIRouter(tags=["ops"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    # Liveness: the process is alive and serving. Touches no dependency, on purpose —
    # a failing liveness probe restarts the pod, and restarting won't fix Postgres.
    return HealthOut(status="ok")


@router.get("/ready", response_model=ReadyOut, responses={503: {"model": ReadyOut}})
def ready(
    response: Response, service: ReadinessService = Depends(get_readiness_service)
) -> ReadyOut:
    failed = service.failed_dependencies()
    if failed:
        response.status_code = 503
        return ReadyOut(status="unavailable", failed=failed)
    return ReadyOut(status="ok")


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
