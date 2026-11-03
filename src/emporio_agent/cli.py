"""Interface de linha de comando do agente."""

from __future__ import annotations

import argparse
import uuid

from rich.console import Console
from rich.markup import escape

from emporio_agent.agent.factory import build_agent
from emporio_agent.agent.loop import AgentReply, SessionProviderMismatch
from emporio_agent.config import load_settings
from emporio_agent.llm.base import LLMError

EXIT_WORDS = {"sair", "exit", "quit"}


def _print_trace(console: Console, reply: AgentReply) -> None:
    for step in reply.tool_trace:
        console.print(f"  [dim]tool: {step.name}({escape(str(step.arguments))})[/dim]")
    usage = reply.usage
    console.print(
        f"  [dim]tokens: {usage.input_tokens} entrada, {usage.cached_input_tokens} do cache, "
        f"{usage.output_tokens} saída; revisões do guardrail: {reply.guardrail_retries}[/dim]"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Converse com o Tom, atendente da Empório da Música.")
    parser.add_argument("--session", help="ID da conversa. Repita o mesmo ID para retomá-la.")
    parser.add_argument("--debug", action="store_true", help="Mostra tools chamadas e consumo de tokens.")
    args = parser.parse_args()

    console = Console()
    settings = load_settings()
    session_id = args.session or uuid.uuid4().hex[:8]
    agent = build_agent(settings)
    console.print(f"[bold]Empório da Música[/bold] · sessão [cyan]{session_id}[/cyan] · {settings.provider}/{settings.model}")
    console.print(f"[dim]Digite 'sair' para encerrar. Para retomar: --session {session_id}[/dim]\n")

    while True:
        try:
            text = console.input("[bold green]Você:[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            return
        if not text:
            continue
        if text.casefold() in EXIT_WORDS:
            return
        try:
            with console.status("Tom está digitando..."):
                reply = agent.reply(session_id, text)
        except SessionProviderMismatch as exc:
            console.print(f"[red]{escape(str(exc))}[/red]")
            return
        except LLMError as exc:
            hint = f" {exc.user_action}" if exc.user_action else ""
            console.print(f"[red]Erro do provedor: {escape(str(exc))}{escape(hint)}[/red]\n")
            continue
        console.print(f"[bold blue]Tom:[/bold blue] {escape(reply.text)}")
        if args.debug:
            _print_trace(console, reply)
        console.print()


if __name__ == "__main__":
    main()
