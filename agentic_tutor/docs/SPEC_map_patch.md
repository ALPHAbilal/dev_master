# BUILD SPEC (PATCH) — stable node identity + code-owned disproval

Fixes two holes left by `SPEC_map_authoring.md`:
- **Hole 1:** the "disproved" mark relied on two different agents writing byte-identical text
  → it never fired. Replace it with a code-owned rule: **when an axis that had a misconception
  (or mechanism) gap is later PROVED, disprove that gap.** No agent string-matching.
- **Hole 2:** "make a dot" always inserted, so grading + sealing stamped the same proved axis
  twice. Give the per-axis "state" dots a **stable identity** and find-or-create them.

Execute IN ORDER. Paths relative to `agentic_tutor/tutor_v2/`. Grep for symbols; lines drift.

---

## Core idea

A dot that represents *the state of one axis* — `takeaway` (proved), `misconception`,
`mechanism` — must be **one per (unit, axis)**. Tag those dots with their `axis` and
find-or-create by `(journey, unit, axis, kind)`. `prerequisite` dots are NOT singletons
(one axis can uncover several distinct prerequisites) — they keep inserting.

Disproval becomes a deterministic cross-turn edge (same family as `detoured_to`/`returned_to`):
proving an axis disproves any still-active gap dot on that same axis.

---

## STEP 1 — `schema.sql`: give nodes an axis tag

In the `semantic_nodes` table add a nullable column:
```sql
axis TEXT,
```
Migration for existing DBs (idempotent — run once at init or by hand):
```sql
ALTER TABLE semantic_nodes ADD COLUMN axis TEXT;   -- ignore "duplicate column" if already applied
```
`JourneyReader` selects `*`, so the column reaches the UI with no reader change.

## STEP 2 — `semantics.py`: persist the axis

`add_node`: add param `axis: str | None = None`; include `axis` in the INSERT column list and
values. No validation needed (free axis tag; the caller supplies a real axis or None).

## STEP 3 — `graph_projection.py`: singletons, find-or-create, disproval

1. Near the top add:
```python
# per-axis "state" dots: exactly one per (unit, axis). prerequisite is intentionally excluded.
_SINGLETON_KINDS = frozenset({"takeaway", "misconception", "mechanism"})
```
2. Add a find-or-create helper for agent state-dots:
```python
def _agent_node(self, *, journey_id, unit_id, axis, kind, title, summary, evidence) -> int:
    if kind in _SINGLETON_KINDS:
        row = self.graph.db.one(
            "SELECT id FROM semantic_nodes WHERE journey_id=? AND unit_id=? AND axis=? "
            "AND kind=? AND provenance='agent' ORDER BY id LIMIT 1",
            (journey_id, unit_id, axis, kind))
        if row:
            return int(row["id"])
    return self.graph.add_node(
        journey_id=journey_id, unit_id=unit_id, axis=axis, kind=kind, title=title,
        provenance="agent", summary=summary, evidence_refs=evidence)
```
3. Rewrite `on_grade` to use it, and to disprove on proof:
```python
def on_grade(self, *, journey_id, unit_id, axis, turn_id, category, hidden_gap,
             probe_id, map_text):
    spec = _GRADE_EMISSION[category]
    if spec is None:
        return
    node_kind, relationship = spec
    evidence = [f"probe:{probe_id}", f"turn:{turn_id}"]
    anchor = self._anchor(journey_id, unit_id)
    node_id = self._agent_node(
        journey_id=journey_id, unit_id=unit_id, axis=axis, kind=node_kind,
        title=map_text["title"], summary=map_text["summary"], evidence=evidence)
    self._link(journey_id, anchor, node_id, relationship, evidence)
    if node_kind == "takeaway":                      # a proof — resolve prior gaps on this axis
        self._disprove_axis_gaps(journey_id, unit_id, axis, node_id, evidence)
```
4. Add the code-owned disproval:
```python
def _disprove_axis_gaps(self, journey_id, unit_id, axis, proof_node_id, evidence) -> None:
    gaps = self.graph.db.query(
        "SELECT id FROM semantic_nodes WHERE journey_id=? AND unit_id=? AND axis=? "
        "AND kind IN ('misconception','mechanism') AND provenance='agent' AND status='active'",
        (journey_id, unit_id, axis))
    for g in gaps:
        self.graph.set_node_status(int(g["id"]), "disproved")
        # the gap was disproved BY the proof
        self._link(journey_id, int(g["id"]), proof_node_id, "disproved_by", evidence)
```
5. Simplify `on_distill`: dedup the takeaway, and **delete the old title-match disproval loop**
   (it was the dead Hole-1 code). It no longer needs `misconceptions`:
```python
def on_distill(self, *, journey_id, unit_id, axes_tested, event_ref) -> None:
    evidence = [event_ref]
    anchor = self._anchor(journey_id, unit_id)
    for axis in axes_tested:
        node_id = self._agent_node(
            journey_id=journey_id, unit_id=unit_id, axis=axis, kind="takeaway",
            title=f"Owned: {axis}", summary=f"Sealed the {axis} axis", evidence=evidence)
        self._link(journey_id, anchor, node_id, "proved_by", evidence)
```
   (Because `takeaway` is a singleton keyed by `(unit, axis)`, if `on_grade` already made the
   proved dot for that axis, this finds it — no second dot. Hole 2 closed.)

## STEP 4 — `orchestrator.py`: drop the unused distill arg

In `commit_distill`, change the `on_distill(...)` call to pass only
`journey_id, unit_id, axes_tested=stamp["axes_tested"], event_ref=...` (remove `misconceptions`).
No other wiring changes; `on_grade`'s call is unchanged (it already passes `axis`).

---

## Tests to update / add (`tests_v2/`)
- **Disproval is code-owned now:** a unit graded `misconception` on axis A (dot created), then
  later graded `correct-deep` on axis A → the misconception dot flips to `disproved` and a
  `disproved_by` edge points from it to the takeaway. **No distill needed.** (This replaces the
  old string-match test, which should be deleted.)
- **No double takeaway:** grade `correct-deep` on axis A, then run `on_distill` with A in
  `axes_tested` → exactly ONE takeaway dot for A.
- **Singleton misconception:** two `misconception` grades on the same (unit, axis) → ONE
  misconception dot (find-or-create), not two.
- **Prerequisite still multiplies:** two prerequisite-emitting grades on one axis → TWO
  prerequisite dots (not deduped) — proves `_SINGLETON_KINDS` excludes it on purpose.
- Existing `_GRADE_EMISSION` exhaustiveness and grade-replay-idempotency tests still pass.

## Definition of done
- All `tests_v2/` pass (`cd agentic_tutor && .venv/bin/python -m pytest tests_v2/ -q`).
- `grep -n "AND title=?" graph_projection.py` returns nothing (the fragile title-match is gone).
- No diff in `routing.py`, `packets.py`, `journey_reader.py`. (`schema.sql` DOES change now.)

## Invariants (unchanged from the base spec)
- Rented-context law untouched; agents still author only `map_text`.
- Topology + all cross-turn edges (now including `disproved_by`) are 100% code-owned.
- One home dot per unit still holds (unchanged).
- Atomic + idempotent: all writes ride the turn's txn; find-or-create makes re-runs no-ops.
