# Triage

How a complaint becomes a category, a priority and a summary — and what happens when
the model misbehaves.

## Pipeline (`backend/app/services/triage_service.py`)

1. **Content-hash cache (Redis, 24 h).** Key = SHA-256 of provider name + normalised text +
   location (`providers/cache.py`, `content_hash`). Nine neighbours reporting the same burst
   main cost one inference.
2. **Primary provider** chosen by `TRIAGE_PROVIDER` (`providers/triage/factory.py`).
3. **Hard 10 s wall-clock cap** on every call (`_call_with_deadline`, line 68), on top of the
   SDK's socket timeout.
4. **One retry with 0.5–1.5 s jitter** — only for timeout, 429 and 5xx (`_call_primary`, line 76).
   A 400 or malformed output is never retried.
5. **Fallback to `RuleBasedTriage`**, recorded as `triaged_by = "rules:fallback"`, with one
   WARNING log line carrying the complaint id, provider and error class (line 107).
6. Only successful model answers are cached. Caching a fallback would pin a brief outage
   onto that text for 24 hours.

## Output is untrusted

`parse_triage_output` (`providers/triage/base.py`, line 47) parses strictly: prose, code
fences, categories outside the enum, summaries over 140 characters and out-of-range
confidence are all rejected. Nothing from the model is `eval`'d or used to build SQL.

## Prompt injection

Complaint text is wrapped in `<complaint>` delimiters; any delimiter look-alikes a citizen
types are stripped first (`providers/triage/llm.py`, lines 46–62). The system prompt says the
block is data, not instructions. Even if the model obeys an injection, its answer must
still pass the schema. Test: `tests/test_injection.py`, line 38.

## Providers

| `TRIAGE_PROVIDER` | Class | Notes |
|---|---|---|
| `llm` | `LLMTriage` | Groq, OpenAI-compatible, JSON mode, temperature 0 |
| `ollama` | `OllamaTriage` | Local model, same code path, no data leaves the host |
| `rules` | `RuleBasedTriage` | Keywords incl. Roman Urdu (paani, bijli, kachra, gaddha) |
| `simulated` | `SimulatedTriage` | Deterministic, seeded, failure injection — used in CI |

## Measured

_TODO (Maha): run with a Groq key, submit ~20 complaints including duplicates, then record
from `GET /api/meta/providers`: cache hit rate, typical `latency_ms` for Groq vs rules, and
how many fell back. Don't estimate — paste what you measured._
