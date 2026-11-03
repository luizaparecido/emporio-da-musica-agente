"""Valida os adaptadores contra os tipos reais dos SDKs, sem rede."""

from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from anthropic.types.beta import BetaMessage
from google.genai import errors, types

from emporio_agent.llm.anthropic_client import AnthropicClient
from emporio_agent.llm.base import LLMError, StopReason, ToolResult, ToolSpec
from emporio_agent.llm.gemini_client import GeminiClient

TOOLS = [ToolSpec("get_store_status", "Status", {"type": "object", "properties": {}})]


def anthropic_message(content, stop_reason="end_turn"):
    return BetaMessage.model_validate(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 7},
        }
    )


class StubAnthropic:
    def __init__(self, outcome):
        self.kwargs = None
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self._outcome = outcome

    def _create(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def test_anthropic_request_shape():
    stub = StubAnthropic(anthropic_message([{"type": "text", "text": "Oi"}]))
    AnthropicClient("claude-opus-5-5", effort="low", client=stub).generate("sys", TOOLS, [{"role": "user", "content": "x"}])
    assert stub.kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert stub.kwargs["output_config"] == {"effort": "low"}
    assert stub.kwargs["fallbacks"] == "default" and stub.kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert stub.kwargs["tools"][0]["input_schema"] == {"type": "object", "properties": {}}
    assert "tool_choice" not in stub.kwargs and "thinking" not in stub.kwargs


def test_anthropic_model_without_fallback_support_omits_it():
    stub = StubAnthropic(anthropic_message([{"type": "text", "text": "Oi"}]))
    AnthropicClient("claude-haiku-5-5", client=stub).generate("sys", TOOLS, [])
    assert "fallbacks" not in stub.kwargs and "betas" not in stub.kwargs


def test_anthropic_replays_thinking_blocks_unchanged():
    thinking = {"type": "thinking", "thinking": "", "signature": "assinatura"}
    tool_use = {"type": "tool_use", "id": "t1", "name": "get_store_status", "input": {}}
    response = AnthropicClient("m", client=StubAnthropic(None)).parse_response(
        anthropic_message([thinking, tool_use], "tool_use")
    )
    assert response.stop_reason is StopReason.TOOL_USE
    assert response.tool_calls[0].id == "t1"
    assert response.assistant_message["content"][0] == thinking
    assert response.assistant_message["content"][1]["id"] == "t1"
    assert response.usage.cached_input_tokens == 7


def test_anthropic_refusal_is_not_read_as_content():
    response = AnthropicClient("m", client=StubAnthropic(None)).parse_response(anthropic_message([], "refusal"))
    assert response.stop_reason is StopReason.REFUSAL and response.assistant_message == {}


def test_anthropic_tool_results_go_in_one_message():
    message = AnthropicClient("m", client=StubAnthropic(None)).tool_results_message(
        [ToolResult("a", "x", "{}"), ToolResult("b", "y", "{}", is_error=True)]
    )
    assert message["role"] == "user" and [b["tool_use_id"] for b in message["content"]] == ["a", "b"]
    assert message["content"][1]["is_error"] is True


def test_anthropic_billing_error_is_surfaced_with_api_message():
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(400, request=request)
    error = anthropic.BadRequestError(
        "x", response=response, body={"error": {"message": "Your credit balance is too low"}}
    )
    client = AnthropicClient("m", client=StubAnthropic(error))
    with pytest.raises(LLMError, match="credit balance"):
        client.generate("sys", TOOLS, [])


# --- Gemini -----------------------------------------------------------------
def gemini_response(parts, finish="STOP"):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=parts), finish_reason=finish)],
        usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=10, candidates_token_count=5),
    )


class StubGemini:
    def __init__(self, outcome=None):
        self.kwargs = None
        self._outcome = outcome
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def test_gemini_request_uses_manual_tool_loop_and_validated_history():
    stub = StubGemini(gemini_response([types.Part(text="Oi")]))
    client = GeminiClient("gemini-x", client=stub)
    response = client.generate("sys", TOOLS, [client.user_message("Olá")])
    assert response.text == "Oi" and response.stop_reason is StopReason.END
    config = stub.kwargs["config"]
    assert config.automatic_function_calling.disable is True
    assert config.tools[0].function_declarations[0].parameters_json_schema == TOOLS[0].parameters
    assert stub.kwargs["contents"][0].parts[0].text == "Olá"


def test_gemini_preserves_thought_signature_through_json():
    call = types.FunctionCall(id="c1", name="get_store_status", args={})
    response = GeminiClient("m", client=StubGemini()).parse_response(
        gemini_response([types.Part(function_call=call, thought_signature=b"\x00\xff")])
    )
    assert response.stop_reason is StopReason.TOOL_USE and response.tool_calls[0].id == "c1"
    restored = types.Content.model_validate(response.assistant_message)
    assert restored.parts[0].thought_signature == b"\x00\xff"


def test_gemini_ignores_thought_text():
    response = GeminiClient("m", client=StubGemini()).parse_response(
        gemini_response([types.Part(text="pensando", thought=True), types.Part(text="Resposta")])
    )
    assert response.text == "Resposta"


def test_gemini_blocked_response_is_refusal():
    response = GeminiClient("m", client=StubGemini()).parse_response(gemini_response([], finish="SAFETY"))
    assert response.stop_reason is StopReason.REFUSAL


def test_gemini_tool_results_become_function_responses():
    client = GeminiClient("m", client=StubGemini())
    message = client.tool_results_message([ToolResult("c1", "x", '{"a": 1}'), ToolResult("c2", "y", "falhou", is_error=True)])
    restored = types.Content.model_validate(message)
    assert restored.parts[0].function_response.response == {"a": 1}
    assert restored.parts[1].function_response.response == {"error": "falhou"}


def test_gemini_client_error_becomes_llm_error():
    error = errors.ClientError(400, {"error": {"code": 400, "message": "ruim", "status": "INVALID"}})
    with pytest.raises(LLMError, match="ruim"):
        GeminiClient("m", client=StubGemini(error)).generate("sys", TOOLS, [])
