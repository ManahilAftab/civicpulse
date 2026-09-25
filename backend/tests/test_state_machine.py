import pytest

from app.domain import ALLOWED_TRANSITIONS, Status
from app.errors import InvalidTransition
from app.services.complaint_service import ensure_transition

VALID = [
    (Status.OPEN, Status.IN_PROGRESS),
    (Status.OPEN, Status.REJECTED),
    (Status.IN_PROGRESS, Status.RESOLVED),
    (Status.IN_PROGRESS, Status.REJECTED),
]


@pytest.mark.parametrize(("current", "target"), VALID)
def test_valid_transitions_are_allowed(current, target):
    ensure_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [(a, b) for a in Status for b in Status if (a, b) not in VALID],
)
def test_every_other_transition_is_rejected(current, target):
    with pytest.raises(InvalidTransition) as exc:
        ensure_transition(current, target)
    assert f"{current.value} -> {target.value}" in str(exc.value)


def test_terminal_states_have_no_exits():
    assert ALLOWED_TRANSITIONS[Status.RESOLVED] == frozenset()
    assert ALLOWED_TRANSITIONS[Status.REJECTED] == frozenset()
