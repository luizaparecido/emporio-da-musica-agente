"""Escolhe o adaptador conforme a configuração."""

from __future__ import annotations

from emporio_agent.config import Settings
from emporio_agent.llm.base import LLMClient


def build_llm(settings: Settings) -> LLMClient:
    # Imports locais: quem usa um provedor não precisa carregar o SDK do outro.
    if settings.provider == "anthropic":
        from emporio_agent.llm.anthropic_client import AnthropicClient

        return AnthropicClient(settings.model, effort=settings.anthropic_effort)

    from emporio_agent.llm.gemini_client import GeminiClient

    return GeminiClient(settings.model)
