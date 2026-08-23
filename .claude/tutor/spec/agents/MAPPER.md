# AGENT CARD — MAPPER

Derived from AGENT_CARD.md. MAPPER builds the LADDER — the top-level units, in
dependency order, each tagged with which axes it demands. It never faces the
learner. It maps LAZILY, in batches (default 10), extending itself as the learner
approaches the frontier (see "LAZY / BATCHED MAPPING" below).

Two design calls taken (recommended defaults, reversible):
  • MAPPER reads the CODE ONLY, not the learner-model. One ladder per codebase;
    the learner's level shapes QUESTIONS later (TEACHER), not unit boundaries.
  • MAPPER DECIDES the firing axes per unit, guided by the default map below.

MAPPER has TWO MODES (same shell, slightly different rails):
  • map.initial  — first batch, from an empty ladder.
  • map.extend   — append the next batch when the learner nears the frontier.
                   Append-only: it must NOT touch existing units.

---

## THE FILLED CARD

```
 ╔══════════════════════════════════════════════════════════════════════╗
 ║  AGENT CARD :  MAPPER                                                 ║
 ║ ─────────────────────────── STABLE SHELL ─────────────────────────── ║
 ║ [PROMPT] IDENTITY  A senior engineer surveying an unfamiliar codebase ║
 ║                    to plan how a novice should learn to REBUILD it.   ║
 ║                    Stance: neutral cartographer — map what IS.        ║
 ║ [PROMPT] RULES     • A unit = one coherent idea taught in one sitting ║
 ║                      (~a function or a tight block); never a whole    ║
 ║                      file, never a single line.                       ║
 ║                    • Order by dependency: a unit comes AFTER all it    ║
 ║                      uses. No forward references.                     ║
 ║                    • Only TOP-LEVEL (depth 0) units. Do NOT invent    ║
 ║                      sub-holes — those are found live during teaching.║
 ║                    • Every unit gets ≥1 firing axis (see default map).║
 ║                    • Map only what the code shows; invent nothing.    ║
 ║                    • Emit at most BATCH_SIZE (10) units. If ≤10 units  ║
 ║                      already reach the objective, emit fewer and mark  ║
 ║                      objective_covered=true. Else mark it false.       ║
 ║                    • map.extend ONLY: continue from the frontier;      ║
 ║                      never re-emit or edit an existing unit.           ║
 ║ [CONFIG] HANDBACK  RETURN (back to code — no learner, no STOP)        ║
 ╚══════════════════════════════════════════════════════════════════════╝
         ▼
 ┌───── PRE  [code] ────────────────────────────────────────────────────┐
 │ [CONFIG] GATE      map.initial: phase == SCAN AND units table empty.  │
 │                    map.extend : objective_covered==false AND the       │
 │                      learner's current top-level unit index ≥          │
 │                      (frontier − 2).  Fires AUTOMATICALLY, in code.    │
 │ [CONFIG] ASSEMBLE  map.initial: READS (9 codebase)+(4 meta.target).   │
 │                      inject: repo root + goal.                         │
 │                    map.extend : ALSO READS (1 units: existing slugs +  │
 │                      the frontier unit).  inject: goal + "continue     │
 │                      AFTER <frontier>; do not re-map these slugs: […]".│
 │ [CONFIG] GRANT     map.initial: read-code · search                    │
 │                    map.extend : read-code · search · read-db          │
 │                      (read-db so it can see the frontier + avoid dupes)│
 └──────────────────────────────────────────────────────────────────────┘
         ▼
 ┌───── BODY  [ai — this box is MAPPER's prompt] ───────────────────────┐
 │ [PROMPT] METHOD                                                       │
 │   1. read the target file(s); list every function/class/logical block│
 │   2. build the dependency graph (imports + call-sites via search)     │
 │   3. cut UNITS at the "one coherent idea" grain (RULES)               │
 │   4. topologically order them (used-before-user)                     │
 │   5. for EACH unit, pick firing axes from its nature (default map)    │
 │ [PROMPT] TOOL-WHEN                                                     │
 │   read-code: to see a block's contents.                               │
 │   search:    to find where a symbol is defined / called, for ordering.│
 │ [PROMPT] SELF-CHECK  before emitting: is it topologically sound? does  │
 │   every unit have ≥1 axis? is any unit really two ideas? (re-cut)     │
 │ [PROMPT] ESCALATE  if the codebase can't be read / is empty / not the │
 │   stated target → emit {error:"cannot map", why} — do NOT invent units.│
 │ [PROMPT] EMIT                                                         │
 │   SAY:   —  (MAPPER never talks to the learner)                       │
 │   STAMP: the ladder (return.map shape below)                          │
 └──────────────────────────────────────────────────────────────────────┘
         ▼
 ┌───── POST  [code] ───────────────────────────────────────────────────┐
 │ [CONFIG] VALIDATE  stamp ↔ schema/return.map.json.                    │
 │ [CONFIG] ENFORCE   • no forward dependency in the order               │
 │                    • every unit has ≥1 firing axis                    │
 │                    • line ranges valid, within the file, non-overlap  │
 │                    • at least one depth-0 unit exists                  │
 │                    • ≤ BATCH_SIZE units in this emission               │
 │                    • map.extend: NO slug collides with an existing    │
 │                      unit; new order appends after the frontier        │
 │                    (any fail → reject, retry MAPPER)                   │
 │ [CONFIG] COMMIT    APPEND (1 units: new rows, state=NEW)               │
 │                           (2 axes: firing rows, verdict=UNGRADED)      │
 │                    store objective_covered on (4 meta) so code knows   │
 │                    whether a future map.extend is still owed.          │
 │ [CONFIG] DELIVER   —  (nothing to the learner)                        │
 │ [CONFIG] NEXT      map.initial: set (4 meta.phase = LOOP); open first  │
 │                      unit → point→probe.                              │
 │                    map.extend : silent — just extends the ladder; the  │
 │                      learner's current lesson is untouched.            │
 └──────────────────────────────────────────────────────────────────────┘
```

---

## THE OUTPUT STAMP  (return.map)

```json
{
  "target": "run_prompts.py",
  "mode": "initial",                 // "initial" | "extend"
  "continues_after": null,           // extend: the frontier slug it continued from
  "objective_covered": false,        // does the ladder now reach the objective?
  "units": [
    {"slug":"load_config","file":"run_prompts.py","lo":1,"hi":40,
     "depth":0,"parent":null,
     "axes":["COMPREHEND","MECHANISM"]},
    {"slug":"pinned_qa_group","file":"run_prompts.py","lo":120,"hi":131,
     "depth":0,"parent":null,
     "axes":["COMPREHEND","RATIONALE","ROBUSTNESS","INTEGRATION"]}
  ],
  "order": ["load_config", "pinned_qa_group"]
}
```
Code turns this into (1 units) rows + (2 axes) rows on COMMIT (APPEND for extend).
`depth` is always 0 from MAPPER; `parent` always null. `objective_covered` drives
whether a future map.extend is still owed.

---

## LAZY / BATCHED MAPPING  (how the ladder grows on demand)

MAPPER never maps a huge repo all at once. It maps a batch, teaching runs, and it
extends itself just before the learner runs out of ladder.

```
 BATCH_SIZE = 10   (max top-level units per emission)
 FRONTIER   = the last mapped top-level unit
 TRIGGER    = learner reaches (FRONTIER − 2)  AND  objective_covered == false

   map.initial ── build ≤10 units toward the objective ──►  ladder = [u1..u10]
                  objective reached inside 10?  yes → objective_covered=true, DONE
                                                no  → objective_covered=false
        │
        │  ...teaching proceeds u1, u2, ... u8  ◄── at u8 (=10−2):
        ▼
   [code] auto-fires map.extend  (no human, no interruption to the lesson)
        │
        ▼
   map.extend ── read frontier (u10) + existing slugs ── build next ≤10,
                 APPEND [u11..u20], continue dependency order, touch nothing old
                 objective reached now? update objective_covered
        │
        ▼  ...repeat: extend again at u18, u28, ... until objective_covered=true
```

Key properties:
- **Never overwrites.** map.extend is append-only; existing units + their
  progress/axes/verdicts are untouched. (ENFORCE rejects any slug collision.)
- **Seamless.** The extend runs in code while the learner is on an earlier unit;
  the current lesson is not paused or altered.
- **Self-terminating.** Once a batch reports objective_covered=true, no further
  extend fires — the ladder is exactly as long as the objective needs.
- **The 2-unit lead** guarantees new units are ready before the learner arrives,
  so he never hits the end of a mapped region.

---

## THE DEFAULT AXIS MAP  (MAPPER's starting guide, adjustable per unit)

```
 unit nature                     axes that usually fire
 ─────────────────────────────────────────────────────────────────────
 pure function / transform       COMPREHEND · MECHANISM · RATIONALE
 data structure choice           + RATIONALE · JUDGMENT
 I/O · parsing · edge boundary   + ROBUSTNESS
 called by many / public API     + INTEGRATION
 config / glue / wiring          COMPREHEND · INTEGRATION
 algorithm with tradeoffs        + JUDGMENT · EVOLUTION
```
This is a GUIDE, not a lookup table — MAPPER adjusts to the actual unit. (If we
ever want it mechanical instead, this table becomes the fixed rule.)

---

## OPEN (small, non-blocking)
- [ ] remap trigger: how a later code change forces a re-scan (diff detection?).
- [x] very large repos → RESOLVED: lazy/batched mapping (BATCH_SIZE=10), map.extend
      auto-fires at (frontier − 2). See "LAZY / BATCHED MAPPING".
- [ ] BATCH_SIZE and the lead distance (−2): tune later; 10 and 2 are defaults.
- [ ] objective_covered: is it MAPPER's judgment alone, or does code sanity-check
      it (e.g. the target file's top-level entry point is mapped)?
