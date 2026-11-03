"""LLM roteirizado para testar o loop sem rede."""

from __future__ import annotations

from emporio_agent.llm.base import LLMResponse, StopReason, ToolCall, ToolResult, ToolSpec


def final(text: str) -> LLMResponse:
    return LLMResponse(
        text=text, stop_reason=StopReason.END, assistant_message={"role": "assistant", "content": text}
    )


def call(name: str, /, **arguments) -> LLMResponse:
    return LLMResponse(
        text="",
        stop_reason=StopReason.TOOL_USE,
        assistant_message={"role": "assistant", "content": f"call:{name}"},
        tool_calls=[ToolCall(id=f"id-{name}", name=name, arguments=arguments)],
    )


class ScriptedLLM:
    provider = "fake"
    model = "fake-1"

    def __init__(self, script: list) -> None:
        self.script = list(script)
        self.seen_messages: list[list[dict]] = []

    def generate(self, system: str, tools: list[ToolSpec], messages: list[dict]) -> LLMResponse:
        self.seen_messages.append(list(messages))
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def user_message(self, text: str) -> dict:
        return {"role": "user", "content": text}

    def tool_results_message(self, results: list[ToolResult]) -> dict:
        return {"role": "user", "content": [r.content for r in results]}
