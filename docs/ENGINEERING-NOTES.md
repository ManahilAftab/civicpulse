# Engineering notes

## Index justification

- `ix_complaints_status_priority` (`backend/alembic/versions/0001_create_complaints.py`, line 68)
  serves the dashboard filter `WHERE status = ? AND priority = ?` in
  `ComplaintRepository.list`; status-only filters use its leading column.
- `ix_complaints_created_at` (line 70) serves the default dashboard sort
  `ORDER BY created_at DESC LIMIT ? OFFSET ?`.

## Why Redis has a volume (`compose.yaml`, line 36)

Redis holds more than rebuildable cache here. It also holds the rate-limit counters and the
24 h triage cache. Losing the triage cache on every restart means re-paying LLM calls
against a free-tier quota of tens of requests per minute; losing rate-limit windows lets a
restart reset a caller's budget. AOF on a named volume keeps both. The stats cache alone
would not need it — it rebuilds in one query.

## 1. Laptop vs CI runner
_TODO (Partner B)._

## 2. CI/CD maturity ladder
_TODO (Partner B)._

## 3. Build-once-deploy-many
_TODO (Partner B)._

## 4. What "correct" means for a probabilistic component

With `TRIAGE_PROVIDER=llm` the same text can produce different output, so "correct" can't
mean "this exact answer". It means: every result is **valid** (parses into `TriageResult`,
category and priority inside our enums, summary ≤ 140 chars —
`backend/app/providers/triage/base.py`, line 47), every request **completes** (201 even
when the provider fails — fallback at `backend/app/services/triage_service.py`, line 107),
and quality is **observed**, not assumed (`/api/meta/providers`, fallback counter in
`/metrics`).

CI stays deterministic by design, not luck: it pins `TRIAGE_PROVIDER: simulated`
(`.github/workflows/ci.yml`, line 34), and failure paths are tested by injecting providers
that always raise, return malformed JSON or hang (`backend/tests/fakes.py`). The key test is
`backend/tests/test_api.py`, line 14. No test sleeps or retries to pass; the retry jitter is
injected as a function so tests record the sleep instead of waiting.

## 5. HPA lag
_TODO (Partner B)._

## 6. Why VPA is in Off mode
_TODO (Partner B)._

## 7. `internal: true` and the service that calls the LLM

`internal: true` (`compose.yaml`, line 112) removes outbound routes for `database` and
`cache`. The triage call is made by the backend, which is the only service on **both**
networks (`compose.yaml`, line 74): it reaches Postgres and Redis on `internal`, and the
Groq API through `edge`. We kept the LLM call inside the backend rather than adding an
egress proxy because triage is synchronous with the POST and the backend already needs
edge for the frontend. The trade-off: the backend is the one component that can reach both
the internet and the data, so it is the one to harden (non-root user, no secrets baked
into the image, rate limiting). Ollama sits on `edge` so it can pull its model once; the
weights then live in the `ollama_models` volume.

## 8. The failure

_TODO (Maha): write your own. Suggested, if it fits: installing Docker on Ubuntu 24.04 failed
inside `apt-get update`. What I wrongly believed first: that the Docker install script was
broken. The line that told the truth:
`E: The repository 'https://packages.microsoft.com/ubuntu/22.04/mssql-server-2022 jammy InRelease' is not signed.`
— an old SQL Server (and Yarn) apt source with a missing key was failing the whole update.
Fix: moved those source files to `/etc/apt/disabled-sources/`, `apt update` came back clean,
Docker installed. Rewrite in your own words and say how long it actually took._
