# SPEC — Agent-filled map (Tier 2)

Deterministic topology, agent-filled text. Code owns every node/edge and all cross-turn
wiring; the agent fills only the prose of the one node its current phase is about, using
only what that phase already rents. This is the sole model compatible with the
rented-context law (`packets.py::_unit_context`).

## Anatomy change (bounded)

One field on one agent: `return.grade` gains a conditional `map_text`. The JUDGE becomes
grader **+ one-line narrator of the node its verdict creates**. No new agent, phase, tool,
or context channel. DISTILLER enriches from fields it already returns. Teaching unchanged.

## Emission table (code-owned; one agent node per grade)

| grade `category` | node emitted | edge (to `@unit`) | agent slot required |
|---|---|---|---|
| correct-deep | takeaway | proved_by | `map_text` |
| working-code-wrong-reasoning | mechanism | revealed_gap_in | `map_text` |
| misconception | misconception | revealed_gap_in | `map_text` |
| different-prereq | prerequisite | depends_on | `map_text` |
| sibling-hole | prerequisite | revealed_gap_in | `map_text` |
| all 10 others | — (no node) | — | `map_text` = null |

Table is **total** over `GRADE_CATEGORIES` (enforced by the existing exhaustiveness test on
`_GRADE_EMISSION`). Cross-turn edges (`disproved_by`, `returned_to`, `detoured_to`) are
emitted by code from journey state — never by an agent.

## Contract (`contracts.py`, `schemas/return.grade.json`)

Add optional `map_text` to `return.grade`:

```
map_text : { "title": <non-empty str>, "summary": <non-empty str> }  |  null
```

Conditional rule (mirrors `hidden_gap`): non-null iff `category` is a node-emitting row
above; else null. Validation lives in `_validate_grade`. No other stamp changes.

## Projection (`graph_projection.py`)

- `on_grade`: read node kind + relationship from the table; take `title`/`summary` from
  `map_text` **instead of** `_grade_node_text` synthesis; engine stamps
  `provenance="agent"`, `evidence_refs=[probe:<id>, turn:<id>]`. `@unit` = existing anchor.
- `on_distill` (new, closes GAP 1+2, no new agent field):
  - `takeaway` node per `axes_tested` (proved_by → `@unit`); title from axis wording.
  - for each `learner_diff.misconceptions[]`: find the journey's misconception node by
    title == `belief`; set `status="disproved"`; add `disproved_by` edge (evidence = the
    distill event). If no match, skip (best-effort).
  - `returned_to` edge on parent resume (structural, no text).

## Wiring (`orchestrator.py`)

- `submit_answer`: pass `stamp["map_text"]` into `on_grade` (inside the existing txn).
- `commit_distill`: call `on_distill` (inside the existing txn), gated on
  `graph_projection is not None` like the current calls.
- No Router change. No `schema.sql` change (columns exist).

## Invariants preserved

1. Rented-context law — JUDGE authors text only about this turn, from context it already
   rents. No journey-wide context, no new tool.
2. Code owns topology + all cross-turn wiring.
3. Atomic safety — `map_text` is validated in `validate_return` **before** the txn; an
   invalid stamp fails the turn exactly as today (no new failure class). Map writes stay
   inside the turn txn and cannot introduce a partial state.
4. Idempotent — turn-level guards already make projection run once per turn.

## Non-goals (v1)

- No `map_text` on teaching (no teach stamp; `explanation` node stays code-derived).
- No agent-authored edges or cross-turn links.
- No agent-supplied text on the distill path (uses existing fields).
- `decision` / `failure` node kinds remain unused until a trigger is defined.

## Tests

- Exhaustiveness: every `GRADE_CATEGORIES` member has a table row.
- Conditional contract: node-emitting category with `map_text=null` → ValidationError;
  non-emitting category with non-null `map_text` → ValidationError.
- `on_grade` uses agent title/summary verbatim, evidence points at the turn's probe.
- `on_distill`: disproved misconception flips status + edge; takeaway per tested axis.
- Replay a graded turn → no duplicate node (existing guard).
