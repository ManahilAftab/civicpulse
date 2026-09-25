import json

import pytest

from app.domain import Category, Priority
from app.providers.triage.base import (
    MalformedTriageOutput,
    RetryableTriageError,
    parse_triage_output,
)
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage

rules = RuleBasedTriage()


@pytest.mark.parametrize(
    ("text", "category", "priority"),
    [
        (
            "Burst water main flooding Street 12 since fajr, water entering homes",
            Category.WATER,
            Priority.HIGH,
        ),
        (
            "Bijli gayi hui hai since last night, transformer making noise",
            Category.ELECTRICITY,
            Priority.NORMAL,
        ),
        (
            "Kachra not collected for two weeks, badboo everywhere",
            Category.SANITATION,
            Priority.NORMAL,
        ),
        (
            "Huge gaddha on the road, motorcycle accident, one injured",
            Category.ROADS,
            Priority.HIGH,
        ),
        ("Streetlight flickering outside house 14", Category.STREETLIGHTS, Priority.LOW),
        (
            "Stray dogs are chasing people in our street every evening",
            Category.OTHER,
            Priority.NORMAL,
        ),
    ],
)
def test_rules_classify_realistic_complaints(text, category, priority):
    result = rules.triage(text, "G-9/2")
    assert (result.category, result.priority) == (category, priority)


def test_rules_are_deterministic_and_summary_fits():
    text = "Paani nahi aa raha. " + "Very long complaint text. " * 20
    first, second = rules.triage(text, "I-8"), rules.triage(text, "I-8")
    assert first == second
    assert len(first.summary) <= 140


def test_simulated_is_deterministic_and_can_inject_failures():
    sim = SimulatedTriage(seed=7)
    assert sim.triage("Pipe leak near masjid", "F-7") == sim.triage("Pipe leak near masjid", "F-7")
    with pytest.raises(RetryableTriageError):
        SimulatedTriage(seed=7, failure_rate=1.0).triage("Pipe leak near masjid", "F-7")


GOOD = {"category": "water", "priority": "high", "summary": "Burst main", "confidence": 0.9}


def test_valid_json_parses():
    assert parse_triage_output(json.dumps(GOOD)).category is Category.WATER


@pytest.mark.parametrize(
    "raw",
    [
        "Sure! This is a water complaint with high priority.",  # prose
        "```json\n" + json.dumps(GOOD) + "\n```",  # code fence
        json.dumps(GOOD | {"category": "plumbing"}),  # not in enum
        json.dumps(GOOD | {"priority": "critical"}),  # not in enum
        json.dumps(GOOD | {"summary": "x" * 400}),  # "one line" of 400 chars
        json.dumps(GOOD | {"confidence": 7}),  # out of range
        json.dumps([GOOD]),  # not an object
        "",  # empty
    ],
)
def test_malformed_model_output_is_rejected(raw):
    with pytest.raises(MalformedTriageOutput):
        parse_triage_output(raw)
