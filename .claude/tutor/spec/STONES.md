# TUTOR — THE STONES (every place data lives)

Status: LIVE. A "stone" = a place data LIVES. The governing rule, now that the
engine is settled:

    A STONE EXISTS ONLY IF AN ENGINE ARROW TOUCHES IT.
    (some wakeup READS it, or some return WRITES it — see CATALOGS.md)
    If nothing reads or writes it, it is not a stone. And every fact has ONE
    home — if two stones hold the same fact, one is wrong.

For each stone we pin FOUR things and nothing else:
    HOLDS   what data is in it
    READS   which steps read it        (step names from CATALOGS.md)
    WRITES  which steps write it        ← the important one
    LIFE    LIVE (reset clears) · PERSIST (survives) · READ-ONLY

There are TWELVE stones: 5 live-DB · 3 persist-DB · 2 folders/files · 2 read-only.
`snapshot` is NOT a stone — it is the per-turn wakeup input (see note at end).

---

## THE STONE MAP (overview)

    LIVE — DB + workspace         PERSIST — DB + archive      READ-ONLY
    ┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
    │ 1 units          │        │ 5 probes  (DB)   │        │ 9 codebase       │
    │ 2 axes           │        │ 6 learner (DB)   │        │ 10 schemas       │
    │ 3 stack          │        │ 7 archive (fldr) │        └──────────────────┘
    │ 4 meta           │        │ 8 handoff (DB)   │
    │ 11 workspace(file)│       │                    │
    │ 12 events (DB)   │        │                    │
    └──────────────────┘        └──────────────────┘

Twelve clean nouns, no overlap:
    units · axes · stack · meta · probes · learner · archive · handoff
    · codebase · schemas · workspace · events

Two scopes to keep straight:
  • LIVE (units,axes,stack,meta,events) = this unit's working state; reset clears it.
  • PERSIST (probes,learner,archive,handoff) = survives every reset. `probes`,
    `learner`, and `handoff` are SQLite records; archive is a titled artifact
    folder. SQLite is authoritative for all mutable state and makes checkpoint
    moves atomic.
  • WORKSPACE (11) = one mutable learner document, visible under one stable name.
    It is not cleared merely because a unit closes; the unit's relevant snapshot
    and event trace are sealed into archive.

---

## 1. units  (DB — LIVE)  — the ladder + each unit's state
    PLAIN    The list of code pieces to learn, in dependency order, each with a
             bookmark saying which step it's at. This IS the "map" — MAPPER writes
             these rows directly; there is no separate map file.
    HOLDS    slug, file, lo, hi, depth, parent_id, state
             (state: NEW→POINTED→PROBED→TAUGHT→TESTED→JUDGED→OWNED|PARKED)
    READS    map(after write), point, probe, teach, test, grade, route, distill
    WRITES   map (creates rows) · route (advances state)
    LIFE     LIVE. An OWNED row is kept as history; its detail is distilled to
             `archive` then trimmed.
    NOTE     'kind' (TARGET/TRANSIT) was CUT — a TRANSIT unit is simply one where
             few axes fire. The axis-set (stone 2) already encodes it.

## 2. axes  (DB — LIVE)  — the report card
    PLAIN    For each unit, one row per ANGLE of understanding it demands, and the
             grade on each. A unit is done only when every row is SOLID.
    HOLDS    unit_id, axis, verdict (UNGRADED|SOLID|SHAKY|MISSING),
             shaky_count, evidence_ref
    READS    probe, teach, test, grade, route ("all SOLID? → OWNED"), distill
    WRITES   map (creates the firing rows, UNGRADED) · grade (sets verdict,
             shaky_count, evidence_ref)
    LIFE     LIVE. Distilled to `archive` on OWNED, then cleared.
    NOTE     evidence_ref = a transcript turn pointer (e.g. "turn-4"). It is
             load-bearing: the law "no SOLID without evidence" points at it.
    NOTE     shaky_count is KEPT as a stored number (not derived from `probes`).
             It is the fast operational cell: code reads it, and when it passes 2
             it fires the "=MISSING" rule with no scan. Scope is WITHIN this unit
             (cleared on reset). The `probes` diary (stone 5) is the permanent
             cross-unit record; the counter is the in-the-moment trigger. Both on
             purpose — different jobs.

## 3. stack  (DB — LIVE)  — the "where was I?" memory
    PLAIN    When a gap makes us dive into a sub-unit, we remember the exact
             question we paused so we can climb back and finish. One frame per
             level dived.
    HOLDS    unit_id, depth, resume_q, pending[{slug,why}], hop_budget, is_top
    READS    grade, route, distill
    WRITES   probe (sets resume_q) · route (push on descent / pop on climb-up)
    LIFE     LIVE. A popped frame is dropped (its proof already went to `archive`).

## 4. meta  (DB — LIVE)  — the one dial (exactly ONE row)
    PLAIN    The single dial: what phase we're in and which unit is current.
             Everything reads it. It must exist in ONE place — the old system kept
             3 copies that disagreed, and that was a top bug.
    HOLDS    current_unit, phase (SCAN|LOOP|GRADUATION), target
    READS    every step
    WRITES   map · route · distill  (code only; never duplicated)
    LIFE     LIVE.

## 5. probes  (DB — PERSIST)  — the diary (one row per Q&A)
    PLAIN    The blow-by-blow record of every question asked and every answer
             given, with its grade. Unlike `archive` (which keeps only the final
             outcome per unit), this keeps EVERY exchange, forever. Its data is
             what powers "where has he struggled before?", audits, and spaced
             review — the patterns the tutor exists to catch.
    HOLDS    turn, unit_id, axis, step (probe|test), question, learner_answer,
             verdict, category, timestamp
    READS    grade (recent history for this axis), route (spaced review),
             map/probe (shape questions from past struggle)
    WRITES   grade (append one row every time an answer is judged)
    LIFE     PERSIST — never wiped by a reset. This is the long memory.
    NOTE     the diary is the RICH record; axes.shaky_count is the FAST trigger.
             We keep both by choice (see axes NOTE).

## 6. learner  (DB — PERSIST, never wiped)  — the person
    PLAIN    What we know about the learner as a person. The ONE thing that
             follows him across every reset and every codebase.
    HOLDS    can[], cant[], misconceptions[{belief, disproved_by}]
    READS    map (shape the ladder), probe, teach (pitch to his level), grade
    WRITES   grade (append) · distill (consolidate)
    LIFE     PERSIST across everything.
    NOTE     simplified to three fields. ('shown' — exposed-but-unproven — was
             dropped; re-add only if we enforce the "don't use an unproven term"
             law.)

## 7. archive  (folder — PERSIST)  — the permanent proof
    PLAIN    The permanent record of finished units: what we tested and the proof
             he understood. This is WHY wiping working memory is safe.
    HOLDS    per unit: {unit, title, logical_document, final_verdict,
             axes_tested, tests, evidence, event_log, workspace_snapshot,
             resume_at?} — one titled artifact directory per unit
    READS    route (spaced review later), the learner
    WRITES   distill (on OWNED or park; atomically receives sealed events)
    LIFE     PERSIST — the record that makes a wipe safe.

## 8. handoff  (DB — PERSIST)  — the "what to start next" note (its own stone)
    PLAIN    An authoritative SQLite record that tells the next session exactly
             what to begin with and gives it the context to start strong. A fresh
             cold context reads this first instead of reconstructing from raw rows.
    HOLDS    next_unit (what to start with) + a short why/context +
             dive_depth ("we're N levels deep in X, mid-dive") +
             open sibling holes + a one-line learner note (what to watch) +
             resume_stack[] when a session is parked: exact stack frames
             {unit_id, axis, state, resume_q, pending, hop_budget,
              evidence_refs, workspace_revision} + continuation
             {next_step, awaiting, outstanding_question_ref?, context_refs[]}
    READS    the next context at warm-start (read FIRST)
    WRITES   distill (every reset)
    LIFE     PERSIST until the next start consumes/overwrites it. On PARK, the
             stack fact MOVES here from live (3 stack), so it has one home.
             Code writes the continuation only at a safe boundary: after an
             agent return, saved learner event, or committed guarded action.
             It never snapshots an in-flight agent/tool transaction.

## 9. codebase  (READ-ONLY)  — the textbook
    PLAIN    The real target code the learner is mastering. We only ever READ it;
             the tutor never edits it during a lesson.
    HOLDS    the real target code
    READS    map, point, probe, teach, test, grade
    WRITES   nobody
    LIFE     READ-ONLY.

## 10. schemas  (READ-ONLY)  — the blank forms
    PLAIN    One blank form per return stamp. When an agent finishes, it asks for
             the form's PATH, opens it, and fills it. Keeps every output in a
             known shape; the harness validates against it.
    HOLDS    schema/return.map · schema/return.grade · schema/return.distill
    READS    an agent, AFTER get_schema(task) → a path → opens it
    WRITES   design-time only (not written at runtime)
    LIFE     READ-ONLY. Delivered as a PATH, never baked into a prompt.

## 11. workspace  (file — LIVE)  — the learner's one visible document
    PLAIN    The learner writes code in one logical document with one stable UI
             name (for example, `solution.py`). The interface never makes him
             juggle archive files or generated names. Internally this document
             has a stable `document_id`; unit archives save representative
             snapshots/diffs under a human-readable archive title.
    HOLDS    document_id, display_name, language/extension, current content,
             current revision/hash, plus hidden revision checkpoints for every
             test-run revision. The learner sees only the one stable document.
    READS    action hooks, probe, teach, test, grade, distill
    WRITES   learner editor actions through the guarded workspace service
    LIFE     LIVE and mutable. Never reset between tests: learner edits and tests
             the same document continuously. Unit close archives the final file
             plus test-linked checkpoints; a route may reset the visible document
             only through an explicit next-unit workspace-template policy.

## 12. events  (DB — LIVE → ARCHIVED)  — the automatic activity trace
    PLAIN    The application records every learner command, edit, test result,
             error, UI action, and code-side feedback automatically. This is
             distinct from `probes` (the semantic Q&A diary). An event belongs
             to exactly one active unit while live.
    HOLDS    event_id, unit_id, axis?, document_id, kind, action payload,
             output/diff/snapshot reference, policy outcome, timestamp
    READS    action hooks, probe/teach/test/grade when event evidence matters,
             distill (to build the unit artifact)
    WRITES   event recorder [CODE], automatically, for every observed action
    LIFE     LIVE while the unit is active. On OWNED/PARK, code atomically seals
             and MOVES the unit's raw event stream into that unit's archive
             artifact, then removes the live rows. The event has one home at a
             time: events while active; archive after closure.
    NOTE     The archive manifest carries a reflective title; the learner's
             visible workspace filename never changes.

---

## NOT A STONE — snapshot (the per-turn wakeup input)
    The old "stone 0". It is assembled fresh each turn from the stones above +
    the learner's message, handed to one agent, then thrown away. It stores
    nothing new. It lives in CATALOGS.md (what a wakeup packs), not here.

---

## WHAT CHANGED FROM THE OLD STONE LIST (surgery record)
- CUT `codebase-map` folder — it duplicated units+axes (DB). The map IS the DB.
- DEMOTED `snapshot` — it's per-turn wakeup input, not stored data.
- CUT `kind` (TARGET/TRANSIT) field — the firing axis-set already encodes it.
- SIMPLIFIED `learner` to can/cant/misconceptions (dropped `shown`).
- RENAMED to single clean nouns; renumbered 1–9.
- All three cuts were taken on recommendation (one-home-per-fact rule) and are
  reversible if a real reader/writer for them turns up.
- ADDED `workspace` (11): the learner's single logical document needs one home.
- ADDED `events` (12): automatic commands/edits/tests/errors need a distinct
  home from the semantic Q&A diary; each event moves into archive on unit close.

## RESOLVED (was OPEN)
- [x] `probes` diary → YES, build it (stone 5). Its data plays a big role:
      cross-unit struggle patterns, audit, spaced review.
- [x] `shaky_count` → KEEP as a stored number on `axes`, NOT derived. It's the
      fast trigger cell (trips code at 2). Diary and counter coexist by choice.
- [x] `handoff` → KEEP as its own stone (8). A "what to start next" + context
      file makes a cold context start powerful. Now also holds dive_depth.

## STILL OPEN
- [ ] exact evidence_bar per axis (what counts as "proof" for each of the 7 axes).
- [ ] hop_budget mechanics: shrink amount per SHAKY, floor value.
