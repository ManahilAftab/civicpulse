# Backend → platform handoff (for Partner B)

Everything you need to containerise and deploy the backend.

## Run command

```bash
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 20
```
`--factory` matters: importing `app.main` builds nothing, so tests stay hermetic.
Exec form in the Dockerfile:
`CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "20"]`

Install from `requirements.txt` (runtime) — copy it **before** the source for layer caching.
`requirements-dev.txt` is for CI only and must not be in the final image.

## Migrations and seed — not at app startup

The app never creates tables. Run these as a one-shot step before the API starts:

```bash
alembic upgrade head      # schema
python -m app.seed        # 34 complaints; safe to run any number of times
```

- **Compose:** a `migrate` service using the backend image with
  `command: sh -c "alembic upgrade head && python -m app.seed"`, `depends_on: database: condition: service_healthy`,
  and the backend `depends_on: migrate: condition: service_completed_successfully`.
- **Kubernetes:** a `Job` (or an `initContainer` on the backend Deployment) running the same command.

## Environment variables

| Variable | Example | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://civicpulse:${POSTGRES_PASSWORD}@database:5432/civicpulse` | Secret (contains password) |
| `REDIS_URL` | `redis://cache:6379/0` | ConfigMap |
| `TRIAGE_PROVIDER` | `llm` · `ollama` · `rules` · `simulated` | CI uses `simulated` |
| `GROQ_API_KEY` | — | Secret. Required only when `TRIAGE_PROVIDER=llm` |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | ConfigMap |
| `OLLAMA_BASE_URL` | `http://ollama:11434/v1` | ConfigMap |
| `OLLAMA_MODEL` | `llama3.2:1b` | ConfigMap |
| `TRIAGE_TIMEOUT_S` | `10` | |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_S` | `10` / `60` | Set high in the CI integration job |
| `TRUST_PROXY_HEADERS` | `true` | Rate limiter keys on `X-Real-IP` |
| `LOG_LEVEL` | `INFO` | |

Use service names, never `localhost` (−8 marks).

## nginx

Proxy `/api/` to `http://backend:8000` and set the client IP header the rate limiter reads:

```nginx
location /api/ {
    proxy_pass http://backend:8000;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Request-ID $request_id;
    proxy_read_timeout 30s;   # triage can take up to ~21 s worst case (10 s + retry + 10 s)
}
```

## Probes and healthchecks

- Compose backend healthcheck: `python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready')"`
  (the slim image has no curl).
- K8s: startup + liveness → `/health`; readiness → `/ready`. Never swap them.
- Graceful shutdown: set `terminationGracePeriodSeconds: 30` and a `preStop` sleep of ~5 s.
  Verified locally: SIGTERM during a 3-second LLM call → that request still returns 201,
  new connections are refused, then the DB pool closes.

## Network note (engineering notes Q7)

The backend is the only service on both networks. `internal: true` blocks outbound traffic
for `database` and `cache` only; the backend reaches Groq through the `edge` network.
The `ollama` container needs internet only to pull the model the first time — put it on
`internal` after the weights are in the `ollama_models` volume, or on `edge` if you pull at runtime.

## CI commands

```bash
cd backend
pip install -r requirements-dev.txt
ruff check app tests alembic && ruff format --check app tests alembic
mypy app
TRIAGE_PROVIDER=simulated pytest        # coverage gate ≥ 65% is in pyproject.toml
```
