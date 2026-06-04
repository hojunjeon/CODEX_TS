from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
import hashlib
import sqlite3
import time


@dataclass(frozen=True)
class CaptureRecord:
    id: int
    tool: str
    command: str
    text: str
    sha256: str
    bytes: int
    lines: int


class ContextStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS captures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at REAL NOT NULL,
                    tool TEXT NOT NULL,
                    command TEXT NOT NULL,
                    text TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    bytes INTEGER NOT NULL,
                    lines INTEGER NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_captures_sha ON captures(sha256)")

    def capture(self, tool: str, text: str, command: str = "") -> CaptureRecord:
        encoded = text.encode("utf-8", errors="replace")
        digest = hashlib.sha256(encoded).hexdigest()
        line_count = len(text.splitlines())
        with self._connection() as conn:
            existing = conn.execute("SELECT * FROM captures WHERE sha256 = ? ORDER BY id LIMIT 1", (digest,)).fetchone()
            if existing is not None:
                return _record(existing)
            cur = conn.execute(
                """
                INSERT INTO captures(created_at, tool, command, text, sha256, bytes, lines)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (time.time(), tool, command, text, digest, len(encoded), line_count),
            )
            capture_id = int(cur.lastrowid)
        return CaptureRecord(capture_id, tool, command, text, digest, len(encoded), line_count)

    def get(self, capture_id: int) -> CaptureRecord:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM captures WHERE id = ?", (capture_id,)).fetchone()
        if row is None:
            raise KeyError(f"capture not found: {capture_id}")
        return _record(row)

    def preview(self, capture_id: int, lines: int = 20) -> str:
        record = self.get(capture_id)
        all_lines = record.text.splitlines()
        if len(all_lines) <= lines:
            return record.text
        head = "\n".join(all_lines[:lines])
        return f"{head}\n[ccts] preview only. Use ctx://capture/{capture_id} to retrieve full text."

    def search(self, query: str, limit: int = 10) -> list[CaptureRecord]:
        terms = [term.lower() for term in query.split() if len(term) > 1]
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM captures ORDER BY id DESC LIMIT 500").fetchall()
        scored: list[tuple[int, CaptureRecord]] = []
        for row in rows:
            record = _record(row)
            haystack = f"{record.tool} {record.command} {record.text}".lower()
            score = sum(haystack.count(term) for term in terms)
            if score:
                scored.append((score, record))
        scored.sort(key=lambda item: (-item[0], -item[1].id))
        return [record for _, record in scored[:limit]]


def _record(row: sqlite3.Row) -> CaptureRecord:
    return CaptureRecord(
        id=int(row["id"]),
        tool=str(row["tool"]),
        command=str(row["command"]),
        text=str(row["text"]),
        sha256=str(row["sha256"]),
        bytes=int(row["bytes"]),
        lines=int(row["lines"]),
    )

