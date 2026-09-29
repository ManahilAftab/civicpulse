"""Application settings, read from environment variables only.

Nothing here has a real credential as a default. Hostnames default to Compose
service names (`database`, `cache`, `ollama`) — never localhost, because inside a
container localhost is the container itself.
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Infrastructure
    database_url: str = "postgresql+psycopg://civicpulse:change-me@database:5432/civicpulse"
    redis_url: str = "redis://cache:6379/0"

    # Triage provider selection: llm | ollama | rules | simulated
    triage_provider: str = "llm"
    triage_timeout_s: float = 10.0
    triage_cache_ttl_s: int = 24 * 60 * 60
    triage_retry_jitter_min_s: float = 0.5
    triage_retry_jitter_max_s: float = 1.5

    # Groq (OpenAI-compatible). The key is a SecretStr so it never appears in repr/logs.
    groq_api_key: SecretStr | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.1-8b-instant"

    # Ollama (OpenAI-compatible endpoint exposed by the ollama container)
    ollama_base_url: str = "http://ollama:11434/v1"
    ollama_model: str = "llama3.2:1b"

    # SimulatedTriage (CI): deterministic, seeded, with optional failure injection
    simulated_seed: int = 42
    simulated_failure_rate: float = 0.0

    # Stats cache and rate limiting
    stats_cache_ttl_s: int = 30
    rate_limit_requests: int = 10
    rate_limit_window_s: int = 60
    # nginx sets X-Real-IP. Only trust it when the backend is unreachable except via nginx.
    trust_proxy_headers: bool = True

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
