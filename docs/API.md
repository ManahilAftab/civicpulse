# CivicPulse API contract

The source of truth is the live OpenAPI schema at `GET /openapi.json` (FastAPI generates
it from `backend/app/schemas.py`). Generate the frontend client from it:

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o frontend/src/api/schema.d.ts
```

## Vocabulary

| Field | Values |
|---|---|
| `category` | `water` · `electricity` · `sanitation` · `roads` · `streetlights` · `other` |
| `priority` | `high` · `normal` · `low` |
| `status` | `open` · `in_progress` · `resolved` · `rejected` (default `open`) |
| `triaged_by` | `llm:groq` · `llm:ollama` · `rules` · `rules:fallback` · `simulated` |

Valid status transitions are decided by the server only. The frontend must not keep its
own list — show the server's 409 `detail` verbatim.

## Endpoints

| Method | Path | Success | Errors |
|---|---|---|---|
| POST | `/api/complaints` | 201 `Complaint` | 400 field errors · 429 + `Retry-After` |
| GET | `/api/complaints/{id}` | 200 `Complaint` | 404 · 400 (bad UUID) |
| GET | `/api/complaints?category=&priority=&status=&page=1&page_size=20` | 200 `Page` | 400 (`page_size` > 100) |
| PATCH | `/api/complaints/{id}/status` | 200 `Complaint` | 404 · 409 |
| GET | `/api/stats` | 200 `Stats` + header `X-Cache: HIT \| MISS` | — |
| GET | `/api/meta/providers` | 200 `Providers` | — |
| GET | `/health` | 200 `{"status":"ok"}` — liveness, touches nothing | — |
| GET | `/ready` | 200 `{"status":"ok","failed":[]}` | 503 `{"status":"unavailable","failed":["database"]}` |
| GET | `/metrics` | 200 Prometheus text | — |

Every response carries `X-Request-ID` (echoed from the request, or generated).

## Shapes

**POST body**
```json
{ "text": "10–2000 chars", "location": "3–200 chars", "reporter_contact": "optional, ≤ 200" }
```

**Complaint**
```json
{
  "id": "uuid", "text": "...", "location": "...", "reporter_contact": null,
  "category": "water", "priority": "high", "status": "open",
  "ai_summary": "≤ 140 chars", "triaged_by": "llm:groq", "triage_latency_ms": 812,
  "created_at": "2026-09-25T18:51:33Z", "updated_at": "2026-09-25T18:51:33Z"
}
```

**Page** — `{ "items": [Complaint], "total": 42, "page": 1, "page_size": 20 }`

**PATCH body** — `{ "status": "in_progress" }`

**Stats**
```json
{ "total": 35,
  "by_category": { "water": 6, "electricity": 7, "sanitation": 6, "roads": 6, "streetlights": 5, "other": 5 },
  "by_priority": { "high": 12, "normal": 18, "low": 5 },
  "by_status":   { "open": 20, "in_progress": 8, "resolved": 3, "rejected": 4 } }
```

**Providers**
```json
{ "active_provider": "llm:groq", "fallback_provider": "rules",
  "recent": [ { "at": "...", "provider": "llm:groq", "triaged_by": "rules:fallback",
                "latency_ms": 1416, "fallback": true, "cache_hit": false,
                "error_class": "RetryableTriageError" } ],
  "cache": { "hits": 4, "misses": 9, "hit_rate": 0.308 } }
```

**Errors**
```json
{ "detail": "Validation failed", "errors": [ { "field": "text", "message": "String should have at least 10 characters" } ] }
{ "detail": "Invalid status transition: resolved -> open" }
{ "detail": "Complaint 3f2c… not found" }
{ "detail": "Rate limit exceeded. Please try again later." }
```
