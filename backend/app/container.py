"""Composition root: builds long-lived objects once per process. Tests pass in
fakes (SQLite engine, fakeredis, a provider that always raises) through here."""

from dataclasses import dataclass

import redis
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db import build_engine, build_session_factory
from app.providers.cache import RateLimiter, StatsCache, TriageCache, TriageRecorder
from app.providers.triage.base import TriageProvider
from app.providers.triage.factory import build_provider
from app.services.triage_service import TriageService


@dataclass
class Container:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    redis: redis.Redis
    stats_cache: StatsCache
    rate_limiter: RateLimiter
    triage_recorder: TriageRecorder
    triage_service: TriageService

    def close(self) -> None:
        self.triage_service.shutdown()
        self.engine.dispose()  # close pooled Postgres connections
        self.redis.close()


def build_container(
    settings: Settings,
    *,
    engine: Engine | None = None,
    redis_client: redis.Redis | None = None,
    provider: TriageProvider | None = None,
) -> Container:
    engine = engine or build_engine(settings.database_url)
    r = redis_client or redis.Redis.from_url(
        settings.redis_url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2
    )
    recorder = TriageRecorder(r)
    triage_service = TriageService(
        provider or build_provider(settings),
        cache=TriageCache(r, settings.triage_cache_ttl_s),
        recorder=recorder,
        timeout_s=settings.triage_timeout_s,
        jitter_s=(settings.triage_retry_jitter_min_s, settings.triage_retry_jitter_max_s),
    )
    return Container(
        settings=settings,
        engine=engine,
        session_factory=build_session_factory(engine),
        redis=r,
        stats_cache=StatsCache(r, settings.stats_cache_ttl_s),
        rate_limiter=RateLimiter(r, settings.rate_limit_requests, settings.rate_limit_window_s),
        triage_recorder=recorder,
        triage_service=triage_service,
    )
