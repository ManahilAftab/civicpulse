"""Triage orchestration: cache -> primary provider (hard timeout, one jittered retry
on retryable errors only) -> RuleBasedTriage fallback. A citizen never sees a 500
because a third party was slow, rate-limited or wrong."""

import logging
import random
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.domain import TriagedBy
from app.metrics import TRIAGE_CACHE, TRIAGE_FALLBACKS, TRIAGE_LATENCY
from app.providers.cache import TriageCache, TriageRecorder, content_hash
from app.providers.triage.base import (
    RetryableTriageError,
    TriageProvider,
    TriageResult,
)
from app.providers.triage.rules import RuleBasedTriage

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TriageOutcome:
    result: TriageResult
    triaged_by: str
    latency_ms: int
    fallback: bool
    cache_hit: bool
    error_class: str | None = None


class TriageService:
    def __init__(
        self,
        primary: TriageProvider,
        *,
        cache: TriageCache | None = None,
        recorder: TriageRecorder | None = None,
        timeout_s: float = 10.0,
        jitter_s: tuple[float, float] = (0.5, 1.5),
        sleep: Callable[[float], None] = time.sleep,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self.primary = primary
        self.fallback = RuleBasedTriage()
        self._cache = cache
        self._recorder = recorder
        self._timeout_s = timeout_s
        self._jitter = jitter_s
        self._sleep = sleep
        # The SDK timeout bounds individual socket reads; this executor enforces a
        # hard wall-clock cap on the whole call, for any provider we plug in.
        self._executor = executor or ThreadPoolExecutor(max_workers=8, thread_name_prefix="triage")

    @property
    def uses_fallback(self) -> bool:
        return self.primary.name != self.fallback.name

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _call_with_deadline(self, text: str, location: str) -> TriageResult:
        future = self._executor.submit(self.primary.triage, text, location)
        try:
            return future.result(timeout=self._timeout_s)
        except FutureTimeout as exc:
            future.cancel()
            raise RetryableTriageError(f"timed out after {self._timeout_s}s") from exc

    def _call_primary(self, text: str, location: str) -> TriageResult:
        try:
            return self._call_with_deadline(text, location)
        except RetryableTriageError:
            # Exactly one retry, with jitter so many pods don't retry in lockstep.
            self._sleep(random.uniform(*self._jitter))  # noqa: S311
            return self._call_with_deadline(text, location)

    def triage(self, text: str, location: str, complaint_id: UUID | None = None) -> TriageOutcome:
        started = time.perf_counter()
        key = content_hash(self.primary.name, text, location)

        cached = self._cache.get(key) if self._cache and self.uses_fallback else None
        if self._cache and self.uses_fallback:
            TRIAGE_CACHE.labels("hit" if cached else "miss").inc()
            if self._recorder:
                self._recorder.count_cache(hit=cached is not None)

        if cached is not None:
            outcome = TriageOutcome(cached, self.primary.name, self._ms(started), False, True)
        elif not self.uses_fallback:
            result = self.primary.triage(text, location)  # rules: cannot fail
            outcome = TriageOutcome(result, self.primary.name, self._ms(started), False, False)
        else:
            try:
                result = self._call_primary(text, location)
                if self._cache:
                    # Only successful model answers are cached. Caching a fallback would
                    # pin a 30-second outage onto that complaint text for 24 hours.
                    self._cache.set(key, result)
                outcome = TriageOutcome(result, self.primary.name, self._ms(started), False, False)
            except Exception as exc:  # noqa: BLE001 — any provider failure means fallback
                error_class = type(exc).__name__
                TRIAGE_FALLBACKS.labels(self.primary.name, error_class).inc()
                log.warning(
                    "triage fallback",
                    extra={
                        "complaint_id": str(complaint_id) if complaint_id else None,
                        "provider": self.primary.name,
                        "error_class": error_class,
                        "error": str(exc)[:200],
                    },
                )
                result = self.fallback.triage(text, location)
                outcome = TriageOutcome(
                    result,
                    TriagedBy.RULES_FALLBACK.value,
                    self._ms(started),
                    True,
                    False,
                    error_class,
                )

        TRIAGE_LATENCY.labels(outcome.triaged_by).observe(outcome.latency_ms / 1000)
        if self._recorder:
            self._recorder.record(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "provider": self.primary.name,
                    "triaged_by": outcome.triaged_by,
                    "latency_ms": outcome.latency_ms,
                    "fallback": outcome.fallback,
                    "cache_hit": outcome.cache_hit,
                    "error_class": outcome.error_class,
                }
            )
        return outcome

    @staticmethod
    def _ms(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)
