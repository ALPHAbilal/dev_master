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
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """In-place fixes for databases created by an older schema.

        vocab.status -> vocab.state: the mismatch between `vocab.status` and
        `concepts.state`/`slices.state` made an agent guess wrong twelve times in one
        run. CREATE TABLE IF NOT EXISTS leaves an existing table alone, so a DB from
        before the rename still has the old column and must be carried over.
        """
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(vocab)")}
        if "status" in cols and "state" not in cols:
            self.conn.execute("ALTER TABLE vocab RENAME COLUMN status TO state")

        # v2 map columns: probes.level, concepts.review_due/review_streak. ADD COLUMN
        # is safe on an old table; the probes kind-CHECK, however, is baked into the
        # table SQL, so an old probes table must be rebuilt to accept the new kinds.
        pcols = {r[1] for r in self.conn.execute("PRAGMA table_info(probes)")}
        if pcols and "level" not in pcols:
            self.conn.execute("ALTER TABLE probes ADD COLUMN level INTEGER")
        ccols = {r[1] for r in self.conn.execute("PRAGMA table_info(concepts)")}
        if ccols and "review_due" not in ccols:
            self.conn.execute("ALTER TABLE concepts ADD COLUMN review_due TEXT")
            self.conn.execute(
                "ALTER TABLE concepts ADD COLUMN review_streak INTEGER NOT NULL DEFAULT 0")
        # legacy single-cell subhole -> a row on the new stack
        scols = {r[1] for r in self.conn.execute("PRAGMA table_info(slices)")}
        if "subhole_concept" in scols:
            for r in self.conn.execute(
                    "SELECT slug, subhole_concept, subhole_evidence FROM slices "
                    "WHERE subhole_concept IS NOT NULL").fetchall():
                self.conn.execute(
                    "INSERT INTO subholes(slice_slug,concept_slug,evidence) VALUES(?,?,?)",
                    (r[0], r[1], r[2] or "(migrated)"))
                self.conn.execute(
                    "UPDATE slices SET subhole_concept=NULL, subhole_evidence=NULL "
                    "WHERE slug=?", (r[0],))

        row = self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='probes'").fetchone()
        if row and "'entry'" not in row[0]:
            self.conn.executescript("""
                ALTER TABLE probes RENAME TO probes_old;
            """)
            self.conn.executescript(SCHEMA_PATH.read_text())   # recreate probes fresh
            self.conn.execute("""
                INSERT INTO probes(id,concept_slug,kind,result,pushes,self_corrected,
                                   error_class,reveals,terms,note,created_at,level)
                SELECT id,concept_slug,kind,result,pushes,self_corrected,
                       error_class,reveals,terms,note,created_at,level FROM probes_old""")
            self.conn.execute("DROP TABLE probes_old")

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
