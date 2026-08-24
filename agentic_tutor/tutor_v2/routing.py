"""Deterministic code→code routing and the live subhole stack.

This module never reads learner prose. It accepts only a validated Judge stamp,
stored state, and explicit parent bookmarks. Its result tells the caller which
ordinary wakeup to build next.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .config import TutorConfig
from .contracts import validate_return
from .db import Database
from .errors import InvariantError, ValidationError


@dataclass(frozen=True, slots=True)
class RouteDecision:
    next_step: str | None
    unit_id: int | None
    axis: str | None
    reason: str
    highlight: bool = False
    resume_question: str | None = None


class Router:
    """Owns state transitions, stack movement, and deterministic next wakeups."""

    def __init__(self, db: Database, config: TutorConfig) -> None:
        self.db = db
        self.config = config

    def commit_map(self, stamp: dict[str, Any]) -> RouteDecision:
        """Persist a validated Mapper batch and point the first available root unit."""
        stamp = validate_return(stamp)
        if stamp["kind"] != "return.map":
            raise ValidationError("commit_map requires return.map")
        with self.db.transaction():
            meta = self._meta()
            if meta["target"] != stamp["target"]:
                raise ValidationError("return.map target does not match the active session")
            existing = self.db.connection.execute(
                "SELECT COUNT(*) FROM units WHERE session_id=?", (self.config.session_id,)
            ).fetchone()[0]
            if stamp["mode"] == "initial" and existing:
                raise InvariantError("initial map cannot overwrite an existing ladder")
            if stamp["mode"] == "extend" and not existing:
                raise InvariantError("extend map requires an existing ladder")
            offset = self.db.connection.execute(
                "SELECT COALESCE(MAX(ordinal), -1) FROM units WHERE session_id=?",
                (self.config.session_id,),
            ).fetchone()[0] + 1
            for position, unit in enumerate(stamp["units"]):
                cursor = self.db.connection.execute(
                    "INSERT INTO units(session_id,slug,title,file,lo,hi,ordinal,depth,parent_id,anchor_kind,state) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?, 'NEW')",
                    (
                        self.config.session_id, unit["slug"], unit.get("title", unit["slug"]),
                        unit["file"], unit["lo"], unit["hi"], offset + position,
                        unit["depth"], None, "code",
                    ),
                )
                unit_id = int(cursor.lastrowid)
                for axis_position, axis in enumerate(unit["axes"]):
                    self.db.connection.execute(
                        "INSERT INTO axes(unit_id,axis,ordinal) VALUES(?,?,?)",
                        (unit_id, axis, axis_position),
                    )
            self.db.connection.execute(
                "UPDATE meta SET phase='LOOP',updated_at=datetime('now') WHERE session_id=?",
                (self.config.session_id,),
            )
            return self._point_next_root_locked()

    def record_resume_question(self, *, unit_id: int, question: str) -> None:
        """Persist the exact parent question before any possible child dive."""
        if not question.strip():
            raise ValidationError("resume question must not be blank")
        with self.db.transaction():
            frame = self._top_frame_locked()
            if frame["unit_id"] != unit_id:
                raise InvariantError("only the deepest unit may receive a resume question")
            self.db.connection.execute("UPDATE stack SET resume_q=? WHERE id=?", (question, frame["id"]))

    def route_grade(self, *, unit_id: int, stamp: dict[str, Any]) -> RouteDecision:
        """Apply a Judge verdict and select the next deterministic engine step."""
        stamp = validate_return(stamp)
        if stamp["kind"] != "return.grade":
            raise ValidationError("route_grade requires return.grade")
        with self.db.transaction():
            frame = self._top_frame_locked()
            if frame["unit_id"] != unit_id:
                raise InvariantError("only the deepest unit may be graded")
            axis_row = self.db.connection.execute(
                "SELECT * FROM axes WHERE unit_id=? AND axis=?", (unit_id, stamp["axis"])
            ).fetchone()
            if not axis_row:
                raise ValidationError("grade axis does not fire for the current unit")
            category = stamp["category"]
            if category == "disputes-verdict":
                return RouteDecision("wakeup.teach", unit_id, stamp["axis"], "show cited evidence")

            effective_verdict, shaky_count = self._effective_verdict(axis_row, stamp["verdict"])
            self.db.connection.execute(
                "UPDATE axes SET verdict=?,shaky_count=?,evidence_ref=?,updated_at=datetime('now') WHERE id=?",
                (effective_verdict, shaky_count, stamp["evidence_ref"], axis_row["id"]),
            )
            self.db.connection.execute(
                "UPDATE units SET state='JUDGED' WHERE id=?", (unit_id,))

            if category == "correct-deep" and effective_verdict == "SOLID":
                return self._advance_after_solid_locked(unit_id)
            if category in {"pattern-matched", "skip-request"}:
                self.db.connection.execute("UPDATE units SET state='TESTED' WHERE id=?", (unit_id,))
                return RouteDecision("wakeup.test", unit_id, stamp["axis"], "require harder proof")
            if category == "sibling-hole":
                self._queue_sibling_locked(frame, self._gap(stamp))
                self.db.connection.execute("UPDATE units SET state='TAUGHT' WHERE id=?", (unit_id,))
                return RouteDecision("wakeup.teach", unit_id, stamp["axis"], "queued non-blocking sibling")
            if category in {"misconception", "different-prereq"} or effective_verdict == "MISSING":
                return self._push_child_locked(frame, self._gap(stamp), "missing prerequisite")
            if category == "fatigue-switch":
                self.db.connection.execute("UPDATE units SET state='PARKED' WHERE id=?", (unit_id,))
                return RouteDecision("wakeup.distill", unit_id, stamp["axis"], "park requested")
            if category == "working-code-wrong-reasoning":
                mechanism = self._axis_or_raise_locked(unit_id, "MECHANISM")
                self.db.connection.execute("UPDATE units SET state='PROBED' WHERE id=?", (unit_id,))
                return RouteDecision("wakeup.probe", unit_id, mechanism["axis"], "probe mechanism reasoning")
            if category == "shaky":
                self.db.connection.execute("UPDATE units SET state='PROBED' WHERE id=?", (unit_id,))
                return RouteDecision("wakeup.probe", unit_id, stamp["axis"], "narrower probe")
            if category in {"confused-question", "different-axis", "off-topic", "gives-up", "silent-stuck"}:
                self.db.connection.execute("UPDATE units SET state='PROBED' WHERE id=?", (unit_id,))
                return RouteDecision("wakeup.probe", unit_id, stamp["axis"], "redirected probe")
            raise InvariantError(f"category {category} has no route")

    def resume_after_child(self, *, child_unit_id: int) -> RouteDecision:
        """Pop an OWNED child and replay the parent's exact paused question."""
        with self.db.transaction():
            child = self._unit_locked(child_unit_id)
            if child["state"] != "OWNED":
                raise InvariantError("only an OWNED child may return to its parent")
            frame = self._top_frame_locked()
            if frame["unit_id"] != child_unit_id or child["parent_id"] is None:
                raise InvariantError("active frame is not a returning child")
            parent_frame = self.db.connection.execute(
                "SELECT * FROM stack WHERE session_id=? AND unit_id=?",
                (self.config.session_id, child["parent_id"]),
            ).fetchone()
            if not parent_frame or not parent_frame["resume_q"]:
                raise InvariantError("cannot return without the parent's exact resume question")
            self.db.connection.execute("DELETE FROM stack WHERE id=?", (frame["id"],))
            self.db.connection.execute("UPDATE stack SET is_top=1 WHERE id=?", (parent_frame["id"],))
            self.db.connection.execute(
                "UPDATE meta SET current_unit_id=?,updated_at=datetime('now') WHERE session_id=?",
                (child["parent_id"], self.config.session_id),
            )
            self.db.connection.execute("UPDATE units SET state='PROBED' WHERE id=?", (child["parent_id"],))
            axis = self._next_unsolid_axis_locked(child["parent_id"])
            return RouteDecision("wakeup.probe", child["parent_id"], axis["axis"], "return to parent", resume_question=parent_frame["resume_q"])

    def finish_owned_unit(self, *, unit_id: int) -> RouteDecision:
        """Run after distillation has sealed an OWNED unit's proof.

        PARKED units intentionally do not use this method: Stage 9 moves their
        full live stack into handoff before any live frame is cleared.
        """
        with self.db.transaction():
            unit = self._unit_locked(unit_id)
            if unit["state"] != "OWNED":
                raise InvariantError("only an OWNED unit may finish its live frame")
            frame = self._top_frame_locked()
            if frame["unit_id"] != unit_id:
                raise InvariantError("only the deepest OWNED unit may finish")
            if unit["parent_id"] is not None:
                return self.resume_after_child(child_unit_id=unit_id)
            self.db.connection.execute("DELETE FROM stack WHERE id=?", (frame["id"],))
            self.db.connection.execute(
                "UPDATE meta SET current_unit_id=NULL,updated_at=datetime('now') WHERE session_id=?",
                (self.config.session_id,),
            )
            return self._point_next_root_locked()

    def _advance_after_solid_locked(self, unit_id: int) -> RouteDecision:
        unresolved_child = self.db.connection.execute(
            "SELECT id FROM units WHERE parent_id=? AND state NOT IN ('OWNED','PARKED') LIMIT 1",
            (unit_id,),
        ).fetchone()
        if unresolved_child:
            raise InvariantError("parent cannot become OWNED while a child is live")
        next_axis = self._next_unsolid_axis_locked(unit_id)
        if next_axis:
            self.db.connection.execute("UPDATE units SET state='POINTED' WHERE id=?", (unit_id,))
            return RouteDecision("wakeup.probe", unit_id, next_axis["axis"], "next firing axis", highlight=True)
        self.db.connection.execute("UPDATE units SET state='OWNED' WHERE id=?", (unit_id,))
        return RouteDecision("wakeup.distill", unit_id, None, "all firing axes solid")

    def _push_child_locked(self, parent_frame: Any, gap: dict[str, Any], reason: str) -> RouteDecision:
        parent = self._unit_locked(parent_frame["unit_id"])
        if not parent_frame["resume_q"]:
            raise InvariantError("a child dive requires the parent's saved exact question")
        anchor = gap["anchor"]
        if anchor["kind"] == "code":
            file, lo, hi = anchor["file"], anchor["lo"], anchor["hi"]
            highlight = True
        else:
            file, lo, hi = parent["file"], parent["lo"], parent["hi"]
            highlight = False
        duplicate = self.db.connection.execute(
            "SELECT id FROM units WHERE session_id=? AND slug=?", (self.config.session_id, gap["slug"])
        ).fetchone()
        if duplicate:
            raise InvariantError("a hidden-gap child slug already exists in this session")
        next_ordinal = self.db.connection.execute(
            "SELECT COALESCE(MAX(ordinal), -1) + 1 FROM units WHERE session_id=?", (self.config.session_id,)
        ).fetchone()[0]
        cursor = self.db.connection.execute(
            "INSERT INTO units(session_id,slug,title,file,lo,hi,ordinal,depth,parent_id,anchor_kind,state) "
            "VALUES(?,?,?,?,?,?,?,?,?,?, 'POINTED')",
            (self.config.session_id, gap["slug"], gap["why"], file, lo, hi, next_ordinal,
             parent["depth"] + 1, parent["id"], anchor["kind"]),
        )
        child_id = int(cursor.lastrowid)
        self.db.connection.execute("INSERT INTO axes(unit_id,axis,ordinal) VALUES(?,?,0)", (child_id, gap["axis"]))
        self.db.connection.execute("UPDATE stack SET is_top=0 WHERE id=?", (parent_frame["id"],))
        self.db.connection.execute(
            "INSERT INTO stack(session_id,unit_id,depth,resume_q,pending_json,hop_budget,is_top) VALUES(?,?,?,?,?,?,1)",
            (self.config.session_id, child_id, parent_frame["depth"] + 1, None, "[]", parent_frame["hop_budget"]),
        )
        self.db.connection.execute(
            "UPDATE meta SET current_unit_id=?,updated_at=datetime('now') WHERE session_id=?",
            (child_id, self.config.session_id),
        )
        return RouteDecision("wakeup.probe", child_id, gap["axis"], reason, highlight=highlight)

    def _queue_sibling_locked(self, frame: Any, gap: dict[str, Any]) -> None:
        pending = json.loads(frame["pending_json"])
        if any(entry["slug"] == gap["slug"] for entry in pending):
            return
        pending.append(gap)
        self.db.connection.execute("UPDATE stack SET pending_json=? WHERE id=?", (json.dumps(pending, sort_keys=True), frame["id"]))

    def _point_next_root_locked(self) -> RouteDecision:
        active = self.db.connection.execute(
            "SELECT id FROM stack WHERE session_id=?", (self.config.session_id,)
        ).fetchone()
        if active:
            raise InvariantError("cannot select a root while the stack is live")
        unit = self.db.connection.execute(
            "SELECT * FROM units WHERE session_id=? AND depth=0 AND state='NEW' ORDER BY ordinal LIMIT 1",
            (self.config.session_id,),
        ).fetchone()
        if not unit:
            return RouteDecision(None, None, None, "no next top-level unit")
        axis = self._next_unsolid_axis_locked(unit["id"])
        if not axis:
            raise InvariantError("mapped unit has no firing axes")
        self.db.connection.execute("UPDATE units SET state='POINTED' WHERE id=?", (unit["id"],))
        self.db.connection.execute(
            "INSERT INTO stack(session_id,unit_id,depth,resume_q,pending_json,hop_budget,is_top) VALUES(?,?,0,NULL,'[]',2,1)",
            (self.config.session_id, unit["id"]),
        )
        self.db.connection.execute(
            "UPDATE meta SET current_unit_id=?,updated_at=datetime('now') WHERE session_id=?",
            (unit["id"], self.config.session_id),
        )
        return RouteDecision("wakeup.probe", unit["id"], axis["axis"], "point next top-level unit", highlight=True)

    def _effective_verdict(self, axis_row: Any, proposed: str) -> tuple[str, int]:
        shaky_count = int(axis_row["shaky_count"])
        if proposed == "SHAKY":
            shaky_count += 1
            return ("MISSING" if shaky_count >= 2 else "SHAKY", shaky_count)
        return proposed, shaky_count

    def _gap(self, stamp: dict[str, Any]) -> dict[str, Any]:
        gap = stamp["hidden_gap"]
        if gap is None:
            raise InvariantError(
                "a child or sibling route requires JUDGE to supply hidden_gap with axis and anchor"
            )
        return gap

    def _next_unsolid_axis_locked(self, unit_id: int) -> Any | None:
        return self.db.connection.execute(
            "SELECT * FROM axes WHERE unit_id=? AND verdict != 'SOLID' ORDER BY ordinal LIMIT 1",
            (unit_id,),
        ).fetchone()

    def _axis_or_raise_locked(self, unit_id: int, axis: str) -> Any:
        row = self.db.connection.execute("SELECT * FROM axes WHERE unit_id=? AND axis=?", (unit_id, axis)).fetchone()
        if not row:
            raise InvariantError(f"unit does not fire {axis} axis")
        return row

    def _top_frame_locked(self) -> Any:
        row = self.db.connection.execute(
            "SELECT * FROM stack WHERE session_id=? AND is_top=1", (self.config.session_id,)
        ).fetchone()
        if not row:
            raise InvariantError("session has no live top stack frame")
        return row

    def _unit_locked(self, unit_id: int) -> Any:
        row = self.db.connection.execute(
            "SELECT * FROM units WHERE id=? AND session_id=?", (unit_id, self.config.session_id)
        ).fetchone()
        if not row:
            raise ValidationError("unit does not belong to this session")
        return row

    def _meta(self) -> Any:
        row = self.db.connection.execute("SELECT * FROM meta WHERE session_id=?", (self.config.session_id,)).fetchone()
        if not row:
            raise ValidationError("session must initialize workspace/meta before routing")
        return row
