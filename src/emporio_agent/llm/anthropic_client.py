"""Adaptador para a API do Claude, com loop manual de tools."""

from __future__ import annotations

import anthropic

from emporio_agent.llm.base import (
    LLMError,
    LLMResponse,
    StopReason,
    ToolCall,
    ToolResult,
    ToolSpec,
    Usage,
)

MAX_TOKENS = 16000
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MODELS_WITH_DEFAULT_FALLBACK = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
STOP_REASONS = {
    "tool_use": StopReason.TOOL_USE,
    "refusal": StopReason.REFUSAL,
    "max_tokens": StopReason.MAX_TOKENS,
}


class AnthropicClient:
    provider = "anthropic"

    def __init__(self, model: str, effort: str = "low", client: anthropic.Anthropic | None = None) -> None:
        self.model = model
        self._effort = effort
        self._client = client or anthropic.Anthropic()

    def user_message(self, text: str) -> dict:
        return {"role": "user", "content": text}

    def tool_results_message(self, results: list[ToolResult]) -> dict:
        # Todos os resultados vão na mesma mensagem, como a API espera em chamadas paralelas.
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": r.call_id,
                    "content": r.content,
                    "is_error": r.is_error,
                }
                for r in results
            ],
        }

    def request_params(self, system: str, tools: list[ToolSpec], messages: list[dict]) -> dict:
        params: dict = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            # O bloco fixo fica em cache. O cache automático cobre também o histórico.
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "cache_control": {"type": "ephemeral"},
            "tools": [
                {"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools
            ],
            "messages": messages,
            "output_config": {"effort": self._effort},
        }
        if self.model in MODELS_WITH_DEFAULT_FALLBACK:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        return params

    def generate(self, system: str, tools: list[ToolSpec], messages: list[dict]) -> LLMResponse:
        params = self.request_params(system, tools, messages)
        try:
            response = self._client.beta.messages.create(**params)
        except anthropic.AuthenticationError as exc:
            raise LLMError("Chave da Anthropic inválida.", "Confira ANTHROPIC_API_KEY no .env.") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("Limite de requisições da Anthropic atingido.", "Tente de novo em instantes.") from exc
        except anthropic.BadRequestError as exc:
            detail = exc.body.get("error", {}).get("message", str(exc)) if isinstance(exc.body, dict) else str(exc)
            raise LLMError(f"A API da Anthropic recusou a requisição: {detail}") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Erro {exc.status_code} na API da Anthropic.", "Tente de novo em instantes.") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Sem conexão com a API da Anthropic.", "Verifique a rede.") from exc
        return self.parse_response(response)

    def parse_response(self, response) -> LLMResponse:
        stop_reason = STOP_REASONS.get(response.stop_reason, StopReason.END)
        if stop_reason is StopReason.REFUSAL:
            return LLMResponse(text="", stop_reason=stop_reason, assistant_message={})
        blocks = response.content
        usage = response.usage
        return LLMResponse(
            text="".join(b.text for b in blocks if b.type == "text"),
            stop_reason=stop_reason,
            # to_dict devolve os blocos como vieram, incluindo os de raciocínio.
            assistant_message={"role": "assistant", "content": [b.to_dict() for b in blocks]},
            tool_calls=[ToolCall(b.id, b.name, dict(b.input)) for b in blocks if b.type == "tool_use"],
            usage=Usage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cached_input_tokens=usage.cache_read_input_tokens or 0,
            ),
        )
