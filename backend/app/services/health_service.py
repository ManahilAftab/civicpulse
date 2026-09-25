"""Readiness checks. Liveness (/health) deliberately has no service: it must not
touch any dependency, or a slow database becomes a restart loop."""

from collections.abc import Callable


class ReadinessService:
    def __init__(self, checks: dict[str, Callable[[], bool]]) -> None:
        self._checks = checks

    def failed_dependencies(self) -> list[str]:
        failed = []
        for name, check in self._checks.items():
            try:
                ok = check()
            except Exception:  # noqa: BLE001 — any error means not ready
                ok = False
            if not ok:
                failed.append(name)
        return failed
