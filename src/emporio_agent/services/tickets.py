"""Registro de reclamações e encaminhamentos para a equipe (manual §7.3 e §10)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    summary TEXT NOT NULL,
    contact TEXT,
    order_id INTEGER,
    created_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Ticket:
    protocol: str
    kind: str


class TicketService:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(SCHEMA)

    def open(
        self,
        session_id: str,
        kind: str,
        summary: str,
        created_at: datetime,
        contact: str | None = None,
        order_id: int | None = None,
    ) -> Ticket:
        cursor = self._conn.execute(
            "INSERT INTO tickets (session_id, kind, summary, contact, order_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, kind, summary, contact, order_id, created_at.isoformat()),
        )
        self._conn.commit()
        return Ticket(protocol=f"EM-{cursor.lastrowid:05d}", kind=kind)
