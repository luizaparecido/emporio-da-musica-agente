"""Carrega o system prompt e monta o contexto dinâmico de cada turno."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from emporio_agent.services.store_hours import store_status
from emporio_agent.tools.presenters import format_moment

CONTEXT_TAG = "contexto_do_sistema"


def load_system_prompt(prompts_dir: Path) -> str:
    return (prompts_dir / "system.md").read_text(encoding="utf-8")


def build_user_turn(customer_text: str, now: datetime) -> str:
    """Data e hora ficam no turno, não no system prompt, para não invalidar o cache.

    A tag é removida do texto do cliente para ele não conseguir se passar pelo sistema.
    """
    sanitized = customer_text.replace(f"<{CONTEXT_TAG}>", "").replace(f"</{CONTEXT_TAG}>", "")
    status = store_status(now)
    situation = "loja aberta" if status.is_open else "loja fechada"
    if status.next_opening:
        situation += f", reabre {format_moment(status.next_opening)}"
    return (
        f"<{CONTEXT_TAG}>Agora: {format_moment(now)} de {now.year}, {situation}.</{CONTEXT_TAG}>\n"
        f"{sanitized}"
    )
