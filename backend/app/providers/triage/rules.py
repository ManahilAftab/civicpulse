"""RuleBasedTriage: deterministic keyword classifier. Always available, never fails.

Keywords include common Urdu/Roman-Urdu terms because that is how complaints
in Pakistan are actually written ("paani nahi aa raha", "bijli gayi hui hai").
"""

import re

from app.domain import Category, Priority, TriagedBy
from app.providers.triage.base import TriageResult

CATEGORY_KEYWORDS: dict[Category, tuple[str, ...]] = {
    Category.WATER: (
        "water",
        "pani",
        "paani",
        "pipe",
        "water main",
        "leak",
        "tanker",
        "tap",
        "supply line",
        "flood",
        "burst",
        "sewerage line",
        "motor",
    ),
    Category.ELECTRICITY: (
        "electricity",
        "bijli",
        "power",
        "outage",
        "loadshedding",
        "load shedding",
        "transformer",
        "wire",
        "voltage",
        "spark",
        "meter",
        "short circuit",
        "breaker",
    ),
    Category.SANITATION: (
        "garbage",
        "kachra",
        "kooda",
        "trash",
        "waste",
        "sewage",
        "gutter",
        "drain",
        "nala",
        "smell",
        "badboo",
        "mosquito",
        "machar",
        "dump",
        "overflow",
    ),
    Category.ROADS: (
        "road",
        "sarak",
        "sadak",
        "pothole",
        "gaddha",
        "khadda",
        "asphalt",
        "speed breaker",
        "footpath",
        "bridge",
        "carpet",
        "broken road",
        "traffic",
    ),
    Category.STREETLIGHTS: (
        "streetlight",
        "street light",
        "street lights",
        "streetlights",
        "lamp",
        "khamba",
        "pole light",
        "dark street",
        "andhera",
    ),
}

# Signals of danger to life or property, or damage that is actively happening.
HIGH_PRIORITY_KEYWORDS: tuple[str, ...] = (
    "burst",
    "flood",
    "flooding",
    "entering",
    "live wire",
    "spark",
    "fire",
    "aag",
    "electrocut",
    "current",
    "collapsed",
    "accident",
    "injured",
    "danger",
    "khatra",
    "overflowing",
    "emergency",
    "children",
    "bachay",
    "hospital",
    "since fajr",
    "since morning",
    "3 days",
    "three days",
    "urgent",
    "fori",
)
LOW_PRIORITY_KEYWORDS: tuple[str, ...] = (
    "paint",
    "faded",
    "cosmetic",
    "suggestion",
    "request",
    "whenever possible",
    "minor",
    "dim",
    "flicker",
    "untidy",
)

_SENTENCE_END = re.compile(r"(?<=[.!?])\s")


def _score(text: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for kw in keywords if re.search(rf"\b{re.escape(kw)}", text))


def summarise(text: str, limit: int = 140) -> str:
    first = _SENTENCE_END.split(" ".join(text.split()), maxsplit=1)[0]
    if len(first) <= limit:
        return first
    return first[: limit - 1].rstrip() + "…"


class RuleBasedTriage:
    name = TriagedBy.RULES.value

    def triage(self, text: str, location: str) -> TriageResult:
        lowered = text.lower()
        scores = {cat: _score(lowered, kws) for cat, kws in CATEGORY_KEYWORDS.items()}
        best_score = max(scores.values())
        # Ties are broken by the fixed dict order above, which keeps output deterministic.
        category = (
            next(c for c, s in scores.items() if s == best_score)
            if best_score > 0
            else Category.OTHER
        )

        if _score(lowered, HIGH_PRIORITY_KEYWORDS):
            priority = Priority.HIGH
        elif _score(lowered, LOW_PRIORITY_KEYWORDS):
            priority = Priority.LOW
        else:
            priority = Priority.NORMAL

        confidence = 0.3 if category is Category.OTHER else min(0.4 + 0.1 * best_score, 0.7)
        return TriageResult(
            category=category,
            priority=priority,
            summary=summarise(text),
            confidence=round(confidence, 2),
        )
