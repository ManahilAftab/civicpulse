# ADR 0001 — Triage behind a provider interface

**Status:** Accepted

## Context
The component that reads complaints will change: a keyword rule today, a hosted LLM now,
possibly a fine-tuned classifier later. The hosted LLM is outside our control — it can be
slow, rate-limited (free tier: tens of requests per minute) or simply wrong. A citizen
must never see a 500 because of it, and CI must be deterministic.

## Decision
- One `TriageProvider` protocol (`backend/app/providers/triage/base.py`) with a single
  method, `triage(text, location) -> TriageResult`. `TriageResult` is a Pydantic model;
  every provider's output must validate against it.
- Four implementations selected by `TRIAGE_PROVIDER` in `factory.py`:
  `LLMTriage` (Groq), `OllamaTriage` (local), `RuleBasedTriage`, `SimulatedTriage`.
- Resilience lives in one place, `services/triage_service.py`, not in each provider:
  content-hash cache → primary with a 10 s wall-clock cap → one jittered retry on
  retryable errors only (timeout, 429, 5xx) → `RuleBasedTriage` with
  `triaged_by = "rules:fallback"`.
- Providers translate their own failures into `RetryableTriageError` or
  `NonRetryableTriageError`; the service decides what to do with them.
- The OpenAI SDK's own retries are disabled (`max_retries=0`) so the retry policy exists once.

## Consequences
- Swapping models is a config change and one new class; routes and services don't change.
- CI pins `TRIAGE_PROVIDER=simulated`; failure paths are tested by injecting providers
  that raise or return malformed JSON (`tests/fakes.py`). No test sleeps or retries to pass.
- The fallback is always available but less accurate; `/api/meta/providers` and the
  `civicpulse_triage_fallbacks_total` metric make fallback rates visible.
- Only successful model answers are cached. Caching fallbacks would pin a brief outage
  onto that complaint text for 24 hours.
