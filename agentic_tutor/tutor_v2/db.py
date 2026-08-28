"""SQLite bootstrap, migrations, transactions, and cross-table invariants."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
import threading
from typing import Iterator

from .errors import InvariantError

SCHEMA_VERSION = 6
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class Database:
    """The sole SQLite connection for a local tutor session.

    This layer knows storage mechanics and invariant checking only. Routing,
    agent packets, archive files, and SDK code are deliberately absent.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._transaction_depth = 0
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 5000")
        if self.path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
        self._initialize()

    def _initialize(self) -> None:
        with self._lock:
            self._connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            current = self._connection.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()[0]
            if current is None:
                current = 0
            if current > SCHEMA_VERSION:
                raise RuntimeError(
                    f"database schema {current} is newer than supported {SCHEMA_VERSION}"
                )
            for version in range(current + 1, SCHEMA_VERSION + 1):
                self._apply_migration(version)
                self._connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (?)", (version,)
                )
            self._connection.commit()

    def _apply_migration(self, version: int) -> None:
        if version == 1:
            return
        if version == 2:
            self._migrate_events_to_monotonic_ids()
            return
        if version == 3:
            self._migrate_routing_order_and_anchors()
            return
        if version == 4:
            # The additive journey-layer tables are created idempotently by schema.sql
            # (executescript runs on every init), so no transform is required here.
            return
        if version == 5:
            # Per-axis tag on semantic nodes. schema.sql (run by executescript above)
            # already creates the column on fresh DBs, so ignore "duplicate column".
            try:
                self._connection.execute("ALTER TABLE semantic_nodes ADD COLUMN axis TEXT")
            except sqlite3.OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    raise
            return
        if version == 6:
            # Tool-call capture (observability). The additive tool_calls table is created
            # idempotently by schema.sql (executescript runs on every init), so no
            # transform is required here — fresh AND existing DBs both gain the table.
            return
        raise RuntimeError(f"no migration implementation for schema {version}")

    def _migrate_events_to_monotonic_ids(self) -> None:
        """Rebuild the v1 events table so event IDs are never reused after archival."""
        row = self._connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='events'"
        ).fetchone()
        if not row or "AUTOINCREMENT" in row[0].upper():
            return
        self._connection.execute("DROP INDEX IF EXISTS idx_events_session_unit")
        self._connection.execute("ALTER TABLE events RENAME TO events_v1")
        self._connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self._connection.execute(
            """
            INSERT INTO events(id,session_id,unit_id,axis,document_id,kind,payload_json,
                               result_json,revision_hash,created_at)
            SELECT id,session_id,unit_id,axis,document_id,kind,payload_json,
                   result_json,revision_hash,created_at
            FROM events_v1
            """
        )
        self._connection.execute("DROP TABLE events_v1")

    def _migrate_routing_order_and_anchors(self) -> None:
        """Add stable mapper ordering and the conceptual/code child distinction."""
        unit_columns = {row[1] for row in self._connection.execute("PRAGMA table_info(units)")}
        if "ordinal" not in unit_columns:
            self._connection.execute(
                "ALTER TABLE units ADD COLUMN ordinal INTEGER NOT NULL DEFAULT 0"
            )
            self._connection.execute("UPDATE units SET ordinal=id WHERE ordinal=0")
        if "anchor_kind" not in unit_columns:
            self._connection.execute(
                "ALTER TABLE units ADD COLUMN anchor_kind TEXT NOT NULL DEFAULT 'code'"
            )
        axis_columns = {row[1] for row in self._connection.execute("PRAGMA table_info(axes)")}
        if "ordinal" not in axis_columns:
            self._connection.execute(
                "ALTER TABLE axes ADD COLUMN ordinal INTEGER NOT NULL DEFAULT 0"
            )
            self._connection.execute("UPDATE axes SET ordinal=id WHERE ordinal=0")
        self._connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_units_session_ordinal ON units(session_id, ordinal)"
        )
        self._connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_axes_unit_ordinal ON axes(unit_id, ordinal)"
        )

    @property
    def connection(self) -> sqlite3.Connection:
        """Read-only escape hatch for tests; application code uses methods below."""
        return self._connection

    def query(self, sql: str, params: tuple[object, ...] = ()) -> list[dict]:
        with self._lock:
            return [dict(row) for row in self._connection.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple[object, ...] = ()) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> sqlite3.Cursor:
        """Execute one statement and check invariants before committing it."""
        with self.transaction():
            return self._connection.execute(sql, params)

    @contextmanager
    def transaction(self) -> Iterator["Database"]:
        """Commit only when all SQLite and cross-table ownership rules hold."""
        with self._lock:
            outermost = self._transaction_depth == 0
            savepoint = f"tutor_v2_{self._transaction_depth}"
            if outermost:
                self._connection.execute("BEGIN IMMEDIATE")
            else:
                self._connection.execute(f"SAVEPOINT {savepoint}")
            self._transaction_depth += 1
            try:
                yield self
                if outermost:
                    self._verify_invariants()
                    self._connection.commit()
                else:
                    self._connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            except Exception:
                if outermost:
                    self._connection.rollback()
                else:
                    self._connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    self._connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                raise
            finally:
                self._transaction_depth -= 1

    def _verify_invariants(self) -> None:
        """Rules SQLite CHECK constraints cannot express across separate stones."""
        both_homes = self._connection.execute(
            """
            SELECT h.session_id
            FROM handoff AS h
            JOIN stack AS s ON s.session_id = h.session_id
            WHERE h.parked_stack = 1
            GROUP BY h.session_id
            """
        ).fetchall()
        if both_homes:
            raise InvariantError(
                "a parked stack cannot exist in both live stack and handoff"
            )

        too_many_tops = self._connection.execute(
            """
            SELECT session_id FROM stack WHERE is_top = 1
            GROUP BY session_id HAVING COUNT(*) > 1
            """
        ).fetchall()
        if too_many_tops:
            raise InvariantError("a live session may have only one top stack frame")

    def close(self) -> None:
        with self._lock:
            self._connection.close()
