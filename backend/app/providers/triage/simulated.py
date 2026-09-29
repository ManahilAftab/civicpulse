"""SimulatedTriage: a deterministic fake for CI. No network, seeded, with
configurable failure injection so the fallback path can be exercised on purpose."""

import hashlib

from app.domain import TriagedBy
from app.providers.triage.base import RetryableTriageError, TriageResult
from app.providers.triage.rules import RuleBasedTriage


class SimulatedTriage:
    name = TriagedBy.SIMULATED.value

    def __init__(self, seed: int = 42, failure_rate: float = 0.0) -> None:
        self._seed = seed
        self._failure_rate = failure_rate
        self._rules = RuleBasedTriage()

    def _unit_interval(self, text: str) -> float:
        digest = hashlib.sha256(f"{self._seed}:{text}".encode()).digest()
        return int.from_bytes(digest[:4], "big") / 0xFFFFFFFF

    def triage(self, text: str, location: str) -> TriageResult:
        roll = self._unit_interval(text)
        if roll < self._failure_rate:
            raise RetryableTriageError("simulated provider failure (injected)")
        base = self._rules.triage(text, location)
        # Same text + same seed -> same confidence, on every run, on every machine.
        return base.model_copy(update={"confidence": round(0.6 + 0.4 * roll, 2)})
