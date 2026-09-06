"""Deterministic live-journey projection for the UI.

``JourneyReader`` reads SQLite and returns one learner-facing snapshot of a root
journey: identity and state, its units, the live stack position, the semantic graph,
lifecycle overview, conversation, evidence references, learner notes, and a monotonic
projection revision. It performs no routing, no agent calls, and never mutates state. A
failed read must never roll back tutoring state.

The archive reader returns the same snapshot shape for completed journeys, so the UI has
one contract for both (proposal §12–13).
"""
from __future__ import annotations

import json
from typing import Any

from .config import TutorConfig
from .db import Database
from .errors import ValidationError

SNAPSHOT_VERSION = 2

# Backend axis names → learner-facing wording (UI copy layer, spec §4.4).
AXIS_WORDING = {
    "COMPREHEND": "What it does",
    "MECHANISM": "How it works",
    "RATIONALE": "Why it was designed this way",
    "JUDGMENT": "When to use it",
    "ROBUSTNESS": "What can break",
    "INTEGRATION": "How it connects",
    "EVOLUTION": "How to improve it",
}


class JourneyReader:
    """Read-only projection of one root journey from live SQLite state."""

    def __init__(self, db: Database, config: TutorConfig) -> None:
        self.db = db
        self.config = config

    def current_revision(self, journey_id: int) -> int:
        row = self.db.one("SELECT projection_revision FROM journeys WHERE id=?", (journey_id,))
        if not row:
            raise ValidationError("journey does not exist")
        return int(row["projection_revision"])

    def read(self, journey_id: int, *, after_revision: int | None = None) -> dict[str, Any] | None:
        """Return the snapshot, or ``None`` if ``after_revision`` is already current.

        The ``None`` short-circuit lets a polling transport skip unchanged journeys
        without shipping a full projection every tick.
        """
        journey = self.db.one("SELECT * FROM journeys WHERE id=?", (journey_id,))
        if not journey:
            raise ValidationError("journey does not exist")
        revision = int(journey["projection_revision"])
        if after_revision is not None and revision <= after_revision:
            return None

        unit_ids = self._journey_unit_ids(int(journey["root_unit_id"]))
        return {
            "snapshot_version": SNAPSHOT_VERSION,
            "source": "live",
            "journey": {
                "id": journey["id"], "root_unit_id": journey["root_unit_id"],
                "state": journey["state"], "projection_revision": revision,
                "started_at": journey["started_at"], "completed_at": journey["completed_at"],
            },
            "units": self._units(unit_ids),
            "stack": self._stack(),
            "axes": self._axes(unit_ids),
            "semantic_nodes": self.db.query(
                "SELECT * FROM semantic_nodes WHERE journey_id=? ORDER BY id", (journey_id,)),
            "semantic_edges": self.db.query(
                "SELECT * FROM semantic_edges WHERE journey_id=? ORDER BY id", (journey_id,)),
            "lifecycle": self.db.query(
                "SELECT * FROM journey_events WHERE journey_id=? ORDER BY id", (journey_id,)),
            "conversation": self._conversation(journey_id),
            "aside_threads": self.db.query(
                "SELECT id,journey_id,unit_id,origin_message_id,title,created_at "
                "FROM aside_threads WHERE journey_id=? ORDER BY id", (journey_id,)),
            "aside_turns": self.db.query(
                "SELECT id,journey_id,thread_id,status,learner_message_id,reply_message_id,"
                "anchor_event_id,created_at,completed_at FROM aside_turns WHERE journey_id=? "
                "ORDER BY created_at,id", (journey_id,)),
            "evidence": {
                "probes": self.db.query(
                    "SELECT * FROM probes WHERE session_id=? AND unit_id IN (%s) ORDER BY id"
                    % self._placeholders(unit_ids),
                    (self.config.session_id, *unit_ids)) if unit_ids else [],
                "events": self.db.query(
                    "SELECT id,unit_id,axis,kind,revision_hash,created_at FROM events "
                    "WHERE session_id=? AND unit_id IN (%s) ORDER BY id"
                    % self._placeholders(unit_ids),
                    (self.config.session_id, *unit_ids)) if unit_ids else [],
            },
            "learner_notes": self.db.query(
                "SELECT * FROM learner_notes WHERE journey_id=? ORDER BY id", (journey_id,)),
            "tool_calls": self.db.query(
                "SELECT id,unit_id,turn_id,step,agent,capability,arguments_json,refused,ordinal,created_at "
                "FROM tool_calls WHERE journey_id=? ORDER BY id", (journey_id,)),
            "axis_wording": AXIS_WORDING,
        }

    # -- internals ----------------------------------------------------------------

    def _conversation(self, journey_id: int) -> list[dict[str, Any]]:
        """Conversation rows in global order, each with its refs decoded from JSON.

        thread_kind / thread_id ride along from SELECT * so a client can group aside
        threads; refs is the decoded list a client renders as highlight chips.
        """
        rows = self.db.query(
            "SELECT * FROM conversation_messages WHERE journey_id=? ORDER BY sequence",
            (journey_id,))
        for row in rows:
            row["refs"] = json.loads(row.get("refs_json") or "[]")
        return rows

    def _journey_unit_ids(self, root_unit_id: int) -> list[int]:
        """All units in this journey: the root plus every descendant child (BFS)."""
        collected = [root_unit_id]
        frontier = [root_unit_id]
        while frontier:
            placeholders = self._placeholders(frontier)
            rows = self.db.query(
                f"SELECT id FROM units WHERE session_id=? AND parent_id IN ({placeholders})",
                (self.config.session_id, *frontier),
            )
            children = [int(row["id"]) for row in rows]
            collected.extend(children)
            frontier = children
        return collected

    def _units(self, unit_ids: list[int]) -> list[dict[str, Any]]:
        if not unit_ids:
            return []
        return self.db.query(
            f"SELECT id,slug,title,file,lo,hi,ordinal,depth,parent_id,anchor_kind,state "
            f"FROM units WHERE id IN ({self._placeholders(unit_ids)}) ORDER BY ordinal",
            tuple(unit_ids),
        )

    def _axes(self, unit_ids: list[int]) -> list[dict[str, Any]]:
        if not unit_ids:
            return []
        return self.db.query(
            f"SELECT * FROM axes WHERE unit_id IN ({self._placeholders(unit_ids)}) ORDER BY unit_id,ordinal",
            tuple(unit_ids),
        )

    def _stack(self) -> list[dict[str, Any]]:
        rows = self.db.query(
            "SELECT unit_id,depth,resume_q,pending_json,hop_budget,is_top FROM stack "
            "WHERE session_id=? ORDER BY depth",
            (self.config.session_id,),
        )
        for row in rows:
            row["pending"] = json.loads(row.pop("pending_json"))
        return rows

    @staticmethod
    def _placeholders(values: list[int]) -> str:
        return ",".join("?" for _ in values)
