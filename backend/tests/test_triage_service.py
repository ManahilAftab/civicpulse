import fakeredis
import httpx
import openai
import pytest

from app.domain import Category
from app.providers.cache import TriageCache, TriageRecorder
from app.providers.triage.base import NonRetryableTriageError, RetryableTriageError
from app.providers.triage.llm import LLMTriage
from app.services.triage_service import TriageService
from tests.fakes import AlwaysRaises, FailsThenSucceeds, Hangs, ReturnsRaw

TEXT, LOC = "Burst water main flooding Street 12 since fajr", "G-9/2"


def service(provider, **kw):
    r = fakeredis.FakeRedis(decode_responses=True)
    sleeps: list[float] = []
    svc = TriageService(
        provider,
        cache=TriageCache(r, 3600),
        recorder=TriageRecorder(r),
        sleep=sleeps.append,
        jitter_s=(0.5, 1.5),
        **kw,
    )
    return svc, sleeps


def test_success_uses_primary_provider():
    svc, sleeps = service(FailsThenSucceeds(failures=0))
    outcome = svc.triage(TEXT, LOC)
    assert outcome.triaged_by == "llm:groq" and not outcome.fallback and sleeps == []


def test_retryable_error_is_retried_once_with_jitter():
    provider = FailsThenSucceeds(failures=1)
    svc, sleeps = service(provider)
    outcome = svc.triage(TEXT, LOC)
    assert provider.calls == 2 and outcome.triaged_by == "llm:groq"
    assert len(sleeps) == 1 and 0.5 <= sleeps[0] <= 1.5


def test_two_retryable_failures_fall_back_after_exactly_one_retry():
    provider = AlwaysRaises(RetryableTriageError("429"))
    svc, _ = service(provider)
    outcome = svc.triage(TEXT, LOC)
    assert provider.calls == 2
    assert outcome.triaged_by == "rules:fallback" and outcome.result.category is Category.WATER


def test_non_retryable_error_is_never_retried():
    provider = AlwaysRaises(NonRetryableTriageError("HTTP 400"))
    svc, sleeps = service(provider)
    outcome = svc.triage(TEXT, LOC)
    assert provider.calls == 1 and sleeps == [] and outcome.fallback


def test_malformed_json_falls_back_to_rules():
    svc, _ = service(ReturnsRaw("I think this is about water, priority high!"))
    outcome = svc.triage(TEXT, LOC)
    assert outcome.triaged_by == "rules:fallback"
    assert outcome.error_class == "MalformedTriageOutput"


def test_hung_provider_hits_the_hard_timeout_then_falls_back():
    provider = Hangs()
    svc, _ = service(provider, timeout_s=0.05)
    outcome = svc.triage(TEXT, LOC)
    provider.release.set()
    assert outcome.triaged_by == "rules:fallback" and provider.calls == 2


def test_duplicate_complaints_cost_one_inference():
    provider = FailsThenSucceeds(failures=0)
    svc, _ = service(provider)
    first = svc.triage(TEXT, LOC)
    second = svc.triage("  burst WATER main flooding street 12 since fajr ", LOC)  # same content
    assert provider.calls == 1
    assert not first.cache_hit and second.cache_hit
    assert svc._recorder.cache_counts() == (1, 1)


def test_fallback_results_are_not_cached():
    provider = AlwaysRaises(NonRetryableTriageError("boom"))
    svc, _ = service(provider)
    svc.triage(TEXT, LOC)
    svc.triage(TEXT, LOC)
    assert provider.calls == 2  # the outage is not pinned onto this text for 24 h


# --- LLM provider error mapping, with a fake OpenAI client (no network) ---------

_REQ = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


class _FakeCompletions:
    def __init__(self, exc):
        self._exc = exc

    def create(self, **kwargs):
        raise self._exc


class _FakeClient:
    def __init__(self, exc):
        self.chat = type("Chat", (), {"completions": _FakeCompletions(exc)})()


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (openai.APITimeoutError(request=_REQ), RetryableTriageError),
        (
            openai.RateLimitError(
                "slow down", response=httpx.Response(429, request=_REQ), body=None
            ),
            RetryableTriageError,
        ),
        (
            openai.InternalServerError(
                "oops", response=httpx.Response(503, request=_REQ), body=None
            ),
            RetryableTriageError,
        ),
        (
            openai.BadRequestError("bad", response=httpx.Response(400, request=_REQ), body=None),
            NonRetryableTriageError,
        ),
        (
            openai.AuthenticationError(
                "key", response=httpx.Response(401, request=_REQ), body=None
            ),
            NonRetryableTriageError,
        ),
    ],
)
def test_llm_errors_are_classified_for_retry(exc, expected):
    provider = LLMTriage(
        base_url="https://x", api_key="k", model="m", timeout_s=1, client=_FakeClient(exc)
    )
    with pytest.raises(expected):
        provider.triage(TEXT, LOC)


def test_llm_provider_repr_never_contains_the_key():
    provider = LLMTriage(base_url="https://x", api_key="gsk_super_secret", model="m", timeout_s=1)
    assert "gsk_super_secret" not in repr(provider)
