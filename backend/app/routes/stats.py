from fastapi import APIRouter, Depends, Response

from app.dependencies import get_stats_service
from app.schemas import StatsOut
from app.services.stats_service import StatsService

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", response_model=StatsOut)
def get_stats(response: Response, service: StatsService = Depends(get_stats_service)) -> StatsOut:
    stats, hit = service.get_stats()
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return stats
