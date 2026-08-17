"""session — adopting the target codebase. The FIRST act of any session.

Nothing in the tutor is hardcoded to a path: until a `target` row exists, the whole
interface is one screen asking for a codebase. Two ways in, one thing out:

    adopt_folder(db, path)   — survey the code where it already lives (nothing copied)
    adopt_zip(db, blob, ws)  — extract an uploaded .zip into a session workspace

Both normalize to a single absolute `session root` and commit it through the ONE
gateway (`set_target`) — the UI gets no side door into the DB (H1).

Pure Python, no SDK, no HTTP.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from tutor.db import DB
from tutor.gateway import dispatch

# never surfaced to the learner, never surveyed
IGNORED_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
                ".mypy_cache", ".pytest_cache", ".idea", ".claude", "dist", "build"}
# secrets never reach the screen or the survey agent — an adopted repo routinely has
# a .env sitting next to the code, and neither the learner's panel nor M's Read/Grep
# has any business in it.
IGNORED_NAMES = {".env", ".env.local", ".env.production", ".netrc", ".npmrc",
                 ".pypirc", "credentials.json", "id_rsa", ".htpasswd"}
IGNORED_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".keystore"}
MAX_ZIP_BYTES = 50 * 1024 * 1024        # a codebase, not a dataset


def is_secret(path: Path) -> bool:
    name = path.name
    return (name in IGNORED_NAMES
            or path.suffix in IGNORED_SUFFIXES
            or name.startswith(".env."))


class SessionError(Exception):
    """The codebase could not be adopted. Nothing was committed."""


# --------------------------------------------------------------------------
# adopting
# --------------------------------------------------------------------------
def adopt_folder(db: DB, path: str) -> str:
    """Adopt a directory in place. Returns the absolute session root."""
    root = Path(path).expanduser()
    if not root.exists():
        raise SessionError(f"no such folder: {path}")
    if not root.is_dir():
        raise SessionError(f"not a folder: {path}")
    root = root.resolve()
    if not _has_any_code(root):
        raise SessionError(f"{root} has no readable source files to survey")
    return _commit_target(db, root)


def adopt_zip(db: DB, blob: bytes, workspace: str, name: str = "upload") -> str:
    """Extract an uploaded zip into `workspace/<name>/`. Returns the session root."""
    if len(blob) > MAX_ZIP_BYTES:
        raise SessionError(f"zip is larger than {MAX_ZIP_BYTES // (1024*1024)}MB")
    dest = (Path(workspace).expanduser() / _safe_name(name)).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile as e:
        raise SessionError(f"not a readable zip: {e}")
    for member in zf.infolist():
        target = _safe_extract_path(dest, member.filename)
        if target is None:                      # zip-slip / absolute path — skip it
            continue
        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(zf.read(member))
    root = _descend_single_wrapper(dest)
    if not _has_any_code(root):
        raise SessionError("the zip contained no readable source files")
    return _commit_target(db, root)


def current_root(db: DB) -> str | None:
    row = db.one("SELECT codebase_path FROM target WHERE id=1")
    return row["codebase_path"] if row else None


def is_adopted(db: DB) -> bool:
    return current_root(db) is not None


# --------------------------------------------------------------------------
# the file tree the learner sees
# --------------------------------------------------------------------------
def file_tree(db: DB, limit: int = 400) -> list[dict]:
    """Flat, sorted, repo-relative listing + each file's gate/slice status.

    A file is marked HIS when a gate is OPEN on the slice that targets it — the same
    join the wall uses, so the tree can never disagree with what is actually enforced.
    """
    root = current_root(db)
    if not root:
        return []
    rootp = Path(root)
    targeted = {r["target_file"]: r for r in db.query(
        "SELECT s.target_file, s.slug, s.state, "
        "(SELECT state FROM gates g WHERE g.slice_slug=s.slug AND g.state='OPEN') AS gate "
        "FROM slices s")}
    out: list[dict] = []
    for p in sorted(rootp.rglob("*")):
        if any(part in IGNORED_DIRS for part in p.parts):
            continue
        if not p.is_file() or is_secret(p):
            continue
        rel = p.relative_to(rootp).as_posix()
        row = _match_target(targeted, rel)
        out.append({
            "path": rel,
            "slice": row["slug"] if row else None,
            "state": row["state"] if row else None,
            "gated": bool(row and row["gate"]),
        })
        if len(out) >= limit:
            break
    return out


# --------------------------------------------------------------------------
# internals
# --------------------------------------------------------------------------
def _commit_target(db: DB, root: Path) -> str:
    d = dispatch(db, "M", "set_target", {"codebase_path": str(root)})
    if not d.committed:
        raise SessionError(d.text)
    return str(root)


def _has_any_code(root: Path) -> bool:
    for p in root.rglob("*"):
        if (p.is_file() and not is_secret(p)
                and not any(part in IGNORED_DIRS for part in p.parts)):
            return True
    return False


def _safe_name(name: str) -> str:
    stem = Path(name).name or "upload"
    return "".join(c for c in stem if c.isalnum() or c in "-_.") or "upload"


def _safe_extract_path(dest: Path, member_name: str) -> Path | None:
    """Resolve a zip member under dest, or None if it would escape (zip-slip)."""
    if not member_name or member_name.startswith("/") or ".." in Path(member_name).parts:
        return None
    target = (dest / member_name).resolve()
    try:
        target.relative_to(dest)
    except ValueError:
        return None
    return target


def _descend_single_wrapper(dest: Path) -> Path:
    """GitHub-style zips wrap everything in one folder; survey the code, not the wrapper."""
    entries = [p for p in dest.iterdir() if p.name not in IGNORED_DIRS]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0].resolve()
    return dest


def _match_target(targeted: dict, rel: str) -> dict | None:
    if rel in targeted:
        return targeted[rel]
    for tf, row in targeted.items():             # slices may store a partial path
        if tf and (rel.endswith("/" + tf) or tf.endswith("/" + rel) or tf == rel):
            return row
    return None
