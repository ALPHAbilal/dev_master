"""State-machine merge of a distill ``learner_diff`` into the persistent learner profile.

The learner profile is the ONLY memory that survives across codebases. This service applies a
validated ``return.distill.learner_diff`` so the ``can``/``cant`` lists always reflect the
present: a newly proven skill moves out of ``cant`` and into ``can``; a gap is recorded; a
disproved misconception is marked (kept for history, never dropped). A proven ``can`` is never
removed — there is no regression in v1.

It reads no agent text and makes no judgment: it only merges an already-validated diff, and it
is the only writer of the ``learner`` table.
"""
from __future__ import annotations

import json
from typing import Any

from .config import TutorConfig
from .db import Database


def _default_profile() -> dict[str, Any]:
    return {"can": [], "cant": [], "misconceptions": []}


class LearnerModelService:
    """Deterministic, idempotent writer of the cross-codebase learner profile."""

    def __init__(self, db: Database, config: TutorConfig) -> None:
        self.db = db
        self.config = config

    def read(self) -> dict[str, Any]:
        """Return the current profile, filling any missing list with an empty one."""
        row = self.db.one(
            "SELECT profile_json FROM learner WHERE learner_id=?", (self.config.learner_id,)
        )
        profile = _default_profile()
        if row:
            stored = json.loads(row["profile_json"])
            if isinstance(stored, dict):
                profile.update({key: stored.get(key, profile[key]) for key in profile})
        return profile

    def apply_diff(self, learner_diff: dict[str, Any]) -> dict[str, Any]:
        """Merge one validated distill diff and persist the result (idempotent).

        - ``can``:  union(existing, diff.can), de-duplicated, order preserved.
        - ``cant``: union(existing, diff.cant) minus anything now proven (moved to ``can``).
        - ``misconceptions``: upsert by belief; each diff entry is marked ``disproved`` with its
          ``disproved_by`` evidence. Existing entries are kept — history is never lost.
        """
        profile = self.read()
        can = list(dict.fromkeys([*profile["can"], *learner_diff.get("can", [])]))
        proven = set(can)
        cant = [
            item
            for item in dict.fromkeys([*profile["cant"], *learner_diff.get("cant", [])])
            if item not in proven
        ]
        misconceptions = self._merge_misconceptions(
            profile["misconceptions"], learner_diff.get("misconceptions", [])
        )
        merged = {"can": can, "cant": cant, "misconceptions": misconceptions}
        self._write(merged)
        return merged

    @staticmethod
    def _merge_misconceptions(
        existing: list[dict[str, Any]], incoming: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        by_belief: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for item in existing:
            belief = item["belief"]
            if belief not in by_belief:
                order.append(belief)
            by_belief[belief] = dict(item)
        for item in incoming:
            belief = item["belief"]
            if belief not in by_belief:
                order.append(belief)
                by_belief[belief] = {"belief": belief}
            by_belief[belief]["disproved_by"] = item["disproved_by"]
            by_belief[belief]["status"] = "disproved"
        return [by_belief[belief] for belief in order]

    def _write(self, profile: dict[str, Any]) -> None:
        payload = json.dumps(profile, sort_keys=True, separators=(",", ":"))
        with self.db.transaction():
            self.db.connection.execute(
                "INSERT INTO learner(learner_id,profile_json) VALUES(?,?) "
                "ON CONFLICT(learner_id) DO UPDATE SET profile_json=excluded.profile_json,"
                "updated_at=datetime('now')",
                (self.config.learner_id, payload),
            )
