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

Measured on k3d (2 nodes), HPA `k8s/base/hpa.yaml` (target 60 % CPU, min 2, max 10), backend
requests `cpu: 100m` (`k8s/base/backend.yaml`). Raw data: `docs/evidence/hpa-watch.txt`,
`docs/evidence/load-phases.txt`; chart: `docs/evidence/hpa-scaling.png`.

- Load started **16:57:26** (hey, 10 concurrent users on `GET /api/complaints`).
- CPU crossed the target at 16:57:49 (210 %). First scale-out **2 → 6 at 16:58:04**: **~38 s**
  after load arrived. **6 → 10 at 16:58:19**, then pinned at `maxReplicas`.
- Where the time went: metrics-server scrapes about every 15 s, the HPA controller evaluates
  every 15 s, so up to ~30 s pass before the controller even sees the load; then new pods
  pull nothing (image already imported) but still run the migrate init container and must
  pass the startup and readiness probes before the Service sends them traffic.
- At 10 replicas CPU stayed ~430–455 % of request, and throughput flattened at ~190 req/s
  whether 40 or 80 users were offered: the cap and the laptop's cores were the limit, not the
  HPA. All 43,156 requests returned 200.
- Load stopped **17:01:57**; CPU fell to 6 % by 17:02:35, but replicas held at 10 until
  **17:07:35** and then dropped **10 → 2**: exactly the 300 s `scaleDown` stabilisation window.
- What would reduce the lag: a shorter metrics resolution, pre-warming (`minReplicas` sized
  for known peaks), keeping startup cheap (move migrations to a one-off Job instead of an
  init container in every pod), and scaling on a leading signal such as request rate
  instead of CPU. Autoscaling reacts; it doesn't replace capacity planning.

## 6. Why VPA is in Off mode

`k8s/base/vpa.yaml` sets `updateMode: "Off"`: recommend only, never evict. Our HPA scales on
CPU utilisation, which is usage ÷ request. VPA in Auto also acts on CPU and changes the
request: it raises the request, which lowers the utilisation the HPA computes, so the HPA
scales in; fewer pods means more load per pod, so VPA raises the request again. The two
controllers act on the same signal and fight. Recommender mode plus a human decision (read
the Target / bounds, then change `resources.requests` in a reviewed commit) is the usual
practice for exactly this reason.

### The VPA loop we actually ran

1. Guessed requests in `k8s/base/backend.yaml`: `cpu: 100m`, `memory: 128Mi`.
2. Load test (hey, 3 min, 40 users), then `kubectl describe vpa backend-vpa`
   (`docs/evidence/vpa-recommendation.txt`): Target `cpu: 511m`, `memory: 250Mi`;
   Lower Bound `25m`; the Upper Bound was huge because the recommender had only minutes of
   history, which is exactly why a human reads it rather than letting it act.
3. Updated requests to `cpu: 500m`, `memory: 256Mi` (limits `cpu: 1`, `memory: 512Mi`,
   since a request cannot exceed its limit).
4. Re-ran the same HPA load test (`docs/evidence/hpa-watch-after-vpa.txt`).
5. What changed: with the 100m guess, utilisation peaked at ~450 % and stayed ~430–455 %
   even at 10 replicas, so the HPA saw every pod as 4.5x overloaded. With 500m it peaked at
   ~180 % and fell to ~102–126 % at 10 replicas: the percentage now reflects real headroom,
   and each pod may use up to a full core. Our 80-user load still needed `maxReplicas`.

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
