"""Contrato comum entre o agente e os provedores de LLM.

As mensagens são dicts opacos no formato de cada provedor. O agente só as guarda e devolve,
o que preserva blocos de raciocínio e assinaturas que precisam voltar sem alteração.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class StopReason(StrEnum):
    END = "end"
    TOOL_USE = "tool_use"
    REFUSAL = "refusal"
    MAX_TOKENS = "max_tokens"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    name: str
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0


@dataclass(frozen=True)
class LLMResponse:
    text: str
    stop_reason: StopReason
    assistant_message: dict
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


class LLMError(Exception):
    """Falha do provedor. `user_action` diz o que o operador pode fazer, quando há o que fazer."""

    def __init__(self, message: str, user_action: str | None = None) -> None:
        super().__init__(message)
        self.user_action = user_action


class LLMClient(Protocol):
    provider: str
    model: str

    def generate(self, system: str, tools: list[ToolSpec], messages: list[dict]) -> LLMResponse: ...

    def user_message(self, text: str) -> dict: ...

    def tool_results_message(self, results: list[ToolResult]) -> dict: ...
