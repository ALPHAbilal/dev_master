"""Minimal code→agent packet assembly and step-scoped capability policy."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import TutorConfig
from .contracts import WAKEUP_AGENTS, validate_continuation, validate_wakeup
from .db import Database
from .errors import CapabilityUnavailableError, ValidationError


class CapabilityPolicy:
    """The complete v1 capability allowlist; agents receive no implicit tools."""

    _BY_STEP: dict[str, tuple[str, ...]] = {
        "wakeup.map": ("read_code_slice", "search_repository"),
        "wakeup.probe": ("read_code_slice", "read_axis_evidence", "read_probe_history"),
        "wakeup.teach": ("read_code_slice", "read_axis_evidence", "read_probe_history"),
        "wakeup.test": ("read_code_slice", "read_axis_evidence", "read_probe_history", "read_workspace"),
        "wakeup.grade": ("read_code_slice", "read_axis_evidence", "read_probe_history", "read_transcript"),
        "wakeup.distill": ("read_turn_context", "read_probe_history", "read_workspace", "read_event_trace"),
        # Off-record aside: the agent may read only the frozen pins for this thread. No
        # workspace, repo search, axis/probe evidence, or write/route capability is granted.
        "wakeup.aside": ("read_pin",),
    }

    def for_step(self, step: str) -> tuple[str, ...]:
        try:
            return self._BY_STEP[step]
        except KeyError as error:
            raise CapabilityUnavailableError(f"no capability policy exists for {step}") from error

    def permits(self, step: str, capability: str) -> bool:
        return capability in self.for_step(step)

    def require(self, step: str, capability: str) -> None:
        if not self.permits(step, capability):
            raise CapabilityUnavailableError(f"{capability} is not available during {step}")


class WakeupBuilder:
    """Builds the one ordinary packet an agent receives for a specific step."""

    def __init__(self, db: Database, config: TutorConfig, policy: CapabilityPolicy | None = None) -> None:
        self.db = db
        self.config = config
        self.policy = policy or CapabilityPolicy()

    def build(
        self,
        *,
        step: str,
        unit_id: int | None = None,
        axis: str | None = None,
        transient: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assemble a closed, scoped wakeup envelope from persisted facts.

        `transient` is deliberately caller-supplied and separate from SQLite: it
        holds only the current learner answer/action evidence waiting to be judged.
        It never becomes a route or tool grant by itself.
        """
        if step not in WAKEUP_AGENTS:
            raise ValidationError(f"unsupported wakeup step: {step}")
        if step == "wakeup.aside":
            raise ValidationError("wakeup.aside is built by build_aside, not build")
        meta = self._meta()
        if step == "wakeup.map":
            if unit_id is not None or axis is not None:
                raise ValidationError("wakeup.map is not unit or axis scoped")
            context = {
                "target": meta["target"],
                "repository_root": str(self._codebase_root()),
            }
        else:
            if unit_id is None or axis is None:
                raise ValidationError(f"{step} requires unit_id and axis")
            context = self._unit_context(step, unit_id, axis, meta, transient or {})
        packet: dict[str, Any] = {
            "step": step,
            "agent": WAKEUP_AGENTS[step],
            "session_id": self.config.session_id,
            "context": context,
            "capabilities": list(self.policy.for_step(step)),
        }
        if unit_id is not None:
            packet["unit_id"] = unit_id
        if axis is not None:
            packet["axis"] = axis
        return validate_wakeup(packet)

    def build_resumed(
        self,
        *,
        continuation: dict[str, Any],
        unit_id: int,
        axis: str,
        transient: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the same ordinary packet after restore—no resume narrative added."""
        continuation = validate_continuation(continuation)
        return self.build(
            step=continuation["next_step"], unit_id=unit_id, axis=axis, transient=transient
        )

    def build_aside(self, *, journey_id: int, request_id: str) -> dict[str, Any]:
        """Assemble the closed packet for an off-record aside from persisted state.

        The agent receives its unit (id/slug/title + the axes that fire), the current
        question, a *pin manifest* (paths + descriptions, never the raw blobs), and this
        thread's prior completed Q&A. No axis grade, probe history, workspace, stack, meta,
        or profile is included, and the only capability granted is read_pin.
        """
        from .references import PinStore  # local import avoids a construction-time cycle
        turn = self.db.one(
            "SELECT * FROM aside_turns WHERE id=? AND journey_id=?", (request_id, journey_id))
        if not turn:
            raise ValidationError("aside turn does not belong to this journey")
        request = json.loads(turn["request_json"])
        unit_id = int(request["unit_id"])
        unit = self.db.one(
            "SELECT id,slug,title FROM units WHERE id=? AND session_id=?",
            (unit_id, self.config.session_id))
        if not unit:
            raise ValidationError("aside unit does not belong to this session")
        axes = [row["axis"] for row in self.db.query(
            "SELECT axis FROM axes WHERE unit_id=? ORDER BY ordinal", (unit_id,))]
        rows = self.db.query(
            "SELECT id,role,content,refs_json FROM conversation_messages "
            "WHERE journey_id=? AND thread_id=? AND thread_kind='aside' ORDER BY sequence",
            (journey_id, turn["thread_id"]))
        history = [{"message_id": row["id"], "role": row["role"], "content": row["content"],
                    "refs": json.loads(row["refs_json"])}
                   for row in rows if row["id"] != turn["learner_message_id"]]
        history_truncated = len(history) > 20
        manifest = PinStore(self.config).manifest(thread_id=turn["thread_id"])
        context = {
            "journey_id": journey_id,
            "thread_id": turn["thread_id"],
            "request_id": request_id,
            "unit": {"id": unit["id"], "slug": unit["slug"], "title": unit["title"], "axes": axes},
            "question": request["question"],
            "pins": manifest,
            "history": history[-20:],
            "history_truncated": history_truncated,
        }
        packet = {
            "step": "wakeup.aside",
            "agent": WAKEUP_AGENTS["wakeup.aside"],
            "session_id": self.config.session_id,
            "context": context,
            "capabilities": list(self.policy.for_step("wakeup.aside")),
            "unit_id": unit_id,
        }
        return validate_wakeup(packet)

    def _unit_context(
        self, step: str, unit_id: int, axis: str, meta: dict[str, Any], transient: dict[str, Any]
    ) -> dict[str, Any]:
        unit = self.db.one(
            "SELECT * FROM units WHERE id=? AND session_id=?", (unit_id, self.config.session_id)
        )
        if not unit:
            raise ValidationError("wakeup unit does not belong to this session")
        axis_row = self.db.one("SELECT * FROM axes WHERE unit_id=? AND axis=?", (unit_id, axis))
        if not axis_row:
            raise ValidationError("wakeup axis does not fire for this unit")
        source = self._source_context(unit)
        context: dict[str, Any] = {
            "unit": {
                "id": unit["id"], "slug": unit["slug"], "title": unit["title"],
                "state": unit["state"], "anchor_kind": unit["anchor_kind"],
            },
            "axis": {
                "name": axis_row["axis"], "verdict": axis_row["verdict"],
                "shaky_count": axis_row["shaky_count"], "evidence_ref": axis_row["evidence_ref"],
            },
            "source": source,
        }
        if step in {"wakeup.probe", "wakeup.teach"}:
            context["learner"] = self._learner_profile()
            context["hop_budget"] = self._hop_budget(unit_id)
        if step in {"wakeup.probe", "wakeup.teach", "wakeup.test", "wakeup.grade"}:
            context["recent_probes"] = self._recent_probes(unit_id, axis)
        if step == "wakeup.grade":
            if set(transient) - {"learner_answer", "question_ref", "action_evidence", "refs"}:
                raise ValidationError("grade transient contains an unscoped field")
            if "learner_answer" not in transient and "action_evidence" not in transient:
                raise ValidationError("wakeup.grade requires current answer or action evidence")
            context["current_evidence"] = transient
        if step == "wakeup.distill":
            context["workspace"] = self._workspace_ref(meta)
            context["events"] = self._events(unit_id)
            context["stack"] = self._stack(unit_id)
        return context

    def _source_context(self, unit: dict[str, Any]) -> dict[str, Any]:
        root = self._codebase_root()
        candidate = (root / unit["file"]).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValidationError("unit source path escapes configured codebase root")
        if not candidate.is_file():
            raise ValidationError(f"unit source file is unavailable: {unit['file']}")
        lines = candidate.read_text(encoding="utf-8").splitlines()
        lo, hi = int(unit["lo"]), int(unit["hi"])
        if hi > len(lines):
            raise ValidationError("unit source range exceeds the current code file")
        return {
            "role": "code" if unit["anchor_kind"] == "code" else "parent_context",
            "file": unit["file"], "lo": lo, "hi": hi,
            "text": "\n".join(lines[lo - 1:hi]),
            "highlight": unit["anchor_kind"] == "code",
        }

    def _codebase_root(self) -> Path:
        if self.config.codebase_root is None:
            raise ValidationError("codebase_root is required to build a source-scoped wakeup")
        root = self.config.codebase_root.resolve()
        if not root.is_dir():
            raise ValidationError("configured codebase_root is not a directory")
        return root

    def _meta(self) -> dict[str, Any]:
        meta = self.db.one("SELECT * FROM meta WHERE session_id=?", (self.config.session_id,))
        if not meta:
            raise ValidationError("session is not initialized")
        return meta

    def _learner_profile(self) -> dict[str, Any]:
        row = self.db.one("SELECT profile_json FROM learner WHERE learner_id=?", (self.config.learner_id,))
        if not row:
            return {"can": [], "cant": [], "misconceptions": []}
        profile = json.loads(row["profile_json"])
        if not isinstance(profile, dict):
            raise ValidationError("learner profile is malformed")
        return profile

    def _recent_probes(self, unit_id: int, axis: str) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT id,turn,step,question,learner_answer,verdict,category,created_at "
            "FROM probes WHERE session_id=? AND unit_id=? AND axis=? ORDER BY id DESC LIMIT 3",
            (self.config.session_id, unit_id, axis),
        )

    def _hop_budget(self, unit_id: int) -> int:
        row = self.db.one(
            "SELECT hop_budget FROM stack WHERE session_id=? AND unit_id=?", (self.config.session_id, unit_id)
        )
        if not row:
            raise ValidationError("wakeup unit has no live stack frame")
        return int(row["hop_budget"])

    def _workspace_ref(self, meta: dict[str, Any]) -> dict[str, Any]:
        return {
            "document_id": meta["document_id"], "display_name": meta["display_name"],
            "revision": meta["workspace_revision"], "revision_hash": meta["workspace_hash"],
        }

    def _events(self, unit_id: int) -> list[dict[str, Any]]:
        return self.db.query(
            "SELECT id,axis,document_id,kind,payload_json,result_json,revision_hash,created_at "
            "FROM events WHERE session_id=? AND unit_id=? ORDER BY id",
            (self.config.session_id, unit_id),
        )

    def _stack(self, unit_id: int) -> dict[str, Any]:
        row = self.db.one(
            "SELECT depth,resume_q,pending_json,hop_budget,is_top FROM stack WHERE session_id=? AND unit_id=?",
            (self.config.session_id, unit_id),
        )
        if not row:
            raise ValidationError("distill unit has no live stack frame")
        return {
            "depth": row["depth"], "resume_q": row["resume_q"],
            "pending": json.loads(row["pending_json"]), "hop_budget": row["hop_budget"],
            "is_top": bool(row["is_top"]),
        }
