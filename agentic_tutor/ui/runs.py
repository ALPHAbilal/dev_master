"""runs — every survey is archived, never overwritten.

A re-survey used to mean wiping the database by hand, which threw away the only thing
you can judge a new spine against: the old one. Instead:

    archive(db, label)   copy the whole DB file to .tutor/runs/<stamp>-<label>.db
    reset_spine(db)      clear slices + concepts (target and evidence stay)
    history(db)          the archived runs, newest first, with their spine sizes

So the flow on a second survey is archive -> reset -> run. Nothing is ever lost, and
two runs of the same codebase sit side by side for comparison.

Pure stdlib. The archive is a plain SQLite file: open it with any client.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from tutor.db import DB


class ArchiveError(Exception):
    """The run could not be archived. Nothing was cleared."""


def runs_dir(db: DB) -> Path:
    """Sibling of the live DB: <db parent>/runs/. In-memory DBs have no archive."""
    if db.path == ":memory:":
        raise ArchiveError("an in-memory session has no file to archive")
    return Path(db.path).resolve().parent / "runs"


def archive(db: DB, label: str = "survey") -> Path:
    """Snapshot the live DB. Returns the archive path."""
    dest_dir = runs_dir(db)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = dest_dir / f"{stamp}-{_slug(label)}.db"
    # sqlite's own backup API: consistent even with the connection open, unlike cp
    with sqlite3.connect(dest) as out:
        db.conn.backup(out)
    return dest


def reset_spine(db: DB) -> dict:
    """Clear the map so a fresh survey can draw a new one. Target and probes survive.

    Deliberately NOT a gateway op: it destroys M's work wholesale, which no agent may
    ever do. Only the human, through the interface, and only right after an archive.
    """
    counts = {"slices": len(db.query("SELECT 1 FROM slices")),
              "concepts": len(db.query("SELECT 1 FROM concepts")),
              "gates": len(db.query("SELECT 1 FROM gates"))}
    db.execute("DELETE FROM gates")
    db.execute("DELETE FROM slices")
    db.execute("DELETE FROM concepts")
    return counts


def history(db: DB) -> list[dict]:
    """Archived runs, newest first: when, what model, how big a spine."""
    try:
        d = runs_dir(db)
    except ArchiveError:
        return []
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("*.db"), reverse=True):
        out.append({"file": p.name, "label": _label_of(p.name),
                    "when": _when_of(p.name), **_sizes(p)})
    return out


# --------------------------------------------------------------------------
def _sizes(path: Path) -> dict:
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            n = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                 for t in ("slices", "concepts")}
        finally:
            con.close()
        return n
    except sqlite3.Error:
        return {"slices": 0, "concepts": 0}


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-") or "run"


def _label_of(name: str) -> str:
    parts = name[:-3].split("-", 2)
    return parts[2] if len(parts) > 2 else name[:-3]


def _when_of(name: str) -> str:
    try:
        return datetime.strptime(name[:15], "%Y%m%d-%H%M%S").strftime("%d %b %H:%M")
    except ValueError:
        return ""
