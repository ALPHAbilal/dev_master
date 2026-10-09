# MAPPER (Scanner Agent) — Design

Status: **proposal for review**. Nothing here is implemented yet.
Constraint: **strictly additive**. The engine "stones" (units/axes/stack/probes/meta),
the wakeup→gateway→validate→commit anatomy, and every other agent are untouched.
This doc changes only what the MAPPER step fills into that existing skeleton.

---

## 0. Why this agent is hard

The old design let a human set "number of milestones." That number papered over the
one judgment that is actually the whole product: **how many rungs, and where each one
starts and stops.** That feature is removed. MAPPER now owns that judgment alone.

So the design is driven by one question — *what is the best way to master an IT skill?* —
and everything (tools, context, prompt) falls out of the answer.

---

## 1. First-principles foundation (from learning science)

Mastery of any technical skill stacks three mechanisms:

1. **Chunking.** Experts hold the same facts as novices, *recoded into fewer meaningful
   units.* Working memory is ~4–7 chunks. A rung must be **one chunk** — one idea you
   could give a single name — not "lines 40–120."
2. **Threshold concepts.** A few ideas are *troublesome, transformative, integrative,
   irreversible* — gateways that reorganize everything downstream. Most code is glue.
   MAPPER must **find the gateways and skip the glue**, not cut the file evenly.
3. **Active model-building, one component at a time.** Comprehension = building a model
   of structure → flow → behavior. Schemas can't form passively. This is why each rung is
   graded across depth axes (deliberate practice on one chunk).

Sources: Von Mayrhauser & Vans (program comprehension / mental models); Miller (7±2 chunking);
Sorva (threshold concepts in programming); cognitive-load research.

### The rung definition (this replaces the human count)

> **One rung = one threshold-bearing chunk of this code.**
> A span is one rung iff it (a) **recodes into a single named idea**, (b) is
> **load-bearing** (understanding it changes how you read the rest — not glue), and
> (c) is **independently gradeable** on the axes. If a span can't be graded as one
> idea → it's two rungs. If two spans can't be understood apart → they're one rung.

Ordering rule: **order = dependency order** — rung B after rung A only if you must
understand A before B is even comprehensible (the integrative structure of thresholds).

---

## 2. The one fact that shapes everything

Every other agent has its code **pushed into** the wakeup packet (`context["source"]` =
one unit's slice). MAPPER is different: a rung is a chunk it must **discover**, so MAPPER
**pulls** code through tools and explores the whole repo itself.

```
  TEACHER / JUDGE:  code PUSHED into context["source"]   (one unit slice, given)
  MAPPER:           code PULLED via tools                 (whole repo, its own calls)
```

This is why MAPPER gets new read/list tools and does NOT use `read_code_slice`.

---

## 3. The agent, filled into the shared anatomy

```
                          MAPPER — step "wakeup.map"
 ═══════════════════════════════════════════════════════════════════════════

  ┌─ CONTEXT (read-only, in the packet) ────────────────────────────────────┐
  │  target            entry file/dir to map                                │
  │  repository_root   the jail boundary for every tool                     │
  │  axes              the AXES catalog + wording (valid vocabulary)         │
  │  return_schema     the return.map shape + ONE worked example            │
  │  ── NO "source" ── MAPPER fetches code itself via tools                  │
  └─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  ┌─ INSTRUCTION (system prompt = the pedagogy, §5) ────────────────────────┐
  │  rung = threshold chunk · skip glue · trace before you cut ·            │
  │  order = dependency · grade-ability = granularity test                 │
  └─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
  ┌─ CAPABILITIES (tools — §4) ─────────────────────────────────────────────┐
  │  list_repository()          NEW   walk the tree (structural model)      │
  │  read_file(path)            NEW   read actual code (fixes source gap)   │
  │  search_repository(query)   HAVE  grep, trace symbols across files      │
  └─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┴───────────────────────────┐
        │  EXPLORATION LOOP (multi-turn; native to the run loop)  │
        │   list ─▶ read ─▶ search how they call each other ─▶    │
        │   build mental model ── repeat until code understood ── │
        │   each call → gateway re-checks grant, returns JSON or  │
        │   REFUSED, and streams thinking/tool events to the UI   │
        └─────────────────────────────────────────────────────────┘
                                    │  model complete → emit
                                    ▼
  ┌─ RETURN (return.map — validated by _validate_map, §6) ──────────────────┐
  │  mode="initial"  (never "extend" for top-level rungs)                   │
  │  units:[{slug,title,file,lo,hi,depth=0,parent=null,axes[...]}]          │
  │  order = dependency order (must equal unit slug order)                  │
  └─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
     orchestrator.commit_map  →  units + journey  →  LADDER FROZEN
                    (deepening later = subunits depth>0, a separate op)
```

### Each choice traced to the pedagogy

| Pedagogy mechanism                         | Design consequence                                    |
|--------------------------------------------|-------------------------------------------------------|
| Rung is a chunk to **discover**            | pull code via `read_file` / `list_repository`         |
| Thresholds are **integrative** (X↔Y)       | `search_repository` to trace calls/data flow          |
| **Build model before cutting**             | multi-turn explore loop, emit last (not one-shot)     |
| **Order = understood-first**               | `order` = dependency order (contract enforces)        |
| **Grade-ability = granularity test**       | every unit carries `axes`; ungradeable span ≠ 1 rung  |
| Chunks fit **working memory**              | flat ladder (depth=0); deepen later, locally          |
| Coherence (one mind, one pass)             | `mode="initial"` always; never `extend`               |

---

## 4. Tools accessible to MAPPER

Allowlist for `wakeup.map` becomes exactly these three (drops the broken
`read_code_slice`, keeps `search_repository`, adds two):

| Tool                     | Args (SDK schema)   | Returns                                   | Jail |
|--------------------------|---------------------|-------------------------------------------|------|
| `list_repository`  (NEW) | none `{}`           | `{tree:[{path,bytes,lines}]}`             | root |
| `read_file`        (NEW) | `{path: str}`       | `{path, lines:[...], line_count}`         | root |
| `search_repository`(HAVE)| `{query: str}`      | `{matches:[{file,line,text}]}` (50-cap)   | root |

Rules (identical to the existing gateway discipline):
- Every path is resolved against `repository_root` and rejected with `REFUSED` if it
  escapes the jail (`is_relative_to`), same as `_search_repository` does today.
- Symlinks skipped; binary/oversize files rejected by `read_file`.
- On any rejection the tool returns `REFUSED: <reason>` with `is_error: true` — the agent
  sees it and adapts; no exception crosses the boundary.
- Line numbers in `read_file` are **1-based** so the `lo`/`hi` the agent emits map
  directly onto what `_validate_map` expects (`lo>=1`, `hi>=lo`).

`read_code_slice` is intentionally **not granted** to `wakeup.map` (it returns
`context["source"]`, which the map packet does not set — the current latent bug).

---

## 5. System prompt (authored instruction — draft for review)

Replaces the one-line placeholder in `DEFAULT_INSTRUCTIONS["wakeup.map"]`.

```
You are the MAPPER. You turn a codebase into a learning ladder: an ordered list
of rungs a learner will climb to master this code.

WHAT A RUNG IS
A rung is ONE threshold-bearing chunk: a single idea you can name in a few words
("the pinned-first dedupe", "the retry-with-backoff loop"). A span is one rung only if:
  - it recodes into a single named idea (not "some lines"),
  - it is load-bearing: understanding it changes how the rest reads. Skip glue
    (imports, boilerplate, trivial getters) — glue is never a rung,
  - it can be graded on its own across the axes. If a span can't be graded as one
    idea, it is two rungs. If two spans can't be understood apart, they are one rung.
Do not aim for a fixed count. The code decides how many rungs exist.

HOW TO WORK
1. list_repository to see structure. read_file to read the real code. search_repository
   to trace how pieces call and depend on each other.
2. Build a mental model of structure -> control flow -> behavior BEFORE you cut anything.
3. Only then choose the rungs and order them.

ORDER
order = dependency order. Rung B comes after rung A only if a learner must understand
A before B is even comprehensible. This is NOT file order.

AXES
Tag each rung with the axes on which it can be meaningfully tested. Valid axes:
COMPREHEND, MECHANISM, RATIONALE, JUDGMENT, ROBUSTNESS, INTEGRATION, EVOLUTION.

OUTPUT
Return exactly one return.map JSON object and nothing else. mode is always "initial"
and continues_after is null. units are all top-level: depth=0, parent=null. order must
list the unit slugs in exactly the dependency order of units. Every lo/hi must be real
1-based line numbers from a file you actually read.
```

(Few-shot: attach one worked example in `context.return_schema` rather than the prompt,
so the schema and its example live together — see §6.)

---

## 6. Context packet shape

Built in `WakeupBuilder.build()` under the `step == "wakeup.map"` branch. Today it is
`{target, repository_root}`. Proposed:

```json
{
  "target": "run_prompts.py",
  "repository_root": "/data/codebases/<slug>",
  "axes": {
    "catalog": ["COMPREHEND","MECHANISM","RATIONALE","JUDGMENT",
                "ROBUSTNESS","INTEGRATION","EVOLUTION"],
    "wording": { "COMPREHEND": "What it does", "MECHANISM": "How it works",
                 "RATIONALE": "Why it's built this way",
                 "ROBUSTNESS": "What can break", "...": "..." }
  },
  "return_schema": {
    "shape": "see return.map",
    "example": { "kind":"return.map", "target":"...", "mode":"initial",
                 "continues_after": null, "objective_covered": true,
                 "units": [ /* one worked unit */ ], "order": ["..."] }
  }
}
```

No `source` key. `axes.catalog` MUST equal the engine's `AXES` (single source of truth in
`contracts.py`) — build it from that constant, don't hand-copy, so they never drift.

---

## 7. Return schema (already enforced — MAPPER must match it)

`_validate_map` (contracts.py) requires, verbatim:

```
top level: { kind, target, mode, continues_after, objective_covered, units, order }
  mode              in {"initial","extend"}         -> MAPPER always "initial"
  continues_after   null when initial               -> always null for us
  objective_covered bool
  units[]           non-empty; each:
        { slug, file, lo, hi, depth, parent, axes, title? }
        depth == 0 and parent == null   (enforced: "MAPPER units must be top-level")
        lo >= 1, hi >= lo
        axes: non-empty subset of AXES
        slugs unique
  order             == the list of unit slugs, in dependency order (exact match)
```

The `extend`/`continues_after` machinery exists in the contract but we **do not use it**
for top-level rungs — that is the "continue from a line drawn by a previous scan" seam we
rejected. Full coherent scan = `mode:"initial"` every time.

---

## 8. Where the content goes (additive change map)

| # | File | Change | Kind |
|---|------|--------|------|
| 1 | `packets.py:18` `STEP_CAPABILITIES["wakeup.map"]` | `("read_file","list_repository","search_repository")` | edit tuple |
| 2 | `packets.py:70-76` build() map branch | add `axes` + `return_schema` to context (from `contracts.AXES`) | additive |
| 3 | `sdk_runtime.py` `TutorToolGateway.call` | add `read_file` + `list_repository` handlers (jailed like `_search_repository`) | additive |
| 4 | `sdk_runtime.py` `_sdk_tools` | add schema `{"path": str}` for `read_file`; `list_repository` takes none | additive |
| 5 | `session.py:39` `DEFAULT_INSTRUCTIONS["wakeup.map"]` | replace placeholder with §5 prompt (or a `map_instructions.py` like `aside_instructions.py`) | edit string |
| 6 | tests | new `test_mapper_gateway.py` (jail, read_file, list) + a `_validate_map` happy-path fixture | additive |

Explicitly **NOT** touched: `contracts._validate_map` (already correct), `orchestrator.commit_map`,
the frozen-ladder / deepening logic, any other agent, the DB schema, the stones.

Note on prompt wiring: `factory.build_session` (factory.py:61) does not pass an
`instructions` override, so editing `DEFAULT_INSTRUCTIONS` is what actually takes effect.
`SessionRunner` already merges `{**DEFAULT_INSTRUCTIONS, **(instructions or {})}` (session.py:76),
so a future override path exists without changing the wiring now.

---

## 9. Two commitments to confirm before implementing

1. **Add `read_file` + `list_repository`** to the gateway (the additive fix that retires the
   broken `read_code_slice` path for map). — agree?
2. **Flat ladder on first scan** (`depth=0`, `mode="initial"`); deepening is a separate later
   operation on an existing rung. — agree?

Open sub-questions worth a line each:
- `list_repository`: whole-tree in one shot, or accept an optional subdir arg for large repos?
- `read_file`: cap max lines/bytes at what limit before it must `search` instead?
- Few-shot example: keep it in `context.return_schema` (my pick) or inline in the prompt?
```