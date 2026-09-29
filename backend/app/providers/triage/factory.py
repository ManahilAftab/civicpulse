"""Select the primary triage provider from TRIAGE_PROVIDER."""

from app.config import Settings
from app.providers.triage.base import TriageProvider
from app.providers.triage.llm import LLMTriage, OllamaTriage
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage


class UnknownProviderError(ValueError):
    pass


def build_provider(settings: Settings) -> TriageProvider:
    choice = settings.triage_provider.strip().lower()
    if choice == "llm":
        if settings.groq_api_key is None:
            raise UnknownProviderError("TRIAGE_PROVIDER=llm requires GROQ_API_KEY")
        return LLMTriage(
            base_url=settings.groq_base_url,
            api_key=settings.groq_api_key.get_secret_value(),
            model=settings.groq_model,
            timeout_s=settings.triage_timeout_s,
        )
    if choice == "ollama":
        return OllamaTriage(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_s=settings.triage_timeout_s,
        )
    if choice == "rules":
        return RuleBasedTriage()
    if choice == "simulated":
        return SimulatedTriage(
            seed=settings.simulated_seed, failure_rate=settings.simulated_failure_rate
        )
    raise UnknownProviderError(
        f"Unknown TRIAGE_PROVIDER={settings.triage_provider!r}; "
        "expected llm | ollama | rules | simulated"
    )
