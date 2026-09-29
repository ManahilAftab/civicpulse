import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.container import build_container
from app.main import create_app
from app.providers.triage.base import RetryableTriageError
from tests.conftest import VALID, make_settings
from tests.fakes import AlwaysRaises


# --- The one test the brief says to write if you write no other -----------------
def test_provider_that_always_raises_still_returns_201_with_rules_fallback(make_client):
    client = make_client(provider=AlwaysRaises(RetryableTriageError("Groq is down")))
    resp = client.post("/api/complaints", json=VALID)
    assert resp.status_code == 201
    assert resp.json()["triaged_by"] == "rules:fallback"
    assert resp.json()["category"] == "water"


def test_create_then_get_round_trip(client):
    created = client.post("/api/complaints", json=VALID)
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "open"
    assert body["triaged_by"] == "simulated"
    assert body["ai_summary"] and len(body["ai_summary"]) <= 140
    assert body["triage_latency_ms"] >= 0

    fetched = client.get(f"/api/complaints/{body['id']}")
    assert fetched.status_code == 200 and fetched.json() == body


def test_validation_errors_are_400_with_field_level_body(client):
    resp = client.post("/api/complaints", json={"text": "short", "location": "x"})
    assert resp.status_code == 400
    fields = {e["field"] for e in resp.json()["errors"]}
    assert {"text", "location"} <= fields


def test_unknown_complaint_is_404(client):
    resp = client.get(f"/api/complaints/{uuid.uuid4()}")
    assert resp.status_code == 404 and "not found" in resp.json()["detail"]


def test_list_filters_and_paginates_with_total(client):
    for i in range(5):
        client.post(
            "/api/complaints", json=VALID | {"text": f"Burst water main flooding lane {i} now"}
        )
    client.post(
        "/api/complaints", json=VALID | {"text": "Kachra not collected for two weeks in G-6"}
    )

    page = client.get("/api/complaints", params={"category": "water", "page": 1, "page_size": 2})
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 5 and len(body["items"]) == 2 and body["page_size"] == 2
    assert all(item["category"] == "water" for item in body["items"])

    page3 = client.get("/api/complaints", params={"category": "water", "page": 3, "page_size": 2})
    assert len(page3.json()["items"]) == 1


def test_page_size_above_100_is_rejected(client):
    resp = client.get("/api/complaints", params={"page_size": 101})
    assert resp.status_code == 400 and resp.json()["errors"][0]["field"] == "page_size"


def test_status_machine_over_http(client):
    cid = client.post("/api/complaints", json=VALID).json()["id"]
    ok = client.patch(f"/api/complaints/{cid}/status", json={"status": "in_progress"})
    assert ok.status_code == 200 and ok.json()["status"] == "in_progress"
    assert (
        client.patch(f"/api/complaints/{cid}/status", json={"status": "resolved"}).status_code
        == 200
    )

    bad = client.patch(f"/api/complaints/{cid}/status", json={"status": "open"})
    assert bad.status_code == 409
    assert bad.json()["detail"] == "Invalid status transition: resolved -> open"


def test_stats_cache_miss_hit_and_invalidation_on_write(client):
    client.post("/api/complaints", json=VALID)
    first = client.get("/api/stats")
    second = client.get("/api/stats")
    assert first.headers["X-Cache"] == "MISS" and second.headers["X-Cache"] == "HIT"
    assert first.json()["total"] == 1 and first.json()["by_category"]["water"] == 1

    client.post("/api/complaints", json=VALID)  # a write must invalidate, not wait 30 s
    third = client.get("/api/stats")
    assert third.headers["X-Cache"] == "MISS" and third.json()["total"] == 2


def test_rate_limit_returns_429_with_retry_after(make_client):
    client = make_client(rate_limit_requests=2)
    headers = {"X-Real-IP": "203.0.113.9"}
    assert client.post("/api/complaints", json=VALID, headers=headers).status_code == 201
    assert client.post("/api/complaints", json=VALID, headers=headers).status_code == 201
    blocked = client.post("/api/complaints", json=VALID, headers=headers)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    # A different client has its own budget.
    other = client.post("/api/complaints", json=VALID, headers={"X-Real-IP": "198.51.100.4"})
    assert other.status_code == 201


def test_meta_providers_reports_recent_outcomes_and_cache(make_client):
    client = make_client(provider=AlwaysRaises(RetryableTriageError("down")))
    client.post("/api/complaints", json=VALID)
    body = client.get("/api/meta/providers").json()
    assert body["active_provider"] == "llm:groq" and body["fallback_provider"] == "rules"
    last = body["recent"][0]
    assert last["fallback"] is True and last["triaged_by"] == "rules:fallback"
    assert "latency_ms" in last and body["cache"]["misses"] == 1


def test_request_id_is_propagated_or_generated(client):
    assert (
        client.get("/health", headers={"X-Request-ID": "abc-123"}).headers["X-Request-ID"]
        == "abc-123"
    )
    assert len(client.get("/health").headers["X-Request-ID"]) == 36


def test_metrics_exposes_prometheus_text(client):
    client.get("/health")
    body = client.get("/metrics").text
    assert "civicpulse_http_requests_total" in body
    assert "civicpulse_triage_fallbacks_total" in body


# --- /health vs /ready -----------------------------------------------------------
def _client_with_dead_database(redis_client) -> TestClient:
    dead = create_engine(
        "postgresql+psycopg://u:p@127.0.0.1:1/none", connect_args={"connect_timeout": 1}
    )
    settings = make_settings()
    container = build_container(
        settings, engine=dead, redis_client=redis_client, provider=AlwaysRaises()
    )
    return TestClient(create_app(settings, container))


def test_health_does_not_touch_the_database(redis_client):
    assert _client_with_dead_database(redis_client).get("/health").status_code == 200


def test_ready_names_the_failed_dependency(redis_client, client):
    assert client.get("/ready").status_code == 200
    resp = _client_with_dead_database(redis_client).get("/ready")
    assert resp.status_code == 503 and resp.json()["failed"] == ["database"]


def test_malformed_json_names_the_body_not_a_character_offset(client):
    resp = client.post(
        "/api/complaints",
        content='{"text": "ELECTRICITY PROBLEM, "location": "F-10/2"}',
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
    assert resp.json()["errors"][0]["field"] == "body"


def test_openapi_documents_400_not_422(client):
    schema = client.get("/openapi.json").json()
    for operations in schema["paths"].values():
        for operation in operations.values():
            assert "422" not in operation["responses"]
    post = schema["paths"]["/api/complaints"]["post"]["responses"]
    assert {"201", "400", "429"} <= set(post)
