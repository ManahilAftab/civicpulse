"""OllamaTriage: fully offline triage via a local model in the Compose stack.

Ollama exposes an OpenAI-compatible endpoint, so this reuses the same prompt,
guardrails and error mapping as LLMTriage. No key, no rate limit, no PII leaves
the host — slower on CPU and weaker at classification (the buy-vs-host trade-off).
"""

from typing import Any

from app.domain import TriagedBy
from app.providers.triage.llm import OpenAICompatibleTriage


class OllamaTriage(OpenAICompatibleTriage):
    """Offline path: a local model in the Compose stack. No key, no PII leaves the host."""

    def __init__(
        self, *, base_url: str, model: str, timeout_s: float, client: Any | None = None
    ) -> None:
        super().__init__(
            name=TriagedBy.LLM_OLLAMA.value,
            base_url=base_url,
            api_key="ollama",
            model=model,
            timeout_s=timeout_s,
            client=client,
        )
