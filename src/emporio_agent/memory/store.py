"""Persistência das conversas em SQLite.

O histórico fica no formato nativo do provedor, em modo append-only: blocos de raciocínio e
assinaturas precisam voltar à API sem alteração. Por isso a sessão fica presa ao provedor.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    history TEXT NOT NULL,
    grounded_amounts TEXT NOT NULL,
    failed_verifications INTEGER NOT NULL DEFAULT 0
);
"""


@dataclass
class Session:
    id: str
    provider: str
    history: list[dict] = field(default_factory=list)
    grounded_amounts: set[str] = field(default_factory=set)


class SessionStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(SCHEMA)

    def load(self, session_id: str, provider: str) -> Session:
        row = self._conn.execute(
            "SELECT provider, history, grounded_amounts FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return Session(id=session_id, provider=provider)
        return Session(
            id=session_id,
            provider=row[0],
            history=json.loads(row[1]),
            grounded_amounts=set(json.loads(row[2])),
        )

    def save(self, session: Session) -> None:
        self._conn.execute(
            """
            INSERT INTO sessions (id, provider, history, grounded_amounts) VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                history = excluded.history, grounded_amounts = excluded.grounded_amounts
            """,
            (
                session.id,
                session.provider,
                json.dumps(session.history, ensure_ascii=False),
                json.dumps(sorted(session.grounded_amounts)),
            ),
        )
        self._conn.commit()

    def failed_verifications(self, session_id: str) -> int:
        row = self._conn.execute(
            "SELECT failed_verifications FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return row[0] if row else 0

    def record_failed_verification(self, session_id: str, provider: str) -> int:
        self._conn.execute(
            """
            INSERT INTO sessions (id, provider, history, grounded_amounts, failed_verifications)
            VALUES (?, ?, '[]', '[]', 1)
            ON CONFLICT(id) DO UPDATE SET failed_verifications = failed_verifications + 1
            """,
            (session_id, provider),
        )
        self._conn.commit()
        return self.failed_verifications(session_id)
