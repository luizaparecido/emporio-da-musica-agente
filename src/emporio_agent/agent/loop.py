"""Loop do agente: chama o LLM, executa tools e valida a resposta final.

A conversa só é gravada ao final de um turno bem-sucedido. Assim, uma falha de API ou
uma recusa não deixa o histórico em um estado que quebre a próxima mensagem.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from emporio_agent.agent.guardrails import extract_amounts, ungrounded_amounts
from emporio_agent.agent.prompt import build_user_turn
from emporio_agent.config import Clock
from emporio_agent.llm.base import LLMClient, LLMResponse, StopReason, ToolResult, Usage
from emporio_agent.memory.store import Session, SessionStore
from emporio_agent.tools.registry import ToolRegistry

MAX_STEPS = 8
MAX_GUARDRAIL_RETRIES = 1

HANDOFF_REPLY = (
    "Não consegui confirmar essa informação com segurança agora, e prefiro não te passar nada errado. "
    "Fala com a nossa equipe pelo (67) 3341-4444, de segunda a sexta das 9h às 18h e aos sábados das 9h às 13h."
)
REFUSAL_REPLY = (
    "Essa eu não consigo te ajudar por aqui. Se tiver alguma dúvida sobre instrumentos, pedidos ou a loja, é só falar!"
)
GUARDRAIL_CORRECTION = (
    "<contexto_do_sistema>Revisão automática: sua resposta citou valores que não vieram de nenhuma tool nem do "
    "cliente: {amounts}. Reescreva a resposta usando só valores devolvidos pelas tools. Consulte a tool adequada "
    "se precisar. Não comente esta revisão com o cliente.</contexto_do_sistema>"
)


class SessionProviderMismatch(Exception):
    """A sessão foi criada com outro provedor; o histórico nativo não é transferível."""


@dataclass(frozen=True)
class ToolTrace:
    name: str
    arguments: dict
    result: str
    is_error: bool


@dataclass
class AgentReply:
    text: str
    tool_trace: list[ToolTrace] = field(default_factory=list)
    guardrail_retries: int = 0
    fallback_used: bool = False
    usage: Usage = field(default_factory=Usage)


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        tools: ToolRegistry,
        sessions: SessionStore,
        system_prompt: str,
        clock: Clock,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._sessions = sessions
        self._system_prompt = system_prompt
        self._clock = clock
        self._specs = tools.specs()

    def reply(self, session_id: str, customer_text: str) -> AgentReply:
        session = self._sessions.load(session_id, self._llm.provider)
        if session.provider != self._llm.provider:
            raise SessionProviderMismatch(
                f"A sessão {session_id!r} usa o provedor {session.provider}. Inicie outra sessão."
            )
        session.grounded_amounts |= extract_amounts(customer_text)
        turn_text = build_user_turn(customer_text, self._clock.now())
        session.history.append(self._llm.user_message(turn_text))

        result = AgentReply(text="")
        guardrail_retries = 0
        for _ in range(MAX_STEPS):
            response = self._llm.generate(self._system_prompt, self._specs, session.history)
            result.usage = _add_usage(result.usage, response.usage)

            if response.stop_reason is StopReason.REFUSAL:
                result.text, result.fallback_used = REFUSAL_REPLY, True
                return result
            if response.stop_reason is StopReason.MAX_TOKENS:
                break

            session.history.append(response.assistant_message)
            if response.stop_reason is StopReason.TOOL_USE:
                self._run_tools(response, session, result)
                continue

            unknown = ungrounded_amounts(response.text, session.grounded_amounts)
            if not unknown and response.text.strip():
                result.text = response.text.strip()
                result.guardrail_retries = guardrail_retries
                self._sessions.save(session)
                return result
            if guardrail_retries >= MAX_GUARDRAIL_RETRIES:
                break
            guardrail_retries += 1
            correction = GUARDRAIL_CORRECTION.format(amounts=", ".join(sorted(unknown)) or "resposta vazia")
            session.history.append(self._llm.user_message(correction))

        result.text, result.fallback_used = HANDOFF_REPLY, True
        result.guardrail_retries = guardrail_retries
        return result

    def _run_tools(self, response: LLMResponse, session: Session, result: AgentReply) -> None:
        results: list[ToolResult] = []
        for call in response.tool_calls:
            outcome = self._tools.execute(call.name, call.arguments, session.id)
            session.grounded_amounts |= extract_amounts(outcome.content)
            results.append(ToolResult(call.id, call.name, outcome.content, outcome.is_error))
            result.tool_trace.append(ToolTrace(call.name, call.arguments, outcome.content, outcome.is_error))
        session.history.append(self._llm.tool_results_message(results))


def _add_usage(total: Usage, new: Usage) -> Usage:
    return Usage(
        input_tokens=total.input_tokens + new.input_tokens,
        output_tokens=total.output_tokens + new.output_tokens,
        cached_input_tokens=total.cached_input_tokens + new.cached_input_tokens,
    )
