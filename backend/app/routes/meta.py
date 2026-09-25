from fastapi import APIRouter, Depends

from app.container import Container
from app.dependencies import get_container
from app.schemas import ProvidersOut, TriageCacheStats, TriageOutcomeOut

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/providers", response_model=ProvidersOut)
def providers(c: Container = Depends(get_container)) -> ProvidersOut:
    hits, misses = c.triage_recorder.cache_counts()
    total = hits + misses
    return ProvidersOut(
        active_provider=c.triage_service.primary.name,
        fallback_provider=c.triage_service.fallback.name,
        recent=[TriageOutcomeOut.model_validate(o) for o in c.triage_recorder.recent()],
        cache=TriageCacheStats(
            hits=hits, misses=misses, hit_rate=round(hits / total, 3) if total else 0.0
        ),
    )
