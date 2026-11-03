"""Registro de tools: schema gerado do pydantic, validação e erro devolvido ao modelo."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from emporio_agent.llm.base import ToolSpec


@dataclass(frozen=True)
class ToolOutcome:
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[Any, str], dict]
    schema_patch: Callable[[dict], None] | None = None

    def spec(self) -> ToolSpec:
        schema = self.args_model.model_json_schema()
        _strip_titles(schema)
        if self.schema_patch:
            self.schema_patch(schema)
        return ToolSpec(name=self.name, description=self.description, parameters=schema)


def _strip_titles(node: Any) -> None:
    """Títulos gerados pelo pydantic só gastam tokens. Nenhum argumento se chama title."""
    if isinstance(node, dict):
        node.pop("title", None)
        for value in node.values():
            _strip_titles(value)
    elif isinstance(node, list):
        for value in node:
            _strip_titles(value)


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def specs(self) -> list[ToolSpec]:
        return [tool.spec() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict, session_id: str) -> ToolOutcome:
        tool = self._tools.get(name)
        if tool is None:
            return ToolOutcome(_dump({"erro": f"Tool desconhecida: {name}"}), is_error=True)
        try:
            args = tool.args_model.model_validate(arguments)
        except ValidationError as exc:
            problems = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
            return ToolOutcome(_dump({"erro": "Argumentos inválidos", "detalhes": problems}), is_error=True)
        return ToolOutcome(_dump(tool.handler(args, session_id)))


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)
