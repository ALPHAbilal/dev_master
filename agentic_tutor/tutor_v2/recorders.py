"""Additive, orchestrator-owned recorders for the durable journey layer.

None of these touch the engine's authoritative stones (units, axes, stack, meta).
They write only the journey-layer tables, and every method wraps its writes in
``db.transaction()`` so it composes as a savepoint inside the orchestrator's outer
atomic boundary. Agents never receive these objects.
"""
from __future__ import annotations

import json
from typing import Any

from .config import TutorConfig
from .db import Database
from .domain import ToolCall
from .errors import InvariantError, ValidationError


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class ConversationRecorder:
    """The only writer of the learner-facing conversation transcript."""

    _ROLES = frozenset({"learner", "tutor", "tool", "system"})
    _STATUSES = frozenset({"RECORDED", "AWAITING_EVALUATION", "EVALUATED"})

    def __init__(self, db: Database, config: TutorConfig) -> None:
        self.db = db
        self.config = config

    def record(
        self,
        *,
        journey_id: int,
        unit_id: int,
        role: str,
        message_kind: str,
        content: str,
        turn_id: str,
        axis: str | None = None,
        status: str = "RECORDED",
        source_wakeup_step: str | None = None,
    ) -> int:
        if role not in self._ROLES:
            raise ValidationError(f"unsupported message role: {role}")
        if status not in self._STATUSES:
            raise ValidationError(f"unsupported message status: {status}")
        if not message_kind.strip() or not turn_id.strip():
            raise ValidationError("message_kind and turn_id are required")
        with self.db.transaction():
            sequence = int(self.db.connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM conversation_messages WHERE journey_id=?",
                (journey_id,),
            ).fetchone()[0])
            cursor = self.db.connection.execute(
                "INSERT INTO conversation_messages(journey_id,unit_id,axis,role,message_kind,content,"
                "turn_id,sequence,status,source_wakeup_step) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (journey_id, unit_id, axis, role, message_kind, content, turn_id, sequence,
                 status, source_wakeup_step),
            )
        return int(cursor.lastrowid)

    def set_turn_status(self, *, journey_id: int, turn_id: str, status: str) -> None:
        if status not in self._STATUSES:
            raise ValidationError(f"unsupported message status: {status}")
        with self.db.transaction():
            self.db.connection.execute(
                "UPDATE conversation_messages SET status=? WHERE journey_id=? AND turn_id=?",
                (status, journey_id, turn_id),
            )

    def list_for_journey(self, journey_id: int) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT * FROM conversation_messages WHERE journey_id=? ORDER BY sequence",
            (journey_id,),
        )

    def find_learner_answer(self, *, journey_id: int, turn_id: str) -> dict[str, Any] | None:
        """Return an already-recorded learner answer for this turn, if any (replay guard)."""
        return self.db.one(
            "SELECT * FROM conversation_messages WHERE journey_id=? AND turn_id=? AND role='learner'",
            (journey_id, turn_id),
        )


class ToolCallRecorder:
    """Best-effort capture of what tools the model actually called during one agent wakeup."""

    def __init__(self, db: Database, config: TutorConfig) -> None:
        self.db = db
        self.config = config

    def record(self, *, journey_id: int, unit_id: int | None, turn_id: str, step: str,
               agent: str, tool_calls: list["ToolCall"]) -> None:
        if not tool_calls:
            return
        with self.db.transaction():
            # Idempotent under crash-recovery replay: this (journey, turn) was already
            # captured, so re-recording it would duplicate the rows. Skip — the rest of
            # the turn is likewise idempotent.
            already = self.db.connection.execute(
                "SELECT 1 FROM tool_calls WHERE journey_id=? AND turn_id=? LIMIT 1",
                (journey_id, turn_id),
            ).fetchone()
            if already:
                return
            for tc in tool_calls:
                self.db.connection.execute(
                    "INSERT INTO tool_calls(journey_id,unit_id,turn_id,step,agent,capability,"
                    "arguments_json,refused,ordinal) VALUES(?,?,?,?,?,?,?,?,?)",
                    (journey_id, unit_id, turn_id, step, agent, tc.capability,
                     _json(tc.arguments), 1 if tc.refused else 0, tc.ordinal))


class ProbeRecorder:
    """Makes the already-defined probe history real, after evaluation succeeds."""

    _STEPS = frozenset({"probe", "test"})
    _VERDICTS = frozenset({"SOLID", "SHAKY", "MISSING"})

    def __init__(self, db: Database, config: TutorConfig) -> None:
        self.db = db
        self.config = config

    def record(
        self,
        *,
        turn: int,
        unit_id: int,
        axis: str,
        step: str,
        question: str,
        learner_answer: str,
        verdict: str,
        category: str,
    ) -> int:
        if step not in self._STEPS:
            raise ValidationError("probe step must be probe or test")
        if verdict not in self._VERDICTS:
            raise ValidationError("probe verdict must be SOLID, SHAKY, or MISSING")
        if turn <= 0:
            raise ValidationError("probe turn must be positive")
        if not question.strip() or not learner_answer.strip():
            raise ValidationError("probe requires a question and a learner answer")
        with self.db.transaction():
            cursor = self.db.connection.execute(
                "INSERT INTO probes(session_id,turn,unit_id,axis,step,question,learner_answer,verdict,category) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (self.config.session_id, turn, unit_id, axis, step, question, learner_answer,
                 verdict, category),
            )
        return int(cursor.lastrowid)

    def next_turn(self, unit_id: int) -> int:
        row = self.db.one(
            "SELECT COALESCE(MAX(turn), 0) + 1 AS turn FROM probes WHERE session_id=? AND unit_id=?",
            (self.config.session_id, unit_id),
        )
        return int(row["turn"]) if row else 1


class JourneyRecorder:
    """Owns journey identity, lifecycle facts, and the projection revision counter."""

    _STATES = frozenset({"LIVE", "PARKED", "OWNED"})

    def __init__(self, db: Database, config: TutorConfig) -> None:
        self.db = db
        self.config = config

    def start(self, root_unit_id: int) -> int:
        """Create the journey for a newly pointed root unit, or return the existing one."""
        with self.db.transaction():
            existing = self.db.connection.execute(
                "SELECT id FROM journeys WHERE session_id=? AND root_unit_id=?",
                (self.config.session_id, root_unit_id),
            ).fetchone()
            if existing:
                return int(existing["id"])
            cursor = self.db.connection.execute(
                "INSERT INTO journeys(session_id,root_unit_id) VALUES(?,?)",
                (self.config.session_id, root_unit_id),
            )
            return int(cursor.lastrowid)

    def journey_for_unit(self, unit_id: int) -> int:
        """Resolve the journey a unit belongs to by walking to its root unit."""
        root_id = self._root_of(unit_id)
        row = self.db.one(
            "SELECT id FROM journeys WHERE session_id=? AND root_unit_id=?",
            (self.config.session_id, root_id),
        )
        if not row:
            raise InvariantError("unit has no journey; start it when the root is pointed")
        return int(row["id"])

    def record_event(
        self,
        *,
        journey_id: int,
        unit_id: int,
        event_type: str,
        parent_unit_id: int | None = None,
        axis: str | None = None,
        payload: dict[str, Any] | None = None,
        message_refs: list[int] | None = None,
        probe_refs: list[int] | None = None,
        action_event_refs: list[int] | None = None,
        source_ref: dict[str, Any] | None = None,
        workspace_revision: int | None = None,
        workspace_hash: str | None = None,
    ) -> int:
        if not event_type.strip():
            raise ValidationError("event_type is required")
        with self.db.transaction():
            cursor = self.db.connection.execute(
                "INSERT INTO journey_events(journey_id,unit_id,parent_unit_id,axis,event_type,payload_json,"
                "message_refs_json,probe_refs_json,action_event_refs_json,source_ref_json,"
                "workspace_revision,workspace_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (journey_id, unit_id, parent_unit_id, axis, event_type, _json(payload or {}),
                 _json(message_refs or []), _json(probe_refs or []), _json(action_event_refs or []),
                 _json(source_ref) if source_ref is not None else None,
                 workspace_revision, workspace_hash),
            )
        return int(cursor.lastrowid)

    def set_state(self, journey_id: int, state: str, *, completed: bool = False) -> None:
        if state not in self._STATES:
            raise ValidationError(f"unsupported journey state: {state}")
        completed_clause = ",completed_at=datetime('now')" if completed else ""
        with self.db.transaction():
            self.db.connection.execute(
                f"UPDATE journeys SET state=?,updated_at=datetime('now'){completed_clause} WHERE id=?",
                (state, journey_id),
            )

    def bump_revision(self, journey_id: int) -> int:
        with self.db.transaction():
            self.db.connection.execute(
                "UPDATE journeys SET projection_revision=projection_revision+1,updated_at=datetime('now') WHERE id=?",
                (journey_id,),
            )
            row = self.db.connection.execute(
                "SELECT projection_revision FROM journeys WHERE id=?", (journey_id,)
            ).fetchone()
        if not row:
            raise InvariantError("cannot bump a projection revision for a missing journey")
        return int(row["projection_revision"])

    def get(self, journey_id: int) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM journeys WHERE id=?", (journey_id,))
        if not row:
            raise InvariantError("journey does not exist")
        return row

    def _root_of(self, unit_id: int) -> int:
        seen: set[int] = set()
        current = unit_id
        while True:
            if current in seen:
                raise InvariantError("unit parent chain is cyclic")
            seen.add(current)
            row = self.db.one(
                "SELECT parent_id FROM units WHERE id=? AND session_id=?",
                (current, self.config.session_id),
            )
            if not row:
                raise ValidationError("unit does not belong to this session")
            if row["parent_id"] is None:
                return current
            current = int(row["parent_id"])
