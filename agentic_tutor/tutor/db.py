"""SQLite connection + schema bootstrap for the agentic tutor.

Thin wrapper. All *meaning* lives in operations.py; this module only opens a
connection, applies schema.sql, and exposes row-dict helpers. No pedagogy here.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


class DB:
    """A single SQLite database, schema-initialized on open."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        # check_same_thread=False: an agent turn runs on a worker thread while the
        # interface reads state on the request thread. `lock` keeps those serialized —
        # SQLite allows the cross-thread handle, it does not make it concurrent.
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(SCHEMA_PATH.read_text())
        self.conn.commit()

    # --- tiny query helpers -------------------------------------------------
    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.lock:
            cur = self.conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def one(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    # --- meta kv ------------------------------------------------------------
    def meta_get(self, key: str, default=None):
        row = self.one("SELECT value FROM meta WHERE key = ?", (key,))
        return row["value"] if row else default

    def meta_set(self, key: str, value) -> None:
        self.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    def close(self) -> None:
        self.conn.close()
