"""Strict, side-effect-free contracts at every engine arrow.

The router and persistence services must call these validators before accepting an
agent return or an action packet. They intentionally accept plain dictionaries:
the SDK adapter can translate any provider message into these stable shapes.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from .errors import ValidationError

AXES = frozenset({"COMPREHEND", "MECHANISM", "RATIONALE", "JUDGMENT", "ROBUSTNESS", "INTEGRATION", "EVOLUTION"})
WAKEUP_AGENTS = {
    "wakeup.map": "MAPPER",
    "wakeup.probe": "TEACHER",
    "wakeup.teach": "TEACHER",
    "wakeup.test": "TEACHER",
    "wakeup.grade": "JUDGE",
    "wakeup.distill": "DISTILLER",
}
GRADE_CATEGORIES = frozenset({
    "correct-deep", "pattern-matched", "shaky", "misconception", "different-prereq",
    "sibling-hole", "confused-question", "different-axis", "off-topic", "gives-up",
    "silent-stuck", "disputes-verdict", "skip-request", "fatigue-switch",
    "working-code-wrong-reasoning",
})
EVENT_KINDS = frozenset({"edit", "command", "test", "error", "ui", "feedback", "block", "message"})


def _expect_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    return value


def _expect_keys(value: dict[str, Any], *, required: set[str], optional: set[str], label: str) -> None:
    missing = required - value.keys()
    extra = value.keys() - required - optional
    if missing:
        raise ValidationError(f"{label} is missing: {', '.join(sorted(missing))}")
    if extra:
        raise ValidationError(f"{label} has unknown fields: {', '.join(sorted(extra))}")


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be a non-empty string")
    return value


def _integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{label} must be at least {minimum}")
    return value


def _string_list(value: Any, label: str, *, allowed: frozenset[str] | None = None) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValidationError(f"{label} must be a list of non-empty strings")
    if len(set(value)) != len(value):
        raise ValidationError(f"{label} must not contain duplicates")
    if allowed is not None and not set(value) <= allowed:
        raise ValidationError(f"{label} contains an unsupported value")
    return value


def validate_wakeup(packet: dict[str, Any]) -> dict[str, Any]:
    """Validate a code→agent packet without deciding its future tool policy."""
    packet = _expect_object(packet, "wakeup")
    _expect_keys(packet, required={"step", "agent", "session_id", "context", "capabilities"}, optional={"unit_id", "axis"}, label="wakeup")
    step = _string(packet["step"], "wakeup.step")
    if step not in WAKEUP_AGENTS:
        raise ValidationError(f"unsupported wakeup step: {step}")
    if packet["agent"] != WAKEUP_AGENTS[step]:
        raise ValidationError(f"{step} must wake {WAKEUP_AGENTS[step]}")
    _string(packet["session_id"], "wakeup.session_id")
    _expect_object(packet["context"], "wakeup.context")
    _string_list(packet["capabilities"], "wakeup.capabilities")
    if "unit_id" in packet:
        _integer(packet["unit_id"], "wakeup.unit_id", minimum=1)
    if "axis" in packet and packet["axis"] not in AXES:
        raise ValidationError("wakeup.axis is unsupported")
    return deepcopy(packet)


def validate_return(stamp: dict[str, Any]) -> dict[str, Any]:
    """Validate agent→code output. This does not write a single stone."""
    stamp = _expect_object(stamp, "return stamp")
    kind = stamp.get("kind")
    validators: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "return.map": _validate_map,
        "return.grade": _validate_grade,
        "return.distill": _validate_distill,
    }
    if kind not in validators:
        raise ValidationError("return kind must be return.map, return.grade, or return.distill")
    return validators[kind](stamp)


def _validate_map(stamp: dict[str, Any]) -> dict[str, Any]:
    _expect_keys(stamp, required={"kind", "target", "mode", "continues_after", "objective_covered", "units", "order"}, optional=set(), label="return.map")
    _string(stamp["target"], "return.map.target")
    if stamp["mode"] not in {"initial", "extend"}:
        raise ValidationError("return.map.mode must be initial or extend")
    if stamp["continues_after"] is not None:
        _string(stamp["continues_after"], "return.map.continues_after")
    if not isinstance(stamp["objective_covered"], bool):
        raise ValidationError("return.map.objective_covered must be boolean")
    units = stamp["units"]
    if not isinstance(units, list) or not units:
        raise ValidationError("return.map.units must be a non-empty list")
    slugs: list[str] = []
    for index, unit in enumerate(units):
        unit = _expect_object(unit, f"return.map.units[{index}]")
        _expect_keys(unit, required={"slug", "file", "lo", "hi", "depth", "parent", "axes"}, optional={"title"}, label=f"return.map.units[{index}]")
        slug = _string(unit["slug"], f"return.map.units[{index}].slug")
        _string(unit["file"], f"return.map.units[{index}].file")
        lo = _integer(unit["lo"], f"return.map.units[{index}].lo", minimum=1)
        hi = _integer(unit["hi"], f"return.map.units[{index}].hi", minimum=lo)
        depth = _integer(unit["depth"], f"return.map.units[{index}].depth", minimum=0)
        if depth != 0 or unit["parent"] is not None:
            raise ValidationError("MAPPER units must be top-level: depth=0 and parent=null")
        _string_list(unit["axes"], f"return.map.units[{index}].axes", allowed=AXES)
        if "title" in unit:
            _string(unit["title"], f"return.map.units[{index}].title")
        slugs.append(slug)
    if len(set(slugs)) != len(slugs):
        raise ValidationError("return.map unit slugs must be unique")
    if stamp["order"] != slugs:
        raise ValidationError("return.map.order must exactly match units dependency order")
    if stamp["mode"] == "extend" and stamp["continues_after"] is None:
        raise ValidationError("return.map extend requires continues_after")
    if stamp["mode"] == "initial" and stamp["continues_after"] is not None:
        raise ValidationError("return.map initial must have continues_after=null")
    return deepcopy(stamp)


def _validate_grade(stamp: dict[str, Any]) -> dict[str, Any]:
    _expect_keys(stamp, required={"kind", "axis", "verdict", "category", "evidence_ref", "hidden_gap"}, optional=set(), label="return.grade")
    if stamp["axis"] not in AXES:
        raise ValidationError("return.grade.axis is unsupported")
    if stamp["verdict"] not in {"SOLID", "SHAKY", "MISSING"}:
        raise ValidationError("return.grade.verdict is unsupported")
    if stamp["category"] not in GRADE_CATEGORIES:
        raise ValidationError("return.grade.category is unsupported")
    _string(stamp["evidence_ref"], "return.grade.evidence_ref")
    gap = stamp["hidden_gap"]
    if gap is not None:
        gap = _expect_object(gap, "return.grade.hidden_gap")
        _expect_keys(gap, required={"slug", "why", "axis", "anchor"}, optional=set(), label="return.grade.hidden_gap")
        _string(gap["slug"], "return.grade.hidden_gap.slug")
        _string(gap["why"], "return.grade.hidden_gap.why")
        if gap["axis"] not in AXES:
            raise ValidationError("return.grade.hidden_gap.axis is unsupported")
        anchor = _expect_object(gap["anchor"], "return.grade.hidden_gap.anchor")
        if anchor.get("kind") == "conceptual":
            _expect_keys(anchor, required={"kind"}, optional=set(), label="return.grade.hidden_gap.anchor")
        elif anchor.get("kind") == "code":
            _expect_keys(anchor, required={"kind", "file", "lo", "hi"}, optional=set(), label="return.grade.hidden_gap.anchor")
            _string(anchor["file"], "return.grade.hidden_gap.anchor.file")
            lo = _integer(anchor["lo"], "return.grade.hidden_gap.anchor.lo", minimum=1)
            _integer(anchor["hi"], "return.grade.hidden_gap.anchor.hi", minimum=lo)
        else:
            raise ValidationError("return.grade.hidden_gap.anchor.kind must be code or conceptual")
    return deepcopy(stamp)


def _validate_distill(stamp: dict[str, Any]) -> dict[str, Any]:
    _expect_keys(stamp, required={"kind", "unit", "title", "logical_document", "final_verdict", "axes_tested", "tests", "evidence", "event_log", "workspace_snapshot", "resume_at", "learner_diff", "handoff"}, optional=set(), label="return.distill")
    _string(stamp["unit"], "return.distill.unit")
    _string(stamp["title"], "return.distill.title")
    document = _expect_object(stamp["logical_document"], "return.distill.logical_document")
    _expect_keys(document, required={"id", "display_name"}, optional=set(), label="return.distill.logical_document")
    _string(document["id"], "return.distill.logical_document.id")
    _string(document["display_name"], "return.distill.logical_document.display_name")
    if stamp["final_verdict"] not in {"OWNED", "PARKED"}:
        raise ValidationError("return.distill.final_verdict must be OWNED or PARKED")
    _string_list(stamp["axes_tested"], "return.distill.axes_tested", allowed=AXES)
    if not isinstance(stamp["tests"], list) or any(not isinstance(test, dict) for test in stamp["tests"]):
        raise ValidationError("return.distill.tests must be a list of objects")
    _string_list(stamp["evidence"], "return.distill.evidence")
    _string(stamp["event_log"], "return.distill.event_log")
    _string(stamp["workspace_snapshot"], "return.distill.workspace_snapshot")
    _validate_resume(stamp["resume_at"], stamp["final_verdict"])
    _validate_learner_diff(stamp["learner_diff"])
    _validate_handoff(stamp["handoff"])
    return deepcopy(stamp)


def _validate_resume(value: Any, verdict: str) -> None:
    if verdict == "OWNED" and value is not None:
        raise ValidationError("OWNED distill must have resume_at=null")
    if verdict == "PARKED":
        value = _expect_object(value, "return.distill.resume_at")
        _expect_keys(value, required={"axis", "note"}, optional=set(), label="return.distill.resume_at")
        if value["axis"] not in AXES:
            raise ValidationError("return.distill.resume_at.axis is unsupported")
        _string(value["note"], "return.distill.resume_at.note")


def _validate_learner_diff(value: Any) -> None:
    value = _expect_object(value, "return.distill.learner_diff")
    _expect_keys(value, required={"can", "cant", "misconceptions"}, optional=set(), label="return.distill.learner_diff")
    _string_list(value["can"], "return.distill.learner_diff.can")
    _string_list(value["cant"], "return.distill.learner_diff.cant")
    if not isinstance(value["misconceptions"], list):
        raise ValidationError("return.distill.learner_diff.misconceptions must be a list")
    for item in value["misconceptions"]:
        item = _expect_object(item, "return.distill.learner_diff.misconception")
        _expect_keys(item, required={"belief", "disproved_by"}, optional=set(), label="return.distill.learner_diff.misconception")
        _string(item["belief"], "return.distill.learner_diff.misconception.belief")
        _string(item["disproved_by"], "return.distill.learner_diff.misconception.disproved_by")


def _validate_handoff(value: Any) -> None:
    value = _expect_object(value, "return.distill.handoff")
    _expect_keys(value, required={"next_unit", "dive_depth", "why", "watch"}, optional=set(), label="return.distill.handoff")
    _string(value["next_unit"], "return.distill.handoff.next_unit")
    _integer(value["dive_depth"], "return.distill.handoff.dive_depth", minimum=0)
    _string(value["why"], "return.distill.handoff.why")
    _string(value["watch"], "return.distill.handoff.watch")


def validate_action_event(packet: dict[str, Any]) -> dict[str, Any]:
    """Validate code→code/agent observation before EventRecorder receives it."""
    packet = _expect_object(packet, "action event")
    _expect_keys(packet, required={"unit_id", "document_id", "kind", "payload"}, optional={"axis", "result", "revision_hash"}, label="action event")
    _integer(packet["unit_id"], "action event.unit_id", minimum=1)
    _string(packet["document_id"], "action event.document_id")
    if packet["kind"] not in EVENT_KINDS:
        raise ValidationError("action event.kind is unsupported")
    _expect_object(packet["payload"], "action event.payload")
    if "axis" in packet and packet["axis"] is not None and packet["axis"] not in AXES:
        raise ValidationError("action event.axis is unsupported")
    if "result" in packet and packet["result"] is not None:
        _expect_object(packet["result"], "action event.result")
    if "revision_hash" in packet and packet["revision_hash"] is not None:
        _string(packet["revision_hash"], "action event.revision_hash")
    return deepcopy(packet)


def validate_continuation(record: dict[str, Any]) -> dict[str, Any]:
    """Validate code-owned PARK state without turning it into an agent prompt."""
    record = _expect_object(record, "continuation")
    _expect_keys(record, required={"next_step", "awaiting", "outstanding_question_ref", "context_refs"}, optional=set(), label="continuation")
    if record["next_step"] not in WAKEUP_AGENTS:
        raise ValidationError("continuation.next_step is unsupported")
    if record["awaiting"] not in {"learner_answer", "learner_reaction", "none"}:
        raise ValidationError("continuation.awaiting is unsupported")
    question = record["outstanding_question_ref"]
    if record["awaiting"] == "learner_answer" and not isinstance(question, str):
        raise ValidationError("learner_answer continuation requires outstanding_question_ref")
    if record["awaiting"] != "learner_answer" and question is not None:
        raise ValidationError("only learner_answer continuation may hold a question reference")
    if question is not None:
        _string(question, "continuation.outstanding_question_ref")
    _string_list(record["context_refs"], "continuation.context_refs")
    return deepcopy(record)


def validate_archive_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate the sealed artifact form generated from a return.distill stamp."""
    manifest = _expect_object(manifest, "archive manifest")
    _expect_keys(manifest, required={"unit", "title", "logical_document", "final_verdict", "axes_tested", "tests", "evidence", "event_ids", "event_log", "workspace_snapshot", "workspace_hash", "workspace_checkpoints", "resume_at"}, optional=set(), label="archive manifest")
    derived = {
        "kind": "return.distill",
        "unit": manifest["unit"], "title": manifest["title"],
        "logical_document": manifest["logical_document"], "final_verdict": manifest["final_verdict"],
        "axes_tested": manifest["axes_tested"], "tests": manifest["tests"], "evidence": manifest["evidence"],
        "event_log": manifest["event_log"], "workspace_snapshot": manifest["workspace_snapshot"],
        "resume_at": manifest["resume_at"],
        "learner_diff": {"can": [], "cant": [], "misconceptions": []},
        "handoff": {"next_unit": manifest["unit"], "dive_depth": 0, "why": "archive", "watch": "archive"},
    }
    _validate_distill(derived)
    event_ids = manifest["event_ids"]
    if not isinstance(event_ids, list) or any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in event_ids):
        raise ValidationError("archive manifest.event_ids must be positive integers")
    if len(set(event_ids)) != len(event_ids):
        raise ValidationError("archive manifest.event_ids must not contain duplicates")
    _string(manifest["workspace_hash"], "archive manifest.workspace_hash")
    checkpoints = manifest["workspace_checkpoints"]
    if not isinstance(checkpoints, list):
        raise ValidationError("archive manifest.workspace_checkpoints must be a list")
    checkpoint_hashes: set[str] = set()
    for checkpoint in checkpoints:
        checkpoint = _expect_object(checkpoint, "archive manifest.workspace_checkpoint")
        _expect_keys(checkpoint, required={"revision", "hash", "file"}, optional=set(), label="archive manifest.workspace_checkpoint")
        _integer(checkpoint["revision"], "archive manifest.workspace_checkpoint.revision", minimum=0)
        digest = _string(checkpoint["hash"], "archive manifest.workspace_checkpoint.hash")
        _string(checkpoint["file"], "archive manifest.workspace_checkpoint.file")
        if digest in checkpoint_hashes:
            raise ValidationError("archive manifest.workspace_checkpoints must not repeat a hash")
        checkpoint_hashes.add(digest)
    return deepcopy(manifest)
