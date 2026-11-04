"""Adaptador para a API do Gemini (SDK google-genai)."""

from __future__ import annotations

import json

from google import genai
from google.genai import errors, types

from emporio_agent.llm.base import (
    LLMError,
    LLMResponse,
    StopReason,
    ToolCall,
    ToolResult,
    ToolSpec,
    Usage,
)

REQUEST_TIMEOUT_MS = 60_000
RETRY_OPTIONS = types.HttpRetryOptions(attempts=5, initial_delay=2.0, http_status_codes=[429, 500, 503, 504])
BLOCKED_FINISH_REASONS = {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}


def _dump(content: types.Content) -> dict:
    return content.model_dump(mode="json", exclude_none=True)


class GeminiClient:
    provider = "gemini"

    def __init__(self, model: str, client: genai.Client | None = None) -> None:
        self.model = model
        self._client = client or genai.Client(
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS, retry_options=RETRY_OPTIONS)
        )

    def user_message(self, text: str) -> dict:
        return _dump(types.Content(role="user", parts=[types.Part(text=text)]))

    def tool_results_message(self, results: list[ToolResult]) -> dict:
        parts = [
            types.Part(
                function_response=types.FunctionResponse(
                    id=r.call_id or None,
                    name=r.name,
                    response={"error": r.content} if r.is_error else json.loads(r.content),
                )
            )
            for r in results
        ]
        return _dump(types.Content(role="user", parts=parts))

    def request_config(self, system: str, tools: list[ToolSpec]) -> types.GenerateContentConfig:
        declarations = [
            types.FunctionDeclaration(name=t.name, description=t.description, parameters_json_schema=t.parameters)
            for t in tools
        ]
        return types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(function_declarations=declarations)],
            # Quem executa as tools é o nosso loop, igual ao provedor Anthropic.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

    def generate(self, system: str, tools: list[ToolSpec], messages: list[dict]) -> LLMResponse:
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=[types.Content.model_validate(m) for m in messages],
                config=self.request_config(system, tools),
            )
        except errors.ClientError as exc:
            raise LLMError(f"A API do Gemini recusou a requisição ({exc.code}): {exc.message}") from exc
        except errors.APIError as exc:
            raise LLMError(f"Erro {exc.code} na API do Gemini.", "Tente de novo em instantes.") from exc
        return self.parse_response(response)

    def parse_response(self, response: types.GenerateContentResponse) -> LLMResponse:
        candidate = response.candidates[0] if response.candidates else None
        finish = candidate.finish_reason.name if candidate and candidate.finish_reason else None
        if candidate is None or candidate.content is None or finish in BLOCKED_FINISH_REASONS:
            return LLMResponse(text="", stop_reason=StopReason.REFUSAL, assistant_message={})

        parts = candidate.content.parts or []
        calls = [
            ToolCall(p.function_call.id or p.function_call.name, p.function_call.name, dict(p.function_call.args or {}))
            for p in parts
            if p.function_call
        ]
        if calls:
            stop_reason = StopReason.TOOL_USE
        elif finish == "MAX_TOKENS":
            stop_reason = StopReason.MAX_TOKENS
        else:
            stop_reason = StopReason.END
        metadata = response.usage_metadata
        return LLMResponse(
            text="".join(p.text for p in parts if p.text and not p.thought),
            stop_reason=stop_reason,
            assistant_message=_dump(candidate.content),
            tool_calls=calls,
            usage=Usage(
                input_tokens=(metadata.prompt_token_count or 0) if metadata else 0,
                output_tokens=(metadata.candidates_token_count or 0) if metadata else 0,
                cached_input_tokens=(metadata.cached_content_token_count or 0) if metadata else 0,
            ),
        )
