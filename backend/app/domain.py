"""Domain vocabulary: enums and the complaint status state machine.

The transition table below is the single source of truth for valid status
changes. The frontend never duplicates it — it asks the server and renders
the 409 message when a transition is refused.
"""

from enum import StrEnum


class Category(StrEnum):
    WATER = "water"
    ELECTRICITY = "electricity"
    SANITATION = "sanitation"
    ROADS = "roads"
    STREETLIGHTS = "streetlights"
    OTHER = "other"


class Priority(StrEnum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class Status(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"


# Explicit transition table — not a chain of ifs. Terminal states map to an empty set.
ALLOWED_TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.OPEN: frozenset({Status.IN_PROGRESS, Status.REJECTED}),
    Status.IN_PROGRESS: frozenset({Status.RESOLVED, Status.REJECTED}),
    Status.RESOLVED: frozenset(),
    Status.REJECTED: frozenset(),
}


class TriagedBy(StrEnum):
    LLM_GROQ = "llm:groq"
    LLM_OLLAMA = "llm:ollama"
    RULES = "rules"
    RULES_FALLBACK = "rules:fallback"
    SIMULATED = "simulated"
