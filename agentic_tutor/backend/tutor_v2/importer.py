"""Git-URL codebase import (additive).

Clones a public https git repo into ``CODEBASE_ROOT`` so it can be registered exactly like any
directory that already lived on the host. This module owns *no* engine or learning logic — it
only fetches bytes onto disk and returns the resulting path; registration still goes through the
existing ``ControlPlane.create_codebase`` seam. Kept import-time dependency-free (stdlib only).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from .errors import ValidationError

# A cloner runs the fetch. Injected in tests so the clone path is covered without a network.
Cloner = Callable[[str, Path, float], None]


def validate_git_url(url: str) -> str:
    """Accept only plain public https URLs. Reject credentials and internal/link-local hosts."""
    candidate = (url or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValidationError("git_url must be an https:// URL")
    if parsed.username or parsed.password:
        raise ValidationError("credentials in git_url are not allowed")
    host = parsed.hostname.lower()
    blocked = host in {"localhost", "0.0.0.0", "::1"} or host.endswith(".local") \
        or host.startswith("127.") or host.startswith("169.254.") or host.startswith("10.") \
        or host.startswith("192.168.")
    if blocked:
        raise ValidationError("git_url host is not allowed")
    return candidate


def _slug(name: str) -> str:
    kept = "".join(ch if (ch.isalnum() or ch in "._-") else "-" for ch in name.strip())
    return kept.strip("-.")[:40] or "repo"


def _git_clone(url: str, target: Path, timeout: float) -> None:
    """Shallow, non-interactive clone. No credential prompts, no submodules, no history."""
    env = {
        "GIT_TERMINAL_PROMPT": "0",  # never block waiting for a username/password
        "GIT_ASKPASS": "/bin/false",
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", "/tmp"),
    }
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch", "--no-tags", "--", url, str(target)],
        check=True, capture_output=True, timeout=timeout, env=env,
    )


def clone_repository(*, git_url: str, dest_root: Path, name: str,
                     timeout: float = 120.0, cloner: Cloner = _git_clone) -> Path:
    """Validate + clone ``git_url`` into a fresh unique dir under ``dest_root``; return that dir.

    The target is a per-import unique subdirectory, re-resolved and checked to be strictly inside
    ``dest_root`` (defence against traversal even if the slug misbehaves). On any failure the
    partial directory is removed so a retry starts clean.
    """
    url = validate_git_url(git_url)
    root = dest_root.resolve()
    target = (root / f"{_slug(name)}-{uuid.uuid4().hex[:8]}").resolve()
    if not target.is_relative_to(root):
        raise ValidationError("resolved import path escapes CODEBASE_ROOT")
    root.mkdir(parents=True, exist_ok=True)
    try:
        cloner(url, target, timeout)
    except subprocess.TimeoutExpired as exc:
        shutil.rmtree(target, ignore_errors=True)
        raise ValidationError("git clone timed out") from exc
    except subprocess.CalledProcessError as exc:
        shutil.rmtree(target, ignore_errors=True)
        raise ValidationError("git clone failed (check the URL is a public repo)") from exc
    if not target.is_dir():
        raise ValidationError("git clone produced no directory")
    shutil.rmtree(target / ".git", ignore_errors=True)  # drop VCS metadata; we only teach the tree
    return target
