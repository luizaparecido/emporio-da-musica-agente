"""Executa os casos contra o LLM real e relata acertos por caso.

Uso: python -m evals.run [--only id1,id2] [--output evals/results/anthropic.md]
Cada execução consome créditos do provedor configurado e usa um banco temporário.
"""

from __future__ import annotations

import argparse
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from emporio_agent.agent.factory import build_agent
from emporio_agent.agent.loop import Agent, AgentReply
from emporio_agent.config import load_settings
from emporio_agent.data.repository import StoreRepository
from emporio_agent.domain.models import Customer
from emporio_agent.llm.base import LLMError
from evals.cases import CASES, Case


@dataclass
class CaseResult:
    case: Case
    failures: list[str]
    replies: list[AgentReply]

    @property
    def passed(self) -> bool:
        return not self.failures


def check(case: Case, replies: list[AgentReply]) -> list[str]:
    """Regras são avaliadas sobre a conversa inteira, ignorando maiúsculas."""
    called = {step.name for reply in replies for step in reply.tool_trace}
    text = "\n".join(reply.text for reply in replies)
    lowered = text.casefold()
    failures = []
    failures += [f"não chamou {t}" for t in sorted(case.required_tools - called)]
    if case.required_any_tools and not case.required_any_tools & called:
        failures.append(f"não chamou nenhuma de {sorted(case.required_any_tools)}")
    failures += [f"chamou {t} indevidamente" for t in sorted(case.forbidden_tools & called)]
    failures += [f"faltou '{s}'" for s in case.must_contain if s.casefold() not in lowered]
    failures += [f"citou '{s}'" for s in case.must_not_contain if s.casefold() in lowered]
    if case.must_contain_any and not any(s.casefold() in lowered for s in case.must_contain_any):
        failures.append(f"faltou uma de {case.must_contain_any}")
    if any(reply.fallback_used for reply in replies):
        failures.append("caiu na resposta de contingência")
    return failures


def _resolve(text: str, customer_14: Customer) -> str:
    return text.replace("{phone_14}", customer_14.phone_digits)


def run_case(agent: Agent, case: Case, customer_14: Customer) -> CaseResult:
    replies = [agent.reply(case.id, _resolve(turn, customer_14)) for turn in case.turns]
    return CaseResult(case, check(case, replies), replies)


def render_report(results: list[CaseResult], provider: str, model: str) -> str:
    passed = sum(r.passed for r in results)
    lines = [
        f"# Resultado dos evals: {provider}/{model}",
        "",
        f"**{passed}/{len(results)} casos aprovados.**",
        "",
        "| Caso | Resultado | Tools | Falhas |",
        "| --- | --- | --- | --- |",
    ]
    for result in results:
        tools = ", ".join(step.name for reply in result.replies for step in reply.tool_trace) or "-"
        status = "OK" if result.passed else "FALHOU"
        lines.append(f"| {result.case.id} | {status} | {tools} | {'; '.join(result.failures) or '-'} |")
    lines += ["", "## Conversas", ""]
    for result in results:
        lines += [f"### {result.case.id}", ""]
        for turn, reply in zip(result.case.turns, result.replies):
            lines += [f"**Cliente:** {turn}", "", f"**Tom:** {reply.text}", ""]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="IDs de casos separados por vírgula.")
    parser.add_argument("--output", type=Path, help="Grava o relatório em markdown.")
    args = parser.parse_args()

    only = set(args.only.split(",")) if args.only else None
    cases = [c for c in CASES if not only or c.id in only]
    settings = load_settings()
    with tempfile.TemporaryDirectory() as tmp:
        settings = replace(settings, db_path=Path(tmp) / "evals.sqlite3")
        agent = build_agent(settings)
        customer_14 = StoreRepository.from_csv(settings.data_dir).customers[14]
        results: list[CaseResult] = []
        interrupted = False
        for case in cases:
            try:
                result = run_case(agent, case, customer_14)
            except LLMError as exc:
                # Cotas podem acabar no meio: o que já rodou continua no relatório.
                print(f"Erro do provedor, avaliação interrompida em {case.id}: {str(exc)[:200]}")
                interrupted = True
                break
            print(f"{'OK    ' if result.passed else 'FALHOU'} {case.id} {result.failures or ''}")
            results.append(result)

    report = render_report(results, settings.provider, settings.model)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    print(f"\n{sum(r.passed for r in results)}/{len(results)} aprovados de {len(cases)} casos")
    if interrupted:
        return 2
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
