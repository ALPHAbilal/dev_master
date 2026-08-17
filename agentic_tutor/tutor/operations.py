"""The tutor's operation surface — every state mutation, one object each.

Design contract (docs/tutor-simulation.md F5/F6 + Q8, tutor-sdk-mapping.md §2):
  - EVERY state change is an Operation. There are no side doors (H1).
  - EVERY operation is menu-able: it has a one-line `summary` and a `role`, so the
    db() gateway can show a state-filtered menu without dumping full schemas.
  - EVERY operation ships back BOTH:
      * text    — what the model sees now: ack + consequence (F5)
      * receipt — the one-line receipt F7 collapses the tool exchange down to
  - Invalid input raises OpError and commits NOTHING (the tool disposes).

Adding an op later = add one Operation to REGISTRY. Nothing else changes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from .db import DB


class OpError(Exception):
    """Validation/precondition failure. The gateway turns this into a refusal."""


@dataclass
class OpResult:
    text: str                       # ack + consequence — shown to the model this turn
    receipt: str                    # one-line — what persists after F7 collapse


@dataclass
class Operation:
    name: str
    role: str                       # 'L' | 'M' | 'both'  — who may see/call it
    summary: str                    # the one-line menu entry
    schema: dict[str, str]          # field -> type: 'str'|'int'|'bool'|'json'
    run: Callable[[DB, dict], OpResult]
    required: tuple[str, ...] = ()
    available: Callable[[DB], bool] = field(default=lambda db: True)

    def describe(self) -> str:
        """The full schema-as-text, returned when the agent picks this op."""
        lines = [f"{self.name} — {self.summary}", "args:"]
        for fld, typ in self.schema.items():
            req = " (required)" if fld in self.required else ""
            lines.append(f"  {fld}: {typ}{req}")
        return "\n".join(lines)


# --------------------------------------------------------------------------
# validation helpers
# --------------------------------------------------------------------------
_COERCE = {
    "str": lambda v: str(v),
    "int": lambda v: int(v),
    "bool": lambda v: 1 if (v is True or str(v).lower() in ("1", "true", "yes")) else 0,
    "json": lambda v: v if isinstance(v, (list, dict)) else json.loads(v),
}


def validate(op: Operation, args: dict) -> dict:
    for r in op.required:
        if r not in args or args[r] in (None, ""):
            raise OpError(f"missing required arg: {r}")
    clean: dict = {}
    for fld, val in args.items():
        if fld not in op.schema:
            raise OpError(f"unknown arg: {fld}")
        try:
            clean[fld] = _COERCE[op.schema[fld]](val)
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            raise OpError(f"bad value for {fld} (want {op.schema[fld]}): {e}")
    return clean


# --------------------------------------------------------------------------
# L operations — the teacher's writes
# --------------------------------------------------------------------------
def _record_probe(db: DB, a: dict) -> OpResult:
    db.execute(
        "INSERT INTO probes(concept_slug,kind,result,pushes,self_corrected,"
        "error_class,reveals,terms,note) VALUES(?,?,?,?,?,?,?,?,?)",
        (a.get("concept_slug"), a["kind"], a["result"], a.get("pushes", 0),
         a.get("self_corrected", 0), a.get("error_class"), a.get("reveals"),
         a.get("terms"), a.get("note")),
    )
    pushes = a.get("pushes", 0)
    if pushes >= 4:
        conseq = "Cap hit (4 pushes): record and STOP. Do not carry him."
    elif a["result"] == "HIT" and a.get("self_corrected"):
        conseq = "HIT, self-corrected — that is the ZPD. Advance."
    elif a["result"] == "MISS":
        conseq = "MISS recorded. Stay on the road; do not hand him the fix."
    else:
        conseq = "Recorded."
    return OpResult(
        text=f"OK. Probe stored ({a['result']}, {pushes} pushes). {conseq}",
        receipt=f"probe: {a.get('concept_slug','?')} {a['result']} pushes={pushes}",
    )


def _promote_vocab(db: DB, a: dict) -> OpResult:
    db.execute(
        "INSERT INTO vocab(term,status) VALUES(?,?) "
        "ON CONFLICT(term) DO UPDATE SET status=excluded.status, updated_at=datetime('now')",
        (a["term"], a["status"]),
    )
    conseq = (f"'{a['term']}' is now speakable." if a["status"] in ("shown", "proved")
              else f"'{a['term']}' is HELD — probe the behavior before using the word.")
    return OpResult(text=f"OK. {conseq}", receipt=f"vocab: {a['term']}={a['status']}")


def _store_mapping(db: DB, a: dict) -> OpResult:
    for k in ("trigger", "solution", "why"):
        if not a.get(k):
            raise OpError(f"mapping needs a non-empty {k} (the library never lies)")
    db.execute(
        "INSERT INTO mappings(concept_slug,polarity,trigger,solution,why,provenance) "
        "VALUES(?,?,?,?,?,?)",
        (a["concept_slug"], a.get("polarity", "positive"), a["trigger"],
         a["solution"], a["why"], a.get("provenance")),
    )
    return OpResult(
        text="OK. Mapping deposited. The gap may now close.",
        receipt=f"mapping: {a['concept_slug']} ({a.get('polarity','positive')})",
    )


def _close_gap(db: DB, a: dict) -> OpResult:
    slug = a["concept_slug"]
    if not db.one("SELECT 1 FROM concepts WHERE slug=?", (slug,)):
        raise OpError(f"no such concept: {slug}")
    if not db.one("SELECT 1 FROM mappings WHERE concept_slug=? AND polarity='positive'", (slug,)):
        raise OpError(f"cannot close {slug}: no positive mapping stored yet")
    db.execute("UPDATE concepts SET state='OWNED' WHERE slug=?", (slug,))
    # does any slice now have ALL prereqs owned?
    freed = _slices_now_ready(db)
    if freed:
        conseq = f"All prereqs owned for {', '.join(freed)} → gate-when fires. Open the gate."
    else:
        conseq = "Concept OWNED. Continue the slice."
    return OpResult(text=f"OK. {slug} → OWNED. {conseq}",
                    receipt=f"gap-closed: {slug} → OWNED")


def _open_gate(db: DB, a: dict) -> OpResult:
    sl = db.one("SELECT * FROM slices WHERE slug=?", (a["slice_slug"],))
    if not sl:
        raise OpError(f"no such slice: {a['slice_slug']}")
    if db.one("SELECT 1 FROM gates WHERE slice_slug=? AND state='OPEN'", (a["slice_slug"],)):
        raise OpError(f"a gate is already OPEN for {a['slice_slug']}")
    db.execute("INSERT INTO gates(slice_slug,target_file,spec_path,state) VALUES(?,?,?,'OPEN')",
               (sl["slug"], sl["target_file"], sl["spec_path"]))
    return OpResult(
        text=f"OK. Gate OPEN. Wall active: spec hidden, you may NOT write {sl['target_file']}. "
             f"He writes it, or it did not happen.",
        receipt=f"gate-open: {sl['slug']} ({sl['target_file']})",
    )


def _pass_gate(db: DB, a: dict) -> OpResult:
    g = db.one("SELECT * FROM gates WHERE slice_slug=? AND state='OPEN'", (a["slice_slug"],))
    if not g:
        raise OpError(f"no OPEN gate for {a['slice_slug']}")
    db.execute("UPDATE gates SET state='PASSED', closed_at=datetime('now') WHERE id=?", (g["id"],))
    db.execute("UPDATE slices SET state='BUILT', built_at=datetime('now') WHERE slug=?",
               (a["slice_slug"],))
    return OpResult(
        text=f"OK. Gate PASSED. Slice {a['slice_slug']} → BUILT — a real piece of the "
             f"codebase now exists by his hand. Rollover: archive frontier, M plans next.",
        receipt=f"gate-pass: {a['slice_slug']} → BUILT",
    )


def _fail_gate(db: DB, a: dict) -> OpResult:
    g = db.one("SELECT * FROM gates WHERE slice_slug=? AND state='OPEN'", (a["slice_slug"],))
    if not g:
        raise OpError(f"no OPEN gate for {a['slice_slug']}")
    db.execute("UPDATE gates SET state='FAILED', closed_at=datetime('now') WHERE id=?", (g["id"],))
    return OpResult(text=f"OK. Gate FAILED for {a['slice_slug']}. It stays his to write.",
                    receipt=f"gate-fail: {a['slice_slug']}")


def _raise_subhole(db: DB, a: dict) -> OpResult:
    sl = db.one("SELECT * FROM slices WHERE slug=?", (a["slice_slug"],))
    if not sl:
        raise OpError(f"no such slice: {a['slice_slug']}")
    db.execute(
        "UPDATE slices SET subhole_concept=?, subhole_evidence=? WHERE slug=?",
        (a["concept_slug"], a["evidence"], a["slice_slug"]),
    )
    return OpResult(
        text="OK. Subhole handed to M. HOLD — do not answer him until the frontier updates.",
        receipt=f"subhole-raised: {a['concept_slug']} in {a['slice_slug']}",
    )


# --------------------------------------------------------------------------
# M operations — the planner's writes
# --------------------------------------------------------------------------
def _upsert_concept(db: DB, a: dict) -> OpResult:
    db.execute(
        "INSERT INTO concepts(slug,name,definition,aspect,state,requires,ordinal) "
        "VALUES(?,?,?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET "
        "name=excluded.name, definition=excluded.definition, aspect=excluded.aspect, "
        "requires=excluded.requires, ordinal=excluded.ordinal",
        (a["slug"], a["name"], a.get("definition"), a.get("aspect"),
         a.get("state", "LOCKED"), _as_json(a.get("requires")), a.get("ordinal")),
    )
    return OpResult(text=f"OK. Concept {a['slug']} upserted.",
                    receipt=f"concept: {a['slug']}")


def _upsert_slice(db: DB, a: dict) -> OpResult:
    db.execute(
        "INSERT INTO slices(slug,title,target_file,spec_path,state,kind,concept_prereqs,ordinal) "
        "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET "
        "title=excluded.title, target_file=excluded.target_file, spec_path=excluded.spec_path, "
        "kind=excluded.kind, concept_prereqs=excluded.concept_prereqs, ordinal=excluded.ordinal",
        (a["slug"], a["title"], a["target_file"], a.get("spec_path"),
         a.get("state", "LOCKED"), a.get("kind", "function"),
         _as_json(a.get("concept_prereqs")), a.get("ordinal")),
    )
    return OpResult(text=f"OK. Slice {a['slug']} upserted.", receipt=f"slice: {a['slug']}")


def _set_concept_state(db: DB, a: dict) -> OpResult:
    if not db.one("SELECT 1 FROM concepts WHERE slug=?", (a["slug"],)):
        raise OpError(f"no such concept: {a['slug']}")
    db.execute("UPDATE concepts SET state=? WHERE slug=?", (a["state"], a["slug"]))
    return OpResult(text=f"OK. {a['slug']} → {a['state']}.",
                    receipt=f"concept-state: {a['slug']}={a['state']}")


def _set_slice_state(db: DB, a: dict) -> OpResult:
    if not db.one("SELECT 1 FROM slices WHERE slug=?", (a["slug"],)):
        raise OpError(f"no such slice: {a['slug']}")
    db.execute("UPDATE slices SET state=? WHERE slug=?", (a["state"], a["slug"]))
    return OpResult(text=f"OK. Slice {a['slug']} → {a['state']}.",
                    receipt=f"slice-state: {a['slug']}={a['state']}")


def _clear_subhole(db: DB, a: dict) -> OpResult:
    db.execute(
        "UPDATE slices SET subhole_concept=NULL, subhole_evidence=NULL, subhole_plan=? "
        "WHERE slug=?",
        (a.get("plan_note"), a["slice_slug"]),
    )
    return OpResult(text="OK. Subhole cleared — L may continue on the updated frontier.",
                    receipt=f"subhole-cleared: {a['slice_slug']}")


def _decompose_target(db: DB, a: dict) -> OpResult:
    db.execute(
        "INSERT INTO target(id,codebase_path,decomposition) VALUES(1,?,?) "
        "ON CONFLICT(id) DO UPDATE SET codebase_path=excluded.codebase_path, "
        "decomposition=excluded.decomposition",
        (a["codebase_path"], _as_json(a.get("decomposition"))),
    )
    return OpResult(text="OK. Target decomposition stored.",
                    receipt=f"target: {a['codebase_path']}")


# --------------------------------------------------------------------------
# read operations (both) — cheap, no receipt weight
# --------------------------------------------------------------------------
def _list_ready_slices(db: DB, a: dict) -> OpResult:
    rows = db.query("SELECT slug,title,target_file FROM slices WHERE state='READY' ORDER BY ordinal")
    body = "\n".join(f"  {r['slug']} — {r['title']} → {r['target_file']}" for r in rows) or "  (none)"
    return OpResult(text=f"READY slices:\n{body}", receipt="read: ready-slices")


def _list_probes_since(db: DB, a: dict) -> OpResult:
    since = a.get("since_id", 0)
    rows = db.query("SELECT * FROM probes WHERE id > ? ORDER BY id", (since,))
    body = "\n".join(
        f"  #{r['id']} {r['concept_slug']} {r['kind']}/{r['result']} pushes={r['pushes']} "
        f"reveals={r['reveals']}" for r in rows) or "  (none)"
    return OpResult(text=f"probes since {since}:\n{body}", receipt=f"read: probes>{since}")


# --------------------------------------------------------------------------
# internal
# --------------------------------------------------------------------------
def _as_json(v):
    if v is None:
        return None
    return v if isinstance(v, str) else json.dumps(v)


def _slices_now_ready(db: DB) -> list[str]:
    """Set LOCKED slices whose concept_prereqs are all OWNED to READY; return their slugs."""
    freed = []
    for sl in db.query("SELECT slug,concept_prereqs FROM slices WHERE state='LOCKED'"):
        prereqs = json.loads(sl["concept_prereqs"]) if sl["concept_prereqs"] else []
        if not prereqs:
            continue
        owned = {r["slug"] for r in db.query(
            "SELECT slug FROM concepts WHERE state='OWNED' AND slug IN (%s)"
            % ",".join("?" * len(prereqs)), tuple(prereqs))}
        if all(p in owned for p in prereqs):
            db.execute("UPDATE slices SET state='READY' WHERE slug=?", (sl["slug"],))
            freed.append(sl["slug"])
    return freed


# --------------------------------------------------------------------------
# THE REGISTRY — the whole state surface, in one place
# --------------------------------------------------------------------------
def _has_open_gate(db: DB) -> bool:
    return db.one("SELECT 1 FROM gates WHERE state='OPEN'") is not None


REGISTRY: dict[str, Operation] = {op.name: op for op in [
    # --- L: the teacher ---
    Operation("record_probe", "L", "record one judged answer as evidence",
              {"concept_slug": "str", "kind": "str", "result": "str", "pushes": "int",
               "self_corrected": "bool", "error_class": "str", "reveals": "str",
               "terms": "str", "note": "str"},
              _record_probe, required=("kind", "result")),
    Operation("promote_vocab", "L", "set a term's status (hold/shown/proved)",
              {"term": "str", "status": "str"}, _promote_vocab, required=("term", "status")),
    Operation("store_mapping", "L", "deposit an intuition mapping (trigger+solution+why)",
              {"concept_slug": "str", "polarity": "str", "trigger": "str",
               "solution": "str", "why": "str", "provenance": "str"},
              _store_mapping, required=("concept_slug", "trigger", "solution", "why")),
    Operation("close_gap", "L", "mark a concept OWNED (needs a mapping first)",
              {"concept_slug": "str"}, _close_gap, required=("concept_slug",)),
    Operation("open_gate", "L", "open the blank-page wall for a slice",
              {"slice_slug": "str"}, _open_gate, required=("slice_slug",),
              available=lambda db: not _has_open_gate(db)),
    Operation("pass_gate", "L", "close an open gate as PASSED → slice BUILT",
              {"slice_slug": "str"}, _pass_gate, required=("slice_slug",),
              available=_has_open_gate),
    Operation("fail_gate", "L", "close an open gate as FAILED",
              {"slice_slug": "str"}, _fail_gate, required=("slice_slug",),
              available=_has_open_gate),
    Operation("raise_subhole", "L", "hand a shaky prereq to M and HOLD",
              {"slice_slug": "str", "concept_slug": "str", "evidence": "str"},
              _raise_subhole, required=("slice_slug", "concept_slug", "evidence")),
    # --- M: the planner ---
    Operation("upsert_concept", "M", "create/update a concept (DAG node)",
              {"slug": "str", "name": "str", "definition": "str", "aspect": "str",
               "state": "str", "requires": "json", "ordinal": "int"},
              _upsert_concept, required=("slug", "name")),
    Operation("upsert_slice", "M", "create/update a slice (unit of progress)",
              {"slug": "str", "title": "str", "target_file": "str", "spec_path": "str",
               "state": "str", "kind": "str", "concept_prereqs": "json", "ordinal": "int"},
              _upsert_slice, required=("slug", "title", "target_file")),
    Operation("set_concept_state", "M", "force a concept's mastery state",
              {"slug": "str", "state": "str"}, _set_concept_state, required=("slug", "state")),
    Operation("set_slice_state", "M", "force a slice's build state",
              {"slug": "str", "state": "str"}, _set_slice_state, required=("slug", "state")),
    Operation("clear_subhole", "M", "clear a slice's subhole after re-planning",
              {"slice_slug": "str", "plan_note": "str"}, _clear_subhole,
              required=("slice_slug",), available=lambda db: db.one(
                  "SELECT 1 FROM slices WHERE subhole_concept IS NOT NULL") is not None),
    Operation("decompose_target", "M", "store the codebase + its slice decomposition",
              {"codebase_path": "str", "decomposition": "json"}, _decompose_target,
              required=("codebase_path",)),
    # --- reads (both) ---
    Operation("list_ready_slices", "both", "list slices ready to gate",
              {}, _list_ready_slices),
    Operation("list_probes_since", "both", "list evidence rows after an id",
              {"since_id": "int"}, _list_probes_since),
]}


def menu_for(db: DB, role: str) -> list[Operation]:
    """State-filtered menu (F6): ops for this role whose `available` predicate holds now."""
    out = []
    for op in REGISTRY.values():
        if op.role not in (role, "both"):
            continue
        if not op.available(db):
            continue
        out.append(op)
    return out
