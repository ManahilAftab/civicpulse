"""Injectable providers for deterministic tests. No network, no sleeps."""

import threading

from app.domain import Category, Priority
from app.providers.triage.base import (
    NonRetryableTriageError,
    RetryableTriageError,
    TriageResult,
    parse_triage_output,
)


class AlwaysRaises:
    name = "llm:groq"

    def __init__(self, exc: Exception | None = None) -> None:
        self.calls = 0
        self._exc = exc or RetryableTriageError("provider down")

    def triage(self, text: str, location: str) -> TriageResult:
        self.calls += 1
        raise self._exc


class ReturnsRaw:
    """Behaves like an LLM that answered with this raw string."""

    name = "llm:groq"

    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.calls = 0

    def triage(self, text: str, location: str) -> TriageResult:
        self.calls += 1
        return parse_triage_output(self.raw)


class FailsThenSucceeds:
    name = "llm:groq"

    def __init__(self, failures: int, exc: Exception | None = None) -> None:
        self.calls = 0
        self._failures = failures
        self._exc = exc or RetryableTriageError("429")

    def triage(self, text: str, location: str) -> TriageResult:
        self.calls += 1
        if self.calls <= self._failures:
            raise self._exc
        return TriageResult(
            category=Category.WATER, priority=Priority.HIGH, summary="Burst main", confidence=0.9
        )


class Hangs:
    """Blocks until released — used to prove the hard timeout, without time.sleep."""

    name = "llm:groq"

    def __init__(self) -> None:
        self.release = threading.Event()
        self.calls = 0

    def triage(self, text: str, location: str) -> TriageResult:
        self.calls += 1
        self.release.wait(timeout=5)
        raise NonRetryableTriageError("released")
