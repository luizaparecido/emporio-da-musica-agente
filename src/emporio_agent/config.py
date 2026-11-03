"""Configuração do projeto, lida de variáveis de ambiente (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

STORE_TZ = ZoneInfo("America/Campo_Grande")
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MODELS = {
    "anthropic": "claude-opus-5-5",
    "gemini": "gemini-3.8-flash",
}


class Clock:
    """Relógio injetável: fixo quando AGENT_NOW está definido, real caso contrário."""

    def __init__(self, fixed: datetime | None = None) -> None:
        self._fixed = fixed

    def now(self) -> datetime:
        return self._fixed or datetime.now(STORE_TZ)


@dataclass(frozen=True)
class Settings:
    provider: str
    model: str
    anthropic_effort: str
    data_dir: Path
    prompts_dir: Path
    db_path: Path
    clock: Clock


def _parse_now(raw: str | None) -> datetime | None:
    if not raw:
        return None
    parsed = datetime.fromisoformat(raw)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=STORE_TZ)


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    provider = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()
    if provider not in DEFAULT_MODELS:
        raise ValueError(f"LLM_PROVIDER inválido: {provider!r}. Use anthropic ou gemini.")
    return Settings(
        provider=provider,
        model=os.getenv("LLM_MODEL") or DEFAULT_MODELS[provider],
        anthropic_effort=os.getenv("ANTHROPIC_EFFORT", "low"),
        data_dir=Path(os.getenv("AGENT_DATA_DIR", PROJECT_ROOT / "data")),
        prompts_dir=PROJECT_ROOT / "prompts",
        db_path=Path(os.getenv("AGENT_DB_PATH", PROJECT_ROOT / "var" / "agent.sqlite3")),
        clock=Clock(_parse_now(os.getenv("AGENT_NOW"))),
    )
