import pytest
import redis

from app.config import Settings
from app.providers.cache import RateLimiter, StatsCache, TriageRecorder
from app.providers.triage.factory import UnknownProviderError, build_provider


@pytest.mark.parametrize(
    ("choice", "name"),
    [("rules", "rules"), ("simulated", "simulated"), ("ollama", "llm:ollama"), ("LLM", "llm:groq")],
)
def test_provider_is_selected_by_environment_variable(choice, name):
    settings = Settings(triage_provider=choice, groq_api_key="test-key")  # type: ignore[arg-type]
    assert build_provider(settings).name == name


def test_llm_without_key_and_unknown_provider_fail_fast():
    with pytest.raises(UnknownProviderError):
        build_provider(Settings(triage_provider="llm", groq_api_key=None))
    with pytest.raises(UnknownProviderError):
        build_provider(Settings(triage_provider="gpt-9"))


def test_redis_outage_fails_open_instead_of_500():
    dead = redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2)
    assert RateLimiter(dead, limit=1, window_s=60).hit("1.2.3.4").allowed is True
    cache = StatsCache(dead, ttl_s=30)
    assert cache.get() is None
    cache.set({"total": 1})
    cache.invalidate()
    recorder = TriageRecorder(dead)
    recorder.record({"x": 1})
    assert recorder.recent() == [] and recorder.cache_counts() == (0, 0)
