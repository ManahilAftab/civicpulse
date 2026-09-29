"""Aggregate statistics, read through the Redis cache."""

from app.domain import Category, Priority, Status
from app.providers.cache import StatsCache
from app.repositories.complaint_repository import ComplaintRepository
from app.schemas import StatsOut


class StatsService:
    def __init__(self, repo: ComplaintRepository, cache: StatsCache) -> None:
        self._repo = repo
        self._cache = cache

    def get_stats(self) -> tuple[StatsOut, bool]:
        """Returns (stats, cache_hit)."""
        cached = self._cache.get()
        if cached is not None:
            return StatsOut.model_validate(cached), True

        by_category = {c: 0 for c in Category} | self._repo.count_by("category")
        by_priority = {p: 0 for p in Priority} | self._repo.count_by("priority")
        by_status = {s: 0 for s in Status} | self._repo.count_by("status")
        stats = StatsOut(
            total=sum(by_status.values()),
            by_category=by_category,
            by_priority=by_priority,
            by_status=by_status,
        )
        self._cache.set(stats.model_dump(mode="json"))
        return stats, False
