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
- **Chosen provider:** Groq. What Groq's own terms say (checked 29 September 2026):
  - Inference inputs and outputs are **not retained by default**; they are logged only
    temporarily when Groq is troubleshooting reliability problems or investigating abuse
    (console.groq.com/docs/your-data).
  - The Groq Services Agreement says Groq may **not use inputs or outputs to train or
    fine-tune models** unless the customer explicitly allows it
    (console.groq.com/docs/legal/services-agreement).
  - Any customer can switch on **Zero Data Retention** in the Console's Data Controls
    page, which removes even that troubleshooting/abuse logging.
  - Residual exposure we accept: requests are processed by a US company, so complaint
    text and location leave Pakistan. That is acceptable for a coursework system with
    seeded data; a real municipality should enable ZDR or use `TRIAGE_PROVIDER=ollama`.
- **Offline option:** `TRIAGE_PROVIDER=ollama` keeps all data on the host; use it wherever
  sending citizen text to a third party is not acceptable.
- **Logs:** complaint text and contact details are never logged — only ids, provider,
  latency and error class. The API key is a `SecretStr` and never logged or repr'd.
- **Not done (yet):** automatic redaction of phone numbers and names inside free text.
  Next step: a regex pass for Pakistani mobile formats (`03xx-xxxxxxx`) before sending.

## Consequences
Free text may still contain PII a citizen typed. We accept that exposure for the Groq path
and document it; deployments that cannot accept it run the Ollama provider.
