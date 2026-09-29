"""Idempotent seed: `python -m app.seed`.

Each seed row gets a deterministic UUID (uuid5 of its seed key), so running the
command twice finds the rows already present and inserts nothing. Seeds are
triaged with RuleBasedTriage: no API quota spent, identical results every time.
"""

import logging
import uuid
from contextlib import suppress

import redis

from app.config import get_settings
from app.db import build_engine, build_session_factory
from app.domain import Status, TriagedBy
from app.logging_config import configure_logging
from app.models import Complaint
from app.providers.cache import StatsCache
from app.providers.triage.rules import RuleBasedTriage
from app.repositories.complaint_repository import ComplaintRepository
from app.seed_data import SEED_COMPLAINTS

SEED_NAMESPACE = uuid.UUID("6f1c2a52-3b1e-4f0e-9d7a-c1c1c0de5eed")
log = logging.getLogger("civicpulse.seed")


def seed_id(key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, key)


def run_seed(repo: ComplaintRepository) -> int:
    """Insert missing seed complaints. Returns how many rows were inserted."""
    rules = RuleBasedTriage()
    inserted = 0
    for key, text, location, contact, status in SEED_COMPLAINTS:
        result = rules.triage(text, location)
        complaint = Complaint(
            id=seed_id(key),
            text=text,
            location=location,
            reporter_contact=contact,
            category=result.category,
            priority=result.priority,
            status=Status(status),
            ai_summary=result.summary,
            triaged_by=TriagedBy.RULES.value,
            triage_latency_ms=0,
        )
        if repo.add_if_absent(complaint):
            inserted += 1
    return inserted


def main() -> None:  # pragma: no cover — exercised by the Compose integration job
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings.database_url)
    with build_session_factory(engine)() as session:
        inserted = run_seed(ComplaintRepository(session))
    with suppress(redis.RedisError):
        StatsCache(
            redis.Redis.from_url(settings.redis_url), settings.stats_cache_ttl_s
        ).invalidate()
    log.info("seed complete", extra={"inserted": inserted, "total_seed_rows": len(SEED_COMPLAINTS)})
    engine.dispose()


if __name__ == "__main__":  # pragma: no cover
    main()
