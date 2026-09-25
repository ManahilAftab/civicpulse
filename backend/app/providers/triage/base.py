"""The TriageProvider interface and the schema every provider must satisfy.

The same Pydantic machinery validates HTTP input and LLM output: model output is
untrusted until it parses into TriageResult.
"""

import json
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain import Category, Priority


class TriageResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: Category
    priority: Priority
    summary: str = Field(min_length=1, max_length=140)
    confidence: float = Field(ge=0.0, le=1.0)


@runtime_checkable
class TriageProvider(Protocol):
    name: str

    def triage(self, text: str, location: str) -> TriageResult: ...


class TriageError(Exception):
    """A provider could not produce a valid TriageResult."""


class RetryableTriageError(TriageError):
    """Timeout, 429 or 5xx: the same request may succeed on a second attempt."""


class NonRetryableTriageError(TriageError):
    """400, auth failure, or malformed output: retrying would fail the same way."""


class MalformedTriageOutput(NonRetryableTriageError):
    """The model answered, but not with JSON matching TriageResult."""


def parse_triage_output(raw: str) -> TriageResult:
    """Strictly parse model output. Prose, code fences, out-of-enum categories and
    over-long summaries are all rejected — never eval'd, never repaired by guessing."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise MalformedTriageOutput(f"output is not JSON: {raw[:80]!r}") from exc
    if not isinstance(data, dict):
        raise MalformedTriageOutput("output is not a JSON object")
    try:
        return TriageResult.model_validate(data)
    except ValidationError as exc:
        fields = ",".join(str(e["loc"][0]) for e in exc.errors() if e["loc"])
        raise MalformedTriageOutput(f"output failed schema validation: {fields}") from exc
