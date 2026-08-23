# TUTOR — THE DATA LAYER (production-grade)

Status: LIVE — decision doc. This is the ACTUAL data design as if shipping to
production: every store, its real columns/fields, an example row, and — most
important — WHICH PROCESS STEP touches it and how. Use this to decide what to
KEEP, ADD, or DELETE. Decisions are marked `[DECIDE]` inline.

Companions: MASTER.md (engine + flow), CATALOGS.md (the templates), STONES.md
(the plain-English store list), WALKTHROUGH.md (one unit end-to-end).

Aligned to the 12-stone set:
    LIVE-DB (1) units (2) axes (3) stack (4) meta
    PERSIST (5) probes[DB] (6) learner[DB] (7) archive[file] (8) handoff[DB]
    READ-ONLY (9) codebase (10) schemas
    LIVE-FILE (11) workspace   LIVE→ARCHIVED (12) events[DB]

Legend in the relation map:  R = reads   W = writes   · = untouched

---

## 0. THE BIG PICTURE — stores × steps (the relation map)

Every store (row) against every process step (column). If a cell is blank the
step never touches that store. This grid IS "which point relates to what."

```
                         │ map │point│probe│teach│test │grade│route│distill│action│
 ────────────────────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼───────┼──────┤
 1 units      (DB live)  │  W  │  R  │  R  │  R  │  R  │  R  │ R/W │   R   │  R   │
 2 axes       (DB live)  │  W  │  ·  │  R  │  R  │  R  │  W  │  R  │   R   │  R   │
 3 stack      (DB live)  │  ·  │  ·  │  W  │  ·  │  ·  │  R  │ R/W │   R   │  ·   │
 4 meta       (DB live)  │  W  │  R  │  R  │  R  │  R  │  R  │ R/W │   W   │  R   │
 5 probes     (DB persist)│ ·  │  ·  │  ·  │  ·  │  ·  │  W  │  R  │   R   │  ·   │
 6 learner    (DB persist)│ R  │  ·  │  R  │  R  │  ·  │  W  │  ·  │   W   │  ·   │
 7 archive    (folder)   │  ·  │  ·  │  ·  │  ·  │  ·  │  ·  │  R  │   W   │  ·   │
 8 handoff    (DB persist)│·  │  ·  │  ·  │  ·  │  ·  │  ·  │  ·  │   W   │  ·   │
 ────────────────────────┼─────┼─────┼─────┼─────┼─────┼─────┼─────┼───────┼──────┤
 9 codebase   (RO)       │  R  │  R  │  R  │  R  │  R  │  R  │  ·  │   ·   │  ·   │
 10 schemas   (RO)       │  R  │  ·  │  ·  │  ·  │  ·  │  R  │  ·  │   R   │  ·   │
 11 workspace (file live)│  ·  │  ·  │  R  │  R  │  R  │  R  │  ·  │   R   │ R/W  │
 12 events    (DB live)  │  ·  │  ·  │  R  │  R  │  R  │  R  │  ·  │ R/MOVE│  W   │
```

Read a column top-to-bottom = "everything this step needs + produces."
Read a row left-to-right = "everywhere this store is used" (its whole life).
(`snapshot` is not a row — it's the per-turn packet code builds FOR a wakeup.)

---

## 1. THE DATABASE (6 tables — 5 live + 1 persist)

One SQLite DB per project. Every write goes through one guarded module (like the
old tutor_db.py) that REFUSES illegal writes. Below: real columns + example row.

### 1.1  units  — the ladder + each unit's state  (LIVE)
```
 column      type     meaning
 ──────────────────────────────────────────────────────────────────────
 id          int PK
 slug        text     stable name, e.g. "pinned_qa_group"
 file        text     where it lives on disk
 lo, hi      int      line range
 depth       int      0 = top-level unit ; >0 = a sub-hole
 parent_id   int      which unit this was descended from (null at depth 0)
 state       text     NEW|POINTED|PROBED|TAUGHT|TESTED|JUDGED|OWNED|PARKED
 created_at  ts

 example row:
 {id:12, slug:"pinned_qa_group", file:"run_prompts.py", lo:120, hi:131,
  depth:0, parent_id:null, state:"PROBED"}
```
Touched by: map (W rows), point/probe/teach/test/grade (R), route (state W).
NOTE: `kind` (TARGET/TRANSIT) was CUT — a TRANSIT unit is just one where few
axes fire; the axis-set in `axes` already encodes it.

### 1.2  axes  — the report card (one row per firing axis per unit)  (LIVE)
```
 column       type    meaning
 ──────────────────────────────────────────────────────────────────────
 unit_id      int FK
 axis         text    COMPREHEND|MECHANISM|RATIONALE|JUDGMENT|
                      ROBUSTNESS|INTEGRATION|EVOLUTION
 verdict      text    UNGRADED|SOLID|SHAKY|MISSING
 shaky_count  int     how many times SHAKY on this axis (2 → MISSING)
 evidence_ref text    pointer to the proof (transcript turn / probes row id)
 updated_at   ts

 example rows for unit 12:
 {unit_id:12, axis:"COMPREHEND", verdict:"SOLID",  shaky_count:0, ...}
 {unit_id:12, axis:"RATIONALE",  verdict:"SHAKY",  shaky_count:1, ...}
 {unit_id:12, axis:"ROBUSTNESS", verdict:"UNGRADED",shaky_count:0, ...}
```
Touched by: map (W firing rows), grade (W verdict + shaky_count),
probe/teach/test (R), route (R: "all axes SOLID? → OWNED"), distill (R).
NOTE: `shaky_count` is KEPT (a stored number, not derived). It's the fast cell
code trips at 2. Scope = within this unit (cleared on reset). The permanent
cross-unit record is `probes` (1.5).

### 1.3  stack  — the "where was I?" memory  (LIVE)
```
 column      type    meaning
 ──────────────────────────────────────────────────────────────────────
 id          int PK
 unit_id     int FK
 depth       int     position in the dive (0 = main)
 resume_q    text    the EXACT question paused when we dived
 pending     json    sibling holes found, not yet opened  [{slug,why}]
 hop_budget  int     how many inference hops a question may chain (shrinks)
 is_top      bool    only the deepest frame is teachable

 example: {id:3, unit_id:12, depth:0, resume_q:"why a dict not a list?",
           pending:[{slug:"ordered_keys",why:"assumed order"}], hop_budget:2,
           is_top:true}
```
Touched by: probe (W resume_q), route (push/pop, W), grade (R), distill (R).
`[DECIDE]` on pop, is the frame deleted or moved to an archived_frames table?

### 1.4  meta  — the single dial (exactly ONE row, ever)  (LIVE)
```
 column         type   meaning
 ──────────────────────────────────────────────────────────────────────
 current_unit   int    the deepest live unit (== G.current_unit)
 phase          text   SCAN | LOOP | GRADUATION
 target         text   which codebase is the objective
 updated_at     ts

 example: {current_unit:12, phase:"LOOP", target:"run_prompts.py"}
```
Touched by: EVERY step reads it; map/route/distill write it. ONE row — never
duplicated (the old system's 3-copy drift bug lives here if we're careless).

### 1.5  probes  — the diary, one row per Q&A  (PERSIST — never wiped)
```
 column         type   meaning
 ──────────────────────────────────────────────────────────────────────
 id             int PK
 turn           int    which turn of the whole session
 unit_id        int    which unit this Q&A belonged to
 axis           text   which axis was being worked
 step           text   probe | test
 question       text   what the tutor asked
 learner_answer text   what he replied (verbatim)
 verdict        text   SOLID | SHAKY | MISSING
 category       text   the label (faking, off-topic, ...)
 created_at     ts

 example rows:
 {turn:3, unit_id:12, axis:"RATIONALE", step:"probe",
  question:"why a dict not a list?", learner_answer:"...keeps order",
  verdict:"SHAKY", category:"working-code-wrong-reasoning"}
 {turn:5, unit_id:12, axis:"RATIONALE", step:"probe",
  question:"10k questions — dict vs list speed?", learner_answer:"...instant",
  verdict:"SOLID", category:"correct-deep"}
```
Touched by: grade (W, append every judged answer), route (R, spaced review),
distill (R). PERSIST: this is the long memory — "where has he struggled before?"

### 1.6  events  — automatic activity trace  (LIVE → ARCHIVED)
```
 column          type   meaning
 ──────────────────────────────────────────────────────────────────────
 id              int PK  monotonic event id
 unit_id         int FK  active unit that owns the event
 axis            text?   current axis, if applicable
 document_id     text    learner's one logical workspace document
 kind            text    edit | command | test | error | ui | feedback | block
 payload         json    normalized action, diff, command, or UI detail
 result          json?   command/test output, error, or policy outcome
 revision_hash   text?   workspace revision/snapshot reference
 created_at      ts

 example row:
 {id:91, unit_id:12, axis:"ROBUSTNESS", document_id:"learner-main",
  kind:"test", payload:{command:"pytest -q"}, result:{exit:1, output:"..."},
  revision_hash:"sha256:..."}
```
Touched by: action hooks (W automatically), probe/teach/test/grade (R when the
event is relevant evidence), distill (R then MOVE). The event recorder writes
this table without waiting for an agent. On OWNED/PARK, the guarded distill
transaction writes the event stream to that unit's archive artifact and deletes
these live rows only after the archive write succeeds.

---

## 2. THE FOLDERS / FILES (4, persist or live)

```
.claude/tutor/
│
├── tutor.sqlite                       ← authoritative mutable state (stones 1–6,8,12)
│
└── projects/<target>/                 ← per-codebase file artifacts
    ├── workspace/
    │   └── <display-name>             ← one visible logical learner document
    ├── archive/
    │   ├── <unit-slug>/              ← one titled artifact per finished/parked unit
    │   │   ├── manifest.json
    │   │   ├── events.jsonl
    │   │   └── workspace-snapshot.<ext>
    │   └── ...
```
(There is no `codebase-map/` folder — the ladder lives in the `units`+`axes`
DB tables. MAPPER writes those rows directly.)

### 2.1  learner table record  (GLOBAL, never wiped)  = stone 6
```json
{
  "can":  ["read a comprehension: pathlib.Path", "predict f-string output"],
  "cant": ["reason about when NOT to use a structure"],
  "misconceptions": [
    {"belief":"dict order is a guarantee to rely on",
     "disproved_by":"unit:pinned_qa_group"}
  ]
}
```
The JSON above is the `profile_json` payload in one learner table record.
Written by: grade (append can/cant/misconception), distill (consolidate).
Read by: map (shape the ladder), probe/teach (pitch to his level).
NOTE: simplified to 3 fields (`shown` dropped).

### 2.2  workspace/<display-name>  (one logical learner document)  = stone 11

The learner always sees one stable filename in the interface, such as
`solution.py`. The document has a stable internal id; closing a unit captures a
snapshot/diff without renaming or replacing the learner's visible file.

```
document_id:  "learner-main"
display_name: "solution.py"
language:     "python"
revision_hash:"sha256:..."
```

Written by: the guarded editor/workspace service. Read by: action hooks and any
step that needs learner-code evidence. It persists across ordinary unit changes;
only an explicit workspace-template policy may reset it.

### 2.3  archive/<slug>/manifest.json  (per unit)  = stone 7
```json
{
  "unit": "pinned_qa_group",
  "title": "Pinned Q&A grouping — first working lookup",
  "logical_document": {"id":"learner-main", "display_name":"solution.py"},
  "final_verdict": "OWNED",
  "axes_tested": ["COMPREHEND","RATIONALE","ROBUSTNESS","INTEGRATION"],
  "tests": [
    {"axis":"ROBUSTNESS","prompt":"what if two questions share a pin_id?",
     "his_answer":"...","result":"SOLID"}
  ],
  "evidence": ["probes:turn-1..8", "events:91..128"],
  "event_log": "events.jsonl",
  "workspace_snapshot": "workspace-snapshot.py",
  "resume_at": null           // set only if PARKED mid-unit
}
```
Written by: distill (on OWNED or park). The guarded transaction moves this
unit's live event rows into `events.jsonl` only after the manifest and workspace
snapshot are safely written. Read by: route (spaced review later). This is WHY a
wipe is safe — the proof and automatic activity trace are here permanently.

### 2.4  handoff table record  (the warm-start note)  = stone 8
```json
{
  "date": "2026-08-23",
  "next_unit": "run_prompts.main",
  "why": "pinned_qa_group is OWNED (all 4 axes SOLID); main is next in order",
  "dive_depth": 0,
  "open_siblings": [{"slug":"ordered_keys","why":"he assumed dict order"}],
  "learner_note": "still shaky on 'when NOT to' reasoning — push JUDGMENT axis",
  "continuation": {
    "next_step": "wakeup.probe",
    "awaiting": "learner_answer",
    "outstanding_question_ref": "events:128",
    "context_refs": ["probes:turn-3", "events:124..128"]
  },
  "resume_stack": [
    {"unit_id":12,"axis":"RATIONALE","state":"PROBED",
     "resume_q":"why a dict not a list?","pending":[],"hop_budget":2,
     "evidence_refs":["probes:turn-3"],"workspace_revision":"sha256:..."}
  ]
}
```
The JSON above is the `payload_json` value of the latest handoff record; SQLite,
not an exported file, is authoritative. Written by: distill/code checkpoint.
Read by: the next cold context, FIRST.
On PARK, `resume_stack` is the MOVED live stack, not a second copy. On return,
code restores it before waking the deepest unit and builds the same normal
minimal packet it would have built without a break. `dive_depth` remains a
quick display/diagnostic field; `resume_stack` is the exact continuity record.
`continuation` says precisely where the normal engine continues; it is not a
special agent prompt. Examples: after a displayed question it is
`awaiting: learner_answer` (so no agent is re-run); after an answer is saved it
can be `next_step: wakeup.grade`; after a TEACH pause it can await the learner
reaction. Code checkpoints only after a completed agent return, persisted
learner event, or committed guarded tool action—never halfway through an agent
call or transaction.

---

## 3. LIFECYCLE — what a RESET does to each store  (unit becomes OWNED)

```
 store               action                                   verb
 ──────────────────────────────────────────────────────────────────
 1 units             row kept, state=OWNED (history)          KEEP
 2 axes              distilled → archive, then cleared        DISTILL+CLEAR
 3 stack             popped frame dropped                     POP
 4 meta              current_unit advances                    UPDATE
5 probes            untouched — the diary keeps growing      KEEP (persist)
6 learner           consolidated                             UPDATE (never wipe)
 7 archive           titled manifest + events + snapshot       APPEND
8 handoff           overwritten with fresh note              REPLACE
                    on PARK: receives moved (3) stack         MOVE
 11 workspace        same logical document remains             KEEP
 12 events           atomically moved into unit archive        MOVE
```
`[DECIDE]` reset GRAIN: unit-level only (above), or also a lighter per-axis
reset and a heavier per-phase reset? (P.reset_grain in PROCESS.md)

---

## 4. HOW AN AGENT KNOWS THE FORMAT (schema-on-demand)

No format is ever baked into a prompt. The flow:
```
 agent finishes task → get_schema(task) → returns PATH to a schema file (stone 10)
   → agent opens it → fills that exact shape → HARNESS validates ↔ schema
   → mismatch = reject & retry
```
One schema file per return stamp:
```
 schema/return.map.json       ← shape of the units+axes rows MAPPER produces
 schema/return.grade.json     ← shape of the verdict stamp (writes 2,5,6)
 schema/return.distill.json   ← shape of archive manifest (writes 7,8,6; moves 12)
```
`[DECIDE]` schema format: strict JSON Schema (harness can auto-reject) vs a
commented example file (readable, looser).

---

## 5. THE DECISION LIST

RESOLVED:
 - probes diary → YES (stone 5, persist).
 - shaky_count → KEEP as a stored number on axes (fast trigger).
 - handoff → KEEP as its own stone (8), json, holds next_unit + dive_depth;
   PARK additionally moves the live stack plus deterministic continuation here.
 - kind (TARGET/TRANSIT) → CUT (axis-set encodes it).
 - codebase-map folder → CUT (ladder lives in units+axes DB).
 - snapshot → DEMOTED (per-turn wakeup input, not a stone).
 - learner-model → simplified to can/cant/misconceptions.
 - workspace → KEEP as stone 11: one stable learner-visible document.
 - events → KEEP as stone 12: automatic trace, moved to archive on unit close.

STILL OPEN:
 1. popped stack frames — deleted, or moved to an archived_frames table?
 2. reset grain — unit-only, or unit + axis + phase?
 3. schema files — strict JSON Schema, or commented example?
 4. evidence_ref target — a transcript turn, a probes row id, or an event id?
