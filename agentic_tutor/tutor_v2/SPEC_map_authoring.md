# BUILD SPEC — Agent-filled map (Tier 2)

A cold agent can execute this top to bottom. Do the steps IN ORDER; each compiles before
the next. All paths are relative to `agentic_tutor/tutor_v2/`. Line numbers drift — grep for
the named symbol.

---

## 0. Orientation (read before touching anything)

The engine teaches one code unit at a time. Per turn it builds a **wakeup** (scoped context
+ tool allowlist), an agent returns a validated **stamp**, and code routes deterministically.
A live **semantic graph** (nodes + edges) is the "map" the UI renders.

Key files:
- `packets.py` — `WakeupBuilder` builds the per-step packet. **The law:** each step rents only
  the context its phase needs (`_unit_context`). Do NOT widen it.
- `contracts.py` — `validate_return` + `_validate_grade`/`_validate_distill`. All agent output
  is validated here before any write.
- `semantics.py` — `SemanticGraphService`, the ONLY writer of nodes/edges. Enforces the
  node-kind and relationship vocabulary; agent-provenance nodes/edges REQUIRE `evidence_refs`.
- `graph_projection.py` — `GraphProjection`, mirrors validated turns into the graph. Runs
  INSIDE each turn's DB transaction; must stay total and non-throwing.
- `orchestrator.py` — `TurnOrchestrator`, owns the transactions; calls the projection.
- `routing.py` — the Router. **Do not modify.**

The model this spec implements: **code owns all graph topology and every cross-turn edge; the
agent fills only the text of the one node its current phase is about, using only what that
phase already rents.** This is the only model compatible with the rented-context law.

Existing signatures you will use (verify by reading the file):
```
SemanticGraphService.add_node(*, journey_id, kind, title, provenance, unit_id=None,
    summary=None, source_ref=None, evidence_refs=None, status="active") -> int
SemanticGraphService.add_edge(*, journey_id, from_node_id, to_node_id, relationship_type,
    provenance, label=None, explanation=None, evidence_refs=None) -> int
GraphProjection.on_grade(*, journey_id, unit_id, axis, turn_id, category, hidden_gap, probe_id)
GraphProjection._anchor(journey_id, unit_id) -> int      # find-or-create unit's system anchor
GraphProjection._link(journey_id, from_id, to_id, relationship, evidence)  # idempotent edge
```
Vocabulary already allowed (`semantics.py`): node kinds include `concept, mechanism,
misconception, takeaway, prerequisite, test`; semantic relationships include
`proved_by, revealed_gap_in, depends_on, disproved_by, detoured_to, returned_to`.

---

## 1. Design (the contract this build produces)

### Emission table (code-owned; exactly one agent node per grade)
| grade `category` | node kind | edge (from `@unit` anchor) | agent text |
|---|---|---|---|
| correct-deep | takeaway | proved_by | required |
| working-code-wrong-reasoning | mechanism | revealed_gap_in | required |
| misconception | misconception | revealed_gap_in | required |
| different-prereq | prerequisite | depends_on | required |
| sibling-hole | prerequisite | revealed_gap_in | required |
| (the 10 others) | — none — | — | `map_text` = null |

Node-emitting set: `MAP_NODE_CATEGORIES = {correct-deep, working-code-wrong-reasoning,
misconception, different-prereq, sibling-hole}`.

### `map_text` shape (new field on `return.grade`)
```
map_text : { "title": <non-empty str>, "summary": <non-empty str> }   # iff category emits a node
         : null                                                        # otherwise
```
Always present in the stamp (null when no node) — same rule as the existing `hidden_gap`.

### Invariants (must all hold at the end)
1. Rented-context law untouched: no change to `packets.py` context or capabilities.
2. Code owns topology + all cross-turn edges (`detoured_to`, `returned_to`, `disproved_by`).
3. Atomic: `map_text` validated in `validate_return` BEFORE the txn; map writes ride the
   turn's existing txn; an invalid stamp fails the turn as it does today (no new failure class).
4. Idempotent: turn-level guards already run each projection once per turn.

---

## 2. Execution steps (in order)

### STEP A — `semantics.py`: add a status writer
The service is insert-only; `disproved` needs an update, and it must go through the only writer.
Add a method:
```python
def set_node_status(self, node_id: int, status: str) -> None:
    if status not in {"active", "disproved", "superseded"}:
        raise ValidationError(f"unsupported node status: {status}")
    with self.db.transaction():
        self.db.connection.execute(
            "UPDATE semantic_nodes SET status=?,updated_at=datetime('now') WHERE id=?",
            (status, node_id))
```

### STEP B — `contracts.py`: validate `map_text`
1. Near the other module constants add:
```python
MAP_NODE_CATEGORIES = frozenset({
    "correct-deep", "working-code-wrong-reasoning", "misconception",
    "different-prereq", "sibling-hole",
})
```
2. In `_validate_grade`, add `map_text` to the required key set in `_expect_keys(...)`.
3. After the `hidden_gap` block, validate conditionally:
```python
map_text = stamp["map_text"]
if stamp["category"] in MAP_NODE_CATEGORIES:
    map_text = _expect_object(map_text, "return.grade.map_text")
    _expect_keys(map_text, required={"title", "summary"}, optional=set(),
                 label="return.grade.map_text")
    _string(map_text["title"], "return.grade.map_text.title")
    _string(map_text["summary"], "return.grade.map_text.summary")
elif map_text is not None:
    raise ValidationError("map_text must be null when the category emits no node")
```

### STEP C — `schemas/return.grade.json`: mirror it
Add to `"required"`: `"map_text"`. Add to `"properties"`:
`"map_text":{"type":["object","null"]}`. (`additionalProperties` is false — it must be listed.)

### STEP D — `graph_projection.py`: use agent text + add distill/cross-turn emitters
1. In `_GRADE_EMISSION`, change the `working-code-wrong-reasoning` value from
   `("misconception", "revealed_gap_in")` to `("mechanism", "revealed_gap_in")`.
2. Change `on_grade` to accept `map_text` and use it:
```python
def on_grade(self, *, journey_id, unit_id, axis, turn_id, category, hidden_gap,
             probe_id, map_text):
    spec = _GRADE_EMISSION[category]
    if spec is None:
        return
    node_kind, relationship = spec
    evidence = [f"probe:{probe_id}", f"turn:{turn_id}"]
    anchor = self._anchor(journey_id, unit_id)
    node_id = self.graph.add_node(
        journey_id=journey_id, unit_id=unit_id, kind=node_kind,
        title=map_text["title"], provenance="agent",
        summary=map_text["summary"], evidence_refs=evidence)
    self._link(journey_id, anchor, node_id, relationship, evidence)
```
   Delete the now-unused `_grade_node_text`.
3. Add `on_distill` (closes the seal + disproved-misconception gaps). `axes_tested` and
   `misconceptions` come from the validated distill stamp; `event_ref` is a stable evidence
   string for this seal (e.g. `f"unit_distilled:{unit_id}"`).
```python
def on_distill(self, *, journey_id, unit_id, axes_tested, misconceptions, event_ref):
    evidence = [event_ref]
    anchor = self._anchor(journey_id, unit_id)
    for axis in axes_tested:
        node_id = self.graph.add_node(
            journey_id=journey_id, unit_id=unit_id, kind="takeaway",
            title=f"Owned: {axis}", provenance="agent",
            summary=f"Sealed the {axis} axis", evidence_refs=evidence)
        self._link(journey_id, anchor, node_id, "proved_by", evidence)
    for m in misconceptions:
        row = self.graph.db.one(
            "SELECT id FROM semantic_nodes WHERE journey_id=? AND kind='misconception' "
            "AND title=? ORDER BY id LIMIT 1", (journey_id, m["belief"]))
        if not row:
            continue
        self.graph.set_node_status(int(row["id"]), "disproved")
        # disproved_by edge: anchor -> the disproved node (evidence: how it was disproved)
        self._link(journey_id, anchor, int(row["id"]), "disproved_by",
                   evidence + [f"disproved_by:{m['disproved_by']}"])
```
4. Add the two code-owned cross-turn edges:
```python
def on_detour(self, *, journey_id, parent_unit_id, child_unit_id, probe_id, turn_id):
    evidence = [f"probe:{probe_id}", f"turn:{turn_id}"]
    parent = self._anchor(journey_id, parent_unit_id)
    child = self._anchor(journey_id, child_unit_id)
    self._link(journey_id, parent, child, "detoured_to", evidence)

def on_parent_resume(self, *, journey_id, child_unit_id, parent_unit_id, event_ref):
    evidence = [event_ref]
    child = self._anchor(journey_id, child_unit_id)
    parent = self._anchor(journey_id, parent_unit_id)
    self._link(journey_id, child, parent, "returned_to", evidence)
```

### STEP E — `orchestrator.py`: wire the calls (all gated on `self.graph_projection is not None`)
1. `submit_answer` — the existing `on_grade(...)` call: add `map_text=stamp["map_text"]`.
2. `submit_answer` — in the POST-COMMIT block that already runs
   `if decision.unit_id is not None and decision.unit_id != unit_id:` (the child-detour case,
   right after `attach_unit_structure`), also call:
   ```python
   self.graph_projection.on_detour(journey_id=journey_id, parent_unit_id=unit_id,
       child_unit_id=decision.unit_id, probe_id=probe_id, turn_id=turn_id)
   ```
   (Post-commit, so the child anchor exists. `probe_id`/`turn_id` are in scope from the turn.)
3. `commit_distill` — inside the txn, after `apply_diff`, add:
   ```python
   if self.graph_projection is not None:
       self.graph_projection.on_distill(journey_id=journey_id, unit_id=unit_id,
           axes_tested=stamp["axes_tested"],
           misconceptions=stamp["learner_diff"]["misconceptions"],
           event_ref=f"unit_distilled:{unit_id}")
   ```
4. `finish_child` — inside the txn, when a parent is resumed
   (`decision.unit_id is not None and decision.resume_question is not None`), add:
   ```python
   if self.graph_projection is not None:
       self.graph_projection.on_parent_resume(journey_id=journey_id,
           child_unit_id=child_unit_id, parent_unit_id=decision.unit_id,
           event_ref=f"parent_resumed:{decision.unit_id}")
   ```

### STEP F — `session.py`: tell the JUDGE to fill `map_text`
Extend `DEFAULT_INSTRUCTIONS["wakeup.grade"]` to state: when the category emits a node
(the 5 in `MAP_NODE_CATEGORIES`), include `map_text:{title,summary}` naming the concept the
verdict establishes; otherwise `map_text:null`. (This is the fallback prompt; a deployment's
authored JUDGE role prompt overrides it.)

---

## 3. Tests (add under `tests_v2/`)
- `contracts`: node-emitting category with `map_text=null` → `ValidationError`; non-emitting
  category with non-null `map_text` → `ValidationError`; valid pair passes.
- `graph_projection`: `on_grade` writes a node whose title/summary are the agent's verbatim,
  evidence includes `probe:<id>`; the `_GRADE_EMISSION` exhaustiveness test still passes with
  the `mechanism` change.
- `graph_projection`: `on_distill` flips a matching misconception to `disproved` + adds a
  `disproved_by` edge, and adds one `takeaway` per tested axis.
- `orchestrator`: a full grade turn with `map_text` produces the node inside the same txn;
  a replayed grade turn adds no duplicate node (existing idempotency guard).
- `orchestrator`: a child-dive turn adds a `detoured_to` edge; a `finish_child` that resumes
  a parent adds a `returned_to` edge.

## 4. Definition of done
- All existing `tests_v2/` pass, plus the new tests above.
- `grep -n _grade_node_text graph_projection.py` returns nothing (removed).
- No diff in `routing.py`, `packets.py`, `schema.sql`, `journey_reader.py`.
- Run: `cd agentic_tutor && .venv/bin/python -m pytest tests_v2/ -q` (create the venv per
  `BUILD_PLAN.md` if absent).

## 5. Non-goals (do not build)
- No `map_text` on teaching; the `explanation` node stays out of scope.
- No agent-authored edges; agents never emit topology.
- No new distill contract field; `on_distill` uses fields the DISTILLER already returns.
- No new capabilities or wakeup context.
