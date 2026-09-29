"""Redis-backed providers. One Redis, several jobs:

  * StatsCache       — read-through cache for /api/stats (TTL + invalidate-on-write)
  * TriageCache      — content-hash cache of triage results (24 h TTL)
  * RateLimiter      — distributed fixed-window limiter for POST /api/complaints
  * TriageRecorder   — last 20 triage outcomes + cache hit/miss counters

Everything lives in Redis rather than process memory because the HPA runs several
backend pods: an in-process limiter would allow N_pods times the intended traffic,
and an in-process outcome log would show a different history on every refresh.

Cache failures fail open (log and continue): a Redis blip must not turn into a 500
for a citizen. /ready reports Redis as down so Kubernetes can react.
"""

import hashlib
import json
import logging
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

import redis

from app.providers.triage.base import TriageResult

log = logging.getLogger(__name__)

STATS_KEY = "cache:stats:v1"
TRIAGE_KEY_PREFIX = "cache:triage:v1:"
OUTCOMES_KEY = "triage:outcomes"
CACHE_HITS_KEY = "triage:cache:hits"
CACHE_MISSES_KEY = "triage:cache:misses"
RECENT_OUTCOMES = 20


def ping(client: redis.Redis) -> bool:
    try:
        return bool(client.ping())  # type: ignore[union-attr]
    except redis.RedisError:
        return False


class StatsCache:
    def __init__(self, client: redis.Redis, ttl_s: int) -> None:
        # Typed as Any: redis-py stubs mix sync and async return types.
        self._r: Any = client
        self._ttl = ttl_s

    def get(self) -> dict[str, Any] | None:
        try:
            raw = self._r.get(STATS_KEY)
        except redis.RedisError:
            log.warning("stats cache read failed", extra={"error_class": "RedisError"})
            return None
        return json.loads(raw) if raw else None

    def set(self, value: dict[str, Any]) -> None:
        try:
            self._r.set(STATS_KEY, json.dumps(value), ex=self._ttl)
        except redis.RedisError:
            log.warning("stats cache write failed", extra={"error_class": "RedisError"})

    def invalidate(self) -> None:
        try:
            self._r.delete(STATS_KEY)
        except redis.RedisError:
            # The TTL still bounds staleness to 30 s — that is why we keep both.
            log.warning("stats cache invalidation failed", extra={"error_class": "RedisError"})


def content_hash(provider_name: str, text: str, location: str) -> str:
    """Key on normalised content so the nine neighbours reporting the same burst main
    cost one inference. The provider name is part of the key so switching providers
    never serves another model's answer."""
    normalised = " ".join(text.lower().split()) + "\x1f" + " ".join(location.lower().split())
    return hashlib.sha256(f"{provider_name}\x1f{normalised}".encode()).hexdigest()


class TriageCache:
    def __init__(self, client: redis.Redis, ttl_s: int) -> None:
        # Typed as Any: redis-py stubs mix sync and async return types.
        self._r: Any = client
        self._ttl = ttl_s

    def get(self, key: str) -> TriageResult | None:
        try:
            raw = self._r.get(TRIAGE_KEY_PREFIX + key)
        except redis.RedisError:
            return None
        if not raw:
            return None
        try:
            return TriageResult.model_validate_json(raw)
        except ValueError:
            return None  # a stale or corrupt entry is just a miss

    def set(self, key: str, result: TriageResult) -> None:
        try:
            self._r.set(TRIAGE_KEY_PREFIX + key, result.model_dump_json(), ex=self._ttl)
        except redis.RedisError:
            log.warning("triage cache write failed", extra={"error_class": "RedisError"})


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_s: int


class RateLimiter:
    """Fixed-window counter: key = ratelimit:<ip>:<window index>. INCR is atomic in
    Redis, so every pod shares one count per client per window."""

    def __init__(self, client: redis.Redis, limit: int, window_s: int) -> None:
        # Typed as Any: redis-py stubs mix sync and async return types.
        self._r: Any = client
        self._limit = limit
        self._window = window_s

    def hit(self, client_id: str, now: float | None = None) -> RateLimitDecision:
        now = time.time() if now is None else now
        window_index = int(now // self._window)
        key = f"ratelimit:{client_id}:{window_index}"
        try:
            pipe = self._r.pipeline()
            pipe.incr(key)
            pipe.expire(key, self._window + 1)
            count, _ = pipe.execute()
        except redis.RedisError:
            log.warning(
                "rate limiter unavailable; failing open", extra={"error_class": "RedisError"}
            )
            return RateLimitDecision(allowed=True, retry_after_s=0)
        if int(count) > self._limit:
            retry_after = max(1, int((window_index + 1) * self._window - now))
            return RateLimitDecision(allowed=False, retry_after_s=retry_after)
        return RateLimitDecision(allowed=True, retry_after_s=0)


class TriageRecorder:
    def __init__(self, client: redis.Redis) -> None:
        # Typed as Any: redis-py stubs mix sync and async return types.
        self._r: Any = client

    def record(self, outcome: dict[str, Any]) -> None:
        try:
            pipe = self._r.pipeline()
            pipe.lpush(OUTCOMES_KEY, json.dumps(outcome, default=str))
            pipe.ltrim(OUTCOMES_KEY, 0, RECENT_OUTCOMES - 1)
            pipe.execute()
        except redis.RedisError:
            log.warning("could not record triage outcome", extra={"error_class": "RedisError"})

    def count_cache(self, hit: bool) -> None:
        with suppress(redis.RedisError):
            self._r.incr(CACHE_HITS_KEY if hit else CACHE_MISSES_KEY)

    def recent(self) -> list[dict[str, Any]]:
        try:
            return [json.loads(x) for x in self._r.lrange(OUTCOMES_KEY, 0, RECENT_OUTCOMES - 1)]
        except redis.RedisError:
            return []

    def cache_counts(self) -> tuple[int, int]:
        try:
            hits, misses = self._r.mget(CACHE_HITS_KEY, CACHE_MISSES_KEY)
        except redis.RedisError:
            return 0, 0
        return int(hits or 0), int(misses or 0)
