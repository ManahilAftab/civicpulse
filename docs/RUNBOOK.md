# Runbook

## Deploy

**Local (Compose):**
```bash
cp .env.example .env            # set POSTGRES_PASSWORD; GROQ_API_KEY + TRIAGE_PROVIDER=llm for the LLM
docker compose up --build -d
curl -f http://localhost:8000/ready
```

**Kubernetes (local k3d):**
```bash
k3d cluster create civicpulse --agents 1 -p "8080:80@loadbalancer"
docker build -t civicpulse-backend:dev ./backend
k3d image import civicpulse-backend:dev -c civicpulse
kubectl apply -k k8s/overlays/dev
kubectl -n civicpulse rollout status deployment/backend
curl -f http://civicpulse.localhost:8080/api/stats
```
For a real cluster, create the Secret with real values first (see the comment in
`k8s/base/secret.yaml`); the committed one holds placeholders only.

**CI/CD:** merging to `main` runs `.github/workflows/cd.yml`: tests → build and push
`ghcr.io/manahilaftab/civicpulse-backend:<commit sha>` → smoke deploy of that exact SHA.

## Roll back

**Fast (3 a.m.):**
```bash
kubectl -n civicpulse rollout undo deployment/backend
kubectl -n civicpulse rollout status deployment/backend
```
Imperative and immediate, but the cluster now differs from Git.

**Correct (once the fire is out):** re-apply the previous known-good SHA declaratively, so
Git again says what production runs:
```bash
cd k8s/overlays/prod
kustomize edit set image civicpulse-backend=ghcr.io/manahilaftab/civicpulse-backend:<previous sha>
kubectl apply -k .
```
Commit that change through a PR.

## Read logs

Every line is JSON on stdout with a `request_id`.
```bash
docker compose logs -f backend                      # Compose
kubectl -n civicpulse logs -f deployment/backend    # Kubernetes
kubectl -n civicpulse logs deployment/backend | grep '"level": "WARNING"'
```
To follow one request, take `X-Request-ID` from the response headers and grep for it.

## When triage starts failing

Symptoms: complaints still return 201, but `triaged_by` is `rules:fallback`.

1. `GET /api/meta/providers`: check `recent[].error_class` and `latency_ms`.
2. `GET /metrics`: `civicpulse_triage_fallbacks_total` by `error_class`.
3. Logs: `grep "triage fallback"` shows complaint id, provider, error class.
4. Read the error class:
   - `RetryableTriageError: RateLimitError` → free-tier quota exhausted. Wait, or lower
     `RATE_LIMIT_REQUESTS`.
   - `RetryableTriageError: timed out` / `APIConnectionError` → provider slow or down.
   - `NonRetryableTriageError: HTTP 401` → key invalid or rotated. Update the Secret, then
     `kubectl -n civicpulse rollout restart deployment/backend`.
   - `MalformedTriageOutput` → the model changed its output format. Check the model name.
5. To stop depending on the provider entirely: set `TRIAGE_PROVIDER=rules` (ConfigMap or
   `.env`) and restart. Service stays fully available on keyword triage.

## When /ready is 503

The body names the failed dependency (`database` or `redis`). Kubernetes stops routing to
the pod but does not restart it. Liveness (`/health`) never touches dependencies, so a
database outage never becomes a restart loop. Check the dependency's pod:
`kubectl -n civicpulse get pods`, `kubectl -n civicpulse logs statefulset/postgres`.
