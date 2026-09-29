# ADR 0004 — What complaint data leaves our machine

**Status:** Accepted

## Context
Complaints contain PII: reporter phone numbers, house numbers, sometimes names inside the
free text. Triage sends data to a third party (Groq). Free-tier terms can change, and some
free tiers (e.g. Gemini) may use inputs to improve models.

## Decision
- **Never sent:** `reporter_contact`. The provider receives only `text` and `location`
  (`build_messages` in `providers/triage/llm.py`).
- **Sent:** complaint text and location, because triage is impossible without them.
  Location is sector-level in practice (e.g. "G-9/2, Islamabad").
- **Chosen provider:** Groq. *(TODO before submitting: read Groq's current data-use and
  retention terms, and record here exactly what they say and the date you checked.)*
- **Offline option:** `TRIAGE_PROVIDER=ollama` keeps all data on the host; use it wherever
  sending citizen text to a third party is not acceptable.
- **Logs:** complaint text and contact details are never logged — only ids, provider,
  latency and error class. The API key is a `SecretStr` and never logged or repr'd.
- **Not done (yet):** automatic redaction of phone numbers and names inside free text.
  Next step: a regex pass for Pakistani mobile formats (`03xx-xxxxxxx`) before sending.

## Consequences
Free text may still contain PII a citizen typed. We accept that exposure for the Groq path
and document it; deployments that cannot accept it run the Ollama provider.
