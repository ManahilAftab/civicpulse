"""Prometheus metrics exposed on /metrics."""

from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "civicpulse_http_requests_total",
    "HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "civicpulse_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)
TRIAGE_LATENCY = Histogram(
    "civicpulse_triage_duration_seconds",
    "Triage latency, including retries and fallback",
    ["triaged_by"],
    buckets=(0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20),
)
TRIAGE_FALLBACKS = Counter(
    "civicpulse_triage_fallbacks_total",
    "Times the primary triage provider failed and rules were used",
    ["provider", "error_class"],
)
TRIAGE_CACHE = Counter(
    "civicpulse_triage_cache_total",
    "Triage content-hash cache lookups",
    ["result"],
)
