# Tutor — Real Simulation (slice-driven, to react to, then build)

Not a spec. A **trace**. One learner building **the actual target codebase, by hand,
slice by slice.** Shown turn by turn so you can point at any line and say "keep / cut /
change." Once we agree, we build the agentic layer to match — nothing more.

**The core correction from the last draft:** the learner does not do floating drills.
The unit of progress is a **slice of the real project** — a real function/file he must
write. A concept (`enumerate`, `dict.get`) is only ever taught because *some slice needs
it*. The endpoint is reached when the last slice's gate passes — at which point the
whole target codebase exists in his repo, written by his hand.

---

## Part A — The cast and the stores

**Two agents, two stores.**

- **Agent L** — the only one the learner talks to. Teaches, judges, records evidence,
  runs the gate.
- **Agent M** — never seen. Decomposes the target into slices, sequences them, teaches
  the concept gaps a slice needs, writes the next map. Has a research tool.

- **The library** (`*.md` folder) — the PLAN. Owned by M, read-only to L.
- **The DB** — the EVIDENCE + the bank + the slices. Written by tools, read by both.

The learner talks only to L. L touches the world only through **tools** (never shell,
never raw SQL). M touches only tools + the library + the research tool.

**M wakes in three named turns.** Same agent, same core (G2), same tools — only the
injected instruction set differs. There is no separate "scanner agent"; naming the turns
is what keeps that from being re-invented:

| turn | when it fires | writes | frequency over a codebase's life |
|---|---|---|---|
| **M/SURVEY** | a target is adopted | the spine: `target` row, `slices`, the concept DAG, `target.md` | **once**, plus rare repairs |
| **M/PLAN** | frontier.md is empty (a slice closed) | `frontier.md` — the next slice + its gap | once per slice |
| **M/SUBHOLE** | a handoff cell is filled (F4) | a sub-gap under the untouched `slice:` line | 0–2 per slice, capped |

```
target adopted ──► M/SURVEY ×1 ═══════════════════════ the map
                       │
    ┌──────────── per slice, N times ──────────────────┐
    │  M/PLAN ×1 ─► L teaches ─► GATE ─► slice BUILT   │
    │                 └─ M/SUBHOLE ×0-2                │
    └──────────────────────────────────────────────────┘
                       │ last gate passes
                       ▼  SOLO — the codebase is his
```

**Re-survey only when the territory changes** — the target is refactored, or the spine
proves wrong. Note the second case is normally a *spine repair*, not a fresh survey:
hitting the subhole cap means M mis-sized, and the fix is inserting a smaller slice
(F4, G2 rule 6), not re-walking the whole codebase.

M/SURVEY is the cheapest turn in the system and the one whose errors cost the most —
a bad spine misroutes every slice after it. That is why it is built LAST (build order
step 7): only a working loop can prove a spine good or bad.

---

## Part B — The DB, cut from 20 tables to 7

The 20-table schema was scaffolding for the old 6-phase pointer machinery. Most
collapses because the **trajectory now lives in the library**, not in tables. But the
two things that make this "build the REAL codebase" and not "drills" — the **slice
decomposition** and the **gate** (the blank-page wall) — must survive. Proposed:

| Keep | Why it survives the pedagogy |
|---|---|
| `target` | the codebase he's building (path only). The spine itself lives ONLY in `slices` — storing an ordered plan here too was redundancy, and it was removed. |
| `slices` | each real function/file he must write, its spec, its state (LOCKED/READY/BUILT), its concept-prereqs. **This is the unit of progress.** |
| `concepts` | the bank = DAG nodes + mastery overlay (OWNED/READY/LOCKED). Prereqs that slices require. |
| `gates` | the blank-page wall. While open: he can't read the spec, and the agent can't write his target file. **The mechanism by which real code gets built.** |
| `probes` | the evidence M reads. One row per judged answer. Absorbs attempts/stalls/reviews as `kind`. |
| `mappings` | **NEW.** Trigger + solution + why. The intuition unit. Had no table before (H3). |
| `vocab` | the door — every term shown. A question may not use an unshown term. |

(`learner` identity folds into a single row of `target` or a tiny `meta` kv — not counted.)

| Cut / collapse | Where it goes instead |
|---|---|
| floors, stack_frames | the descent now lives in the library (M's per-slice map files) |
| asks, utterances | ephemeral clock/audit — not needed for the loop |
| attempts, stalls, reviews | become `probes` rows with `kind = build/stall/review` |
| misconceptions, +hits | become `mappings` with `polarity = negative` (a false trigger) |
| assumptions, lookups | M's research tool logs to the library, not a table |
| ladder_log, discovery_chains | the library's git history IS the log |
| capstones | a `slice` with `kind = capstone` (design forks, no single right answer) |
| sessions, meta | keep a tiny `meta` kv if needed |

Net: **~7 tables.** There is **no global `phase` row** (see Part E).

### One fact, one place (the anti-redundancy pass, DECIDED — enforced in code)

Every fact in the system has exactly one home; everything else is a render, a seed,
or a refusal:

1. **`gates` stores no paths.** The wall JOINs to `slices` for `target_file`/
   `spec_path` — it can never enforce a stale copy.
2. **The spine lives only in `slices`** (`ordinal` order). `target` holds the
   codebase path, nothing more; `decompose_target` became `set_target`.
3. **OWNED is earned, never set.** `set_concept_state` refuses `OWNED`; only
   `close_gap` (which requires a positive mapping) grants it. No side doors (H1).
4. **READY and BUILT are computed.** `set_slice_state` may only re-LOCK (spine
   repair); READY comes from owned prereqs, BUILT from `pass_gate` alone.
5. **`target.md` is generated** from the DB (`library.render_target_md`), never
   hand-written.
6. **The vocab table is the only door.** The frontier's vocab lists are seed input
   (`library.seed_vocab` plants them at slice start); the door and the router read
   the table exclusively, so a mid-slice promotion is never shadowed.
7. **`spec_path` non-NULL ⇒ the spec exists**, because the only turn that sets the
   path is the one that writes the file (lazy specs), and `open_gate` refuses NULL.

---

## Part C — The library layout (the PLAN as files)

```
library/
  target.md              ← the spine, GENERATED from the DB by code after any spine
                           write (library.render_target_md). A render, never a source
                           — M writes it zero times, so it cannot drift.
  frontier.md            ← the ONE active slice + the concept gap being taught right now.
  concepts/
    enumerate-index.md    ← per-concept map: trigger, solution, why, road, provenance
  slices/
    pinned-qa-group.md    ← the real spec for the real function he writes
```

`frontier.md` is the whole handoff. Its structure is designed around one question:
*what does L need on paper to make this learner measurably stronger this slice?* The
control keys (road, done-when, vocab) steer L; the **teaching-support keys** — taken
straight from the intuition model — are what make the teaching good: the opening
question, the simplification ladder, the predicted wrong turns, the justify
obligation, and the connections to mappings he already owns ("what has worked before,
will it work here" only fires if L surfaces the *before*).

```md
# ── SLICE (the objective; never edited mid-slice) ──────────────
slice: pinned-qa-group
target-file: soufiane_prompts/prompts/run_prompts.py
spec: write _pinned_qa_group(questions) — pinned questions lead each group,
      original order preserved within a group. (full: slices/pinned-qa-group.md)
why-this-slice: run-loop needs it; earliest READY slice on the spine
concept-prereqs: [enumerate-index (NOT owned), dict-group-by (owned), list-stable-sort (owned)]

# ── GAP (one per unowned prereq; the teaching contract) ────────
concept: enumerate-index
road: intuition-train            # guess → check → justify
zpd-note: 1 new piece on owned ground (loops OWNED); expect 1-2 pushes, cap 4

## how L opens (guess-first — never lecture-first)
opening-question: "you'll walk the questions needing each one's position as you go —
  write the loop that gives you each question AND its position, no lookups"
connect-to: [list-iteration (owned): 'this is that loop, plus one more thing per step']

## when he's stuck (descend, don't tell)
simplify-ladder:
  1. "forget questions — loop over ['a','b','c'] and print position + letter"
  2. "keep a counter by hand first; now, what's ugly about that?"

## predicted wrong turns (each one is information, not failure)
worth-failing-at:
  - range(len) + re-index      → reveals: no pairing primitive mapped yet
  - off-by-one on the counter  → reveals: index vs count confusion
just-tell: the WORD "enumerate" once he builds the behavior; names are lane-6

## closing the gap (nothing closes without these)
justify: he must say WHY it beats range(len) in his own words — the proof step
  that checks the intuition; a working line without the why is not done
done-when: pairs item+index unaided on a FRESH sequence + justify holds
mapping-seed: trigger≈"looping and also need the position"; L authors the final
  mapping from what HE actually did, including his wrong turn (provenance)
vocab-ok: index, loop, pair, question, group
vocab-hold: enumerate

# ── GATE (opens when all gaps close) ───────────────────────────
gate-when: enumerate-index reaches OWNED
gate: he writes _pinned_qa_group into run_prompts.py, unaided, spec hidden

# ── SUBHOLE (empty keys; filled only via the F4 handoff) ───────
subhole-concept:
subhole-evidence:
subhole-plan:
```

Why each teaching-support key exists (the intuition model, made operational):
- **opening-question / guess-first** — intuition trains by guessing the high-level
  idea then checking, never by hearing the answer first.
- **connect-to** — a new mapping sticks by association to owned ones; L must surface
  the old mapping the new one extends.
- **simplify-ladder** — the pre-authored descent for "too hard right now": shrink the
  problem, don't reveal the answer. This is how ZPD is held mid-turn.
- **worth-failing-at → reveals** — each predicted wrong turn is labeled with what it
  *diagnoses*, so L's probe row says something M can plan on.
- **justify** — the proof step is the separate channel that checks intuition; skipping
  it produces semi-blind guessers. A gap cannot close on working code alone.
- **mapping-seed** — M seeds the trigger; L authors the final mapping from what the
  learner ACTUALLY did, wrong turn included — self-found solutions burn in deepest,
  and the provenance line is what makes the mapping his, not ours.

### The frontier lifecycle (deterministic reset + archive)

When the slice's gate closes PASS, **code — not an agent — does the rollover**:

```
1. archive : frontier.md → library/history/NNN-pinned-qa-group.md, with the
             outcome appended (gate result, pushes, wrong turns hit, mapping id).
             History is append-only — traceability for humans AND agents
             (M's research can grep it; the learner can reread his own path).
2. reset   : a FRESH frontier.md is written with the KEYS ONLY, all values empty.
3. wake M  : the empty frontier is M's wakeup (the F4 cell pattern again —
             empty-required-file = a filled handoff cell). M plans the next slice
             by filling the keys; the schema tool rejects a partial fill.
```

So M never edits a stale file (no leftover values leaking into the next slice), the
template IS the schema (M literally cannot forget a teaching-support key — the empty
key stares at it), and every completed slice leaves one immutable history file: what
was planned, what actually happened. When M re-plans mid-slice (subholes), it edits
values under the fixed keys; the SLICE block and the key set never change mid-slice.

---

## Part D — THE SIMULATION

Learner: Bilal. Target: `run_prompts.py`, a prompt-runner he's rebuilding by hand.
M has decomposed it into slices; the next buildable one is `pinned-qa-group`. That slice
needs `enumerate-index`, which isn't OWNED — so it gets taught first, **then he writes
the real function.** Three columns per turn:
**[LEARNER sees/types] · [L's ACTUAL context this turn] · [what gets WRITTEN, where]**

---

### Turn 0 — M's planning turn (silent; picks the real SLICE, not a concept)

**M's ACTUAL context (rows + library, no transcripts):**
```
target.md decomposition: [load-prompts BUILT, pinned-qa-group READY, run-loop LOCKED, ...]
slices overlay: pinned-qa-group's prereqs = enumerate-index(CANT), dict-group-by(OWNED), list-stable-sort(OWNED)
concepts overlay: enumerate-index NOT owned
```
**M's judgment:**
- Next buildable slice = `pinned-qa-group` (it's the earliest READY slice on the spine).
- It has ONE missing prereq: `enumerate-index`. Teach that, then gate the slice.
- Road for the gap: `enumerate` has a genuine "guess the shape" moment → intuition-train.

**WRITTEN — M writes `frontier.md`** (the Part C block above). No chat with learner.

---

### Turn 1 — L opens the concept gap, framed BY the real slice

**L's ACTUAL context (filtered — NOT the whole DB):**
```
learner.rules   : never answer first; his code is evidence; no praise
frontier.md     : active slice = pinned-qa-group, active gap = enumerate-index, road=intuition-train
vocab-ok        : index, loop, pair, question, group
vocab-hold      : enumerate
(no gate wall yet — gate opens only after the gap closes. no other slice, no other concept.)
```

**LEARNER sees:**
> To build `_pinned_qa_group` you'll walk the questions and you'll need each one's
> position as you go — to keep original order stable within a group. Start there: write
> the loop that gives you each question *and* its position. Don't reach for anything
> you'd have to look up.

> Note: the concept is introduced **as a step inside building the real function**, not
> as a drill. He knows what he's building.

**LEARNER types:**
```python
for i in range(len(questions)):
    q = questions[i]
```

**WRITTEN:** nothing — L hasn't judged.

---

### Turn 2 — L judges, lets the mistake stand (intuition road)

**L's context:** same frontier block + the learner's code from Turn 1.

`range(len())` is the "worth-failing-at." Road is intuition-train → L does not fix it,
it probes the edge.

**LEARNER sees:**
> That works. But you indexed back in with `questions[i]` to get the item. Is there a way
> to get the item *and* its position in one step, without indexing back? Guess first.

**LEARNER types:**
> maybe a pairing function? i don't remember the name

**WRITTEN — one `probes` row:**
```
concept=enumerate-index  kind=predict  result=PARTIAL  error_class=gap
note="reached for range(len); sensed a pairing primitive but no name"  terms=index,loop  pushes=0
```
> This row is ALL M will see of this turn. Not the transcript.

---

### Turn 3 — he self-corrects with one nudge; L names the word; mapping deposited; concept → OWNED

**LEARNER types** (after L's one nudge "you had it — Python pairs position+item for you"):
```python
for i, q in enumerate(questions):
    # i is the position, q is the question
```

L judges: built the behavior unaided after one push. The gap's `done-when` is met. The
word was on `vocab-hold`; correct use promotes it.

**LEARNER sees:**
> That's it — `enumerate` hands you `(position, item)` so you never index back in.

**WRITTEN — three writes:**
```
probes  : concept=enumerate-index kind=produce result=HIT pushes=1 self_corrected=1
vocab   : term=enumerate  status=proved
mappings: concept=enumerate-index polarity=positive
          trigger  = "looping and I also need the position / a counter"
          solution = "enumerate(seq) → (index, item); +1 only if a human reads it"
          why      = "avoids range(len)+re-index; pairs count with item in one step"
          provenance= "reached for range(len) first, self-corrected on 1 nudge"
```
> concepts.enumerate-index → OWNED. `pinned-qa-group` now has ALL prereqs owned → the
> slice is READY to gate.

---

### Turn 4 — THE GATE opens: he writes the REAL function, unaided

Because `enumerate-index` reached OWNED, `frontier.md`'s `gate-when` fires. L opens a
`gates` row. **Now the hooks enforce the wall:** he cannot read the full spec, and the
agent cannot write `run_prompts.py`. He produces, or it did not happen.

**L's ACTUAL context this turn:**
```
learner.rules
frontier.md: gate is OPEN for slice pinned-qa-group
gates row  : target=run_prompts.py  spec_path=slices/pinned-qa-group.md (BLOCKED to him)
(the concept teaching blocks are GONE — that gap is closed. only the gate is live.)
```

**LEARNER sees:**
> Gate open. Write `_pinned_qa_group(questions)` in `run_prompts.py`: pinned questions
> lead each group, original order preserved within a group. No peeking at the spec, no
> AI writing it. When it's in the file, tell me.

**LEARNER types** (into the real file, over a few minutes — one real attempt):
```python
def _pinned_qa_group(questions):
    groups = {}
    for i, q in enumerate(questions):
        groups.setdefault(q.group, []).append((i, q))
    out = []
    for g in groups.values():
        pinned = [q for _, q in g if q.pinned]
        rest   = [q for _, q in g if not q.pinned]
        out.extend(pinned + rest)
    return out
```

**WRITTEN — the gate closes:**
```
gates  : result=PASS  closed_at=now   (spec-read + target-write walls lifted)
probes : concept=pinned-qa-group kind=build result=HIT  note="stable within group; enumerate used correctly"
slices : pinned-qa-group state=BUILT
mappings: concept=pinned-qa-group polarity=positive
          trigger="group items but some must lead their group, order stable"
          solution="setdefault to bucket by key; within bucket, pinned + rest; enumerate keeps order"
          why="dict groups; stable partition preserves input order without a sort key"
```
> A real slice of the real codebase now exists, written by his hand. That is the actual
> product — not the drill in Turns 1-3.

---

### Turn 5 — M's next planning turn: pick the next SLICE

**M's ACTUAL context (rows, not prose):**
```
new probes: enumerate-index HIT (1 push); pinned-qa-group BUILD HIT (gate PASS)
slices overlay: pinned-qa-group BUILT → run-loop now READY (its prereq slice is done)
ZPD meter: 1 push, self-corrected on the concept; gate passed first try → PERFECT ZPD, don't shrink
```
**M's judgment:** next buildable slice = `run-loop`. Its concept-prereqs = `file-iteration`
(owned), `dict-get-default` (NOT owned). Teach that gap, then gate `run-loop`. `dict-get`
has one right answer → road = **fast-map**, not intuition-train.

**WRITTEN — M rewrites `frontier.md`:** new slice `run-loop`, new gap `dict-get-default`,
road fast-map, new gate targeting the next real function.

> Turn 6 (L's next turn) would therefore read a **structurally different message** —
> show-then-apply (fast-map) instead of withhold-and-probe (intuition) — with zero
> special-casing. The FILE changed; L didn't. And it's still driving toward the real
> codebase: one more slice built, then the next, until the last gate passes = SOLO.

---

## Part E — The routing rule (no global phase; the SLICE + road drive the turn)

**Old model:** one global `meta.phase` → the hook loads that whole phase file + 20
tables every turn. Send-everything.

**New model:** no global phase. The active instruction is `frontier.md` — the current
**slice** plus the current **concept gap's road**, rewritten by M per slice. L loads:

```
ALWAYS (tiny, constant):    learner.rules + frontier.md + its vocab lists
CONDITIONAL (only if true): the gate wall block  (only while a gates row is OPEN)
                            the concept-teaching block (only while a gap is unclosed)
NEVER as a block:           other slices, other concepts, the full bank, table dumps
```

The rule that makes it a router, not a dump:

> **Every block is a pure function of state → text-or-nothing. Empty ⇒ omitted.**
> The agent never sees "0 gates open" or "here are all 6 phase docs." It sees the one
> active slice, the one concept gap (if any), and the gate (if open).

And the key reduction: the "how to behave this turn" that the old **phase files** carried
is now split into two smaller, live things — the **slice** (what real code he's building)
and the **road** (intuition-train / fast-map / slow-solve for the concept gap). Both are
chosen by M from evidence and swapped by rewriting one small file.

**6 phase docs + 20 tables + a global pointer → target-decomposed-into-slices +
7 tables + per-slice roads + the gate.** Progress = slices going BUILT. Done = last gate
passes = the whole codebase is his.

---

## Part F — Context lifecycle (fresh starts, turn deltas, reactive injection)

The stores (library + DB) are the ONLY memory. Conversation history is disposable
scaffolding. Three rules:

### F1 — Fresh context per unit of progress (the wipe rule)

```
slice goes BUILT   → L's conversation history is DELETED.
                     Next L turn starts COLD: rebuilt from learner.rules +
                     the NEW frontier.md + current DB state. Nothing else.

frontier ADVANCES  → M's context is DELETED (a new slice was planned).
                     Next M planning turn starts COLD: rows + library only.
                     (Same-slice frontier edits — subhole rewrites, F4 — do NOT
                     wipe M; it keeps context for mid-slice course corrections.)
```

Why this is safe: everything that mattered from the dead history was already
**deposited as it happened** — probes rows, the mapping, vocab promotions, the gate
result, the rewritten frontier.md. If losing the history would lose information,
that information was in the wrong place. The wipe is also the *test* of the design:
a system that survives its own amnesia has its state where it belongs.

Why it's necessary, not just cheap: after a slice, the history is **toxic** —
old drill transcripts, an abandoned wrong guess, a road (intuition-train) that no
longer applies. Carrying it into a fast-map slice makes L half-behave like the old
road. Cold start = the new frontier.md is the *only* voice.

**Mid-slice, history persists.** The wipe boundary is the slice (for L) and the
planning turn (for M) — never mid-gap, never mid-gate.

### F2 — First-turn vs continue-turn instruction sets (turn deltas)

The instruction block is a function of `(position-in-slice, DB state)` — deterministic:

```
L turn 1 of a slice   → OPENING set: full frontier.md + "frame the slice, open the
                        gap per its road" + full vocab lists + learner.rules
L turn N (gap open)   → CONTINUE set: the gap's done-when + road reminder + the delta
                        since last turn (new probes rows only). NOT the full opening.
L turn N (gate open)  → GATE set: the wall text + what he may/may not see. The
                        teaching blocks are GONE (Part D Turn 4 already shows this).
M turn 1 (new target) → SURVEY set: full target, write target.md + slices.
M turn N (steady)     → PLAN set: new evidence rows since last plan + overlays. Not
                        the decomposition instructions — that job is done.
```

Same agent, different injected set, zero special-case code: the router picks the set
from state, exactly like Part E picks blocks.

### F3 — Reactive injection (DB deltas and known keywords)

Beyond the per-turn set, two triggers inject a block **for that turn only**:

- **DB delta**: a watched row changed since the agent's last turn → inject the
  matching micro-block. Examples: a gate flipped OPEN → inject the wall rules; a
  vocab term hit `proved` → inject "you may now use the word X"; a probes row landed
  with `pushes=4` → inject "cap hit: shrink the step, do not carry him."
- **Known keyword**: the learner's message contains a term we track → inject its
  status. He types "enumerate" while it's on `vocab-hold` → inject "term is HELD:
  he used the word — probe whether he owns the behavior before promoting." He names
  a concept marked as a negative mapping → inject that misconception's trigger.

Both are pure lookups (state → block-or-nothing). No LLM decides what to inject.

### F4 — Subholes: a DB-cell handoff between L and M (a filled cell is a wakeup)

Mid-slice, a prereq can turn out shaky (a "subhole"). L does NOT improvise a fix —
it hands the case to M through the DB, and the whole exchange is deterministic:

```
detect  : probes evidence shows a supposedly-OWNED concept failing inside this slice
hand off: L writes the HANDOFF CELL — slices.subhole = {concept, evidence} — via the
          tool, and DOES NOT ANSWER the learner yet. The F5 return says exactly that:
          "recorded. Hold. M is re-planning."
wake M  : code watches the cell. Cell filled → M wakes with the SUBHOLE instruction
          set injected (the F2/F3 pattern: a wakeup-specific set we author once).
          M keeps its history — NO wipe: same slice, this is a course correction,
          not a new planning cycle. M researches (online + offline), re-checks the
          DAG edge, picks the subhole's road.
update  : M rewrites frontier.md — the `slice:` line UNTOUCHED, a sub-gap inserted
          with parent: <slice> — then clears the cell (the ack).
wake L  : the cleared cell is L's wakeup: next turn gets the "trajectory updated,
          continue" injection, L reads the new frontier.md, teaches the sub-gap
          like any gap (road, done-when, mapping), and the slice's flow resumes.
```

The agent never drifts from the objective because the objective is **frontier.md's
`slice:` line**, which the handoff never touches. Depth capped at 2 sub-gaps;
deeper means M mis-sized the slice → insert a smaller slice instead.

This sharpens F1's wipe boundary for M: **M wipes on frontier-ADVANCE (a new slice
planned), not on every frontier-write.** Subhole rewrites are same-slice edits — M
keeps its context for them.

**Capability split:** M has the research tools, online + offline, and the freedom to
think and plan long. L has offline search over the target codebase only — enough to
ground its questions in the real code, never enough to wander.

### F5 — Post-tool injection (every tool return is state-change + steering)

A tool call is a deterministic interception point. When an agent calls a tool, code
inspects **the type of update** and appends the matching steering text to the tool's
return value — the agent reads it as part of the result, same turn, no extra round-trip:

```
record_probe(result=MISS, pushes=4)  → "OK. Cap hit: record and stop. Do not carry him."
promote_vocab(term=enumerate)        → "OK. 'enumerate' is now speakable."
close_gap(concept=enumerate-index)   → "OK. All prereqs owned → gate-when fires. Open the gate."
open_gate(slice=pinned-qa-group)     → "OK. Wall active: spec hidden from him, you may not
                                        write run_prompts.py."
write_frontier(...)                  → "OK. Frontier replaced. Your planning turn is done — stop."
```

Generalization: **every mutating tool returns `ack + consequence`** — what just became
true and what behavior that now requires. The agent never has to *remember* the
consequence of its own action; the tool hands it back. (This is F3's reactive
injection moved to its sharpest trigger point: the mutation itself.)

### F6 — Menu disclosure for DB tools (don't carry the toolbox, carry the doorbell)

Neither L nor M carries the full DB tool surface in its schema — 15 tool descriptions
every turn is exactly the send-everything disease, relocated. Instead:

EVERY operation goes through this gateway — including hot-path ones like record_probe
(decided: no first-class tools, one pattern, zero exceptions; the tool list stays tiny
and constant, and F7 makes the menu round-trip nearly free by collapsing it to a receipt).

```
constant schema : ONE gateway tool, `db(request?)`, with a one-line description:
                  "interact with tutor state. Call with no args to see what you can do."
step 1 (need)   : the core instructions (G1/G2) create the need — "every judged answer
                  becomes a probes row." The agent detects it must act.
step 2 (menu)   : it calls db() → gets the menu: operation names + one-liners,
                  FILTERED by state (no `open_gate` while a gate is already open;
                  no learner-facing ops in M's menu).
step 3 (pick)   : it calls db(request="record_probe") → gets that ONE operation's
                  full description + parameter schema.
step 4 (do)     : it calls with real args → validated, refused-or-committed, and the
                  return carries the F5 steering line.
```

Cost: full tool documentation is ~zero tokens until the moment of use, and the menu
itself is state-filtered (Part E's rule again: pure function of state → text).

### F7 — Tool-interaction compaction (surgical, not the slice wipe)

F6 leaves debris in history: the menu turn, the description turn, the execute turn.
Once the procedure completes, the NEXT turn's context rebuild deletes **only those
tool exchanges** — not the teaching conversation — and replaces the whole procedure
with one line:

```
before (3 exchanges, ~600 tokens):
  → db()                      ← [menu: record_probe, close_gap, ...]
  → db("record_probe")        ← [full description + schema]
  → db(record_probe {...})    ← "OK. Recorded. 1 push, self-corrected."
after (1 line, next turn):
  ✓ recorded probe: enumerate-index HIT, pushes=1
```

Two compaction layers, different knives: **F7 trims tool debris every turn** (the
learner conversation stays intact mid-slice); **F1 wipes everything at the slice
boundary**. Rule of thumb: descriptions and menus are *rented* context — returned
as soon as the act is done; only the act's one-line receipt persists.

**How F7 is built (decided):** the SDK has no mid-session transcript editing, so we
do NOT delegate conversation memory to it. Our orchestrator owns the message list
through a custom `ContextManager` (see `tutor-sdk-mapping.md` §3): every op returns a
one-line receipt, and before each turn `.collapse()` swaps a completed menu→describe→
execute run for its receipt, then `.render()` produces the exact next prompt for a
stateless model call. F1 (drop the list), F2 (opening-vs-continue framing), and F7
(debris trim) become one mechanism — we decide every turn exactly what is in context.

**Compatibility requirement (why this shapes everything else):** F5-F7 only work if
every mutation goes through the gateway (no side doors — H1), every operation is
individually nameable (menu-able) and self-describing, and every operation can state
its consequence in one line (F5) and its receipt in one line (F7). That is now a
design constraint on the DB and the tool surface, not an optimization done later.

---

## Part G — The agent instructions (first draft, to mark up)

What each agent is actually told. `[...]` marks router-injected blocks (Parts E/F);
everything else is the constant core, kept deliberately short because the router
carries the situation.

### G1 — Agent L, constant core (every turn, ~20 lines)

```
You are the tutor. You are the only agent the learner sees.

1. Never answer before he attempts. His code is evidence; his self-report is a hint.
2. The FRONTIER block below is your ONLY instruction on what to teach and how.
   Do not teach anything else. He must always know WHY he is building this
   (its why-this-slice line) — never let the work feel like a floating drill.
3. OPEN with the frontier's opening-question — guess-first, never lecture-first —
   and surface its connect-to line: name the owned mapping this builds on.
4. Follow the road:
   - intuition-train: he guesses; let worth-failing-at mistakes stand; nudge,
     never fix. Cap: 4 pushes, then record and stop.
   - fast-map: show the solution cleanly, then he applies it once, fresh.
   - slow-solve: he proves it fully; you only verify the proof.
5. When he is stuck: descend the simplify-ladder ONE step. Shrink the problem;
   never reveal the answer. Off-ladder improvisation only if the ladder is spent.
6. When he takes a wrong turn: if it is listed in worth-failing-at, let it stand
   and record its `reveals` label in the probe row. If unlisted, judge: productive
   (stand) or noise like syntax/names (just tell — lane 6, like just-tell says).
7. A gap does NOT close on working code. Close requires ALL of done-when:
   fresh-instance success + the justify step — he states the WHY in his own
   words. No why, no close.
8. Vocabulary door: never use a vocab-hold term. If HE uses one, probe the
   behavior before promoting the word.
9. Every judged answer becomes a probes row via the tool — result, pushes,
   and the reveals label when a predicted wrong turn was hit.
10. Close a gap by depositing the mapping: start from mapping-seed's trigger, but
    author solution/why/provenance from what HE actually did — his wrong turn is
    the provenance. The tool rejects a mapping without trigger+solution+why.
11. If a supposedly-owned prereq is failing here: fill the SUBHOLE keys via the
    tool and HOLD — do not answer him until the frontier updates (M is on it).
12. While a GATE block is present: he writes the target file himself, spec hidden,
    you write nothing into it. He produces, or it did not happen.
13. No praise without evidence. Short, direct. Name gaps he cannot see.

[FRONTIER]     ← always: SLICE + GAP (all keys) + GATE-when + vocab lists
[GATE]         ← only while a gate is OPEN
[DELTA]        ← only when triggered: DB changes, keyword hits, push-cap warnings
[FIRST-TURN]   ← only on turn 1 of a slice: "frame the slice, open the gap"
```

### G2 — Agent M, constant core (every planning turn, ~12 lines)

```
You are the planner. You never talk to the learner; you never see transcripts.
Your inputs are probes rows and the overlays. Your output is the library.
You wake to an EMPTY frontier.md (keys, no values). Your job is to fill every key.

1. Unit of progress = the SLICE. Pick the earliest READY slice on the spine;
   state why in why-this-slice — the learner will read it.
2. For each unowned concept-prereq, write one GAP block. Choose its road:
   - one right answer / a name / a convention  → fast-map (just tell)
   - a genuine guessable shape                 → intuition-train
   - needs proof to stick                      → slow-solve
   Balance: not the same road 3x in a row.
3. Fill the teaching-support keys — this is where the teaching quality lives:
   - opening-question: the question whose answer IS the first step, guess-first
   - connect-to: the owned mapping(s) this one extends — check history/ and the
     mappings table; a gap with no connect-to means the DAG edge is wrong, fix it
   - simplify-ladder: 2-3 pre-authored shrink steps, smallest last
   - worth-failing-at: each predicted wrong turn WITH its reveals label —
     what hitting it diagnoses. Manufactured fumbles are noise; leave them out
   - just-tell: names/conventions L should simply give (lane 6)
   - justify + done-when: the why he must state + fresh-instance proof of doing
   - mapping-seed: the trigger phrase only — L authors the rest from what he did
   - vocab-ok / vocab-hold: every term the opening-question needs, sorted
4. Size by the ZPD meter, write it into zpd-note: 0 pushes = raise, 1-2
   self-corrected = hold, 4 = shrink (insert a smaller slice; don't soften roads).
5. If evidence contradicts a prerequisite edge, research it (online + offline),
   fix the DAG, note it in the concept's map file.
6. On a SUBHOLE wakeup: keep the SLICE block untouched. Research the shaky
   concept, write its GAP block under the existing keys, fill subhole-plan,
   clear the cell. Max 2 sub-gaps — a third means you mis-sized: insert a
   smaller slice instead.
7. Set gate-when. The schema tool rejects a frontier with any empty key.
   Then stop — one step, then observe. Never plan past the next slice.

[EVIDENCE]     ← probes rows since your last turn (rows, never prose)
[OVERLAYS]     ← slice states + concept states + ZPD meter
[HISTORY]      ← on request: past history/NNN-*.md files (what was planned vs
                 what happened — your calibration record)
[SUBHOLE]      ← only on a subhole wakeup: the filled cell + its instructions
[SURVEY]       ← only on a brand-new target (M/SURVEY): write target.md + slices first
```

### G2a — The `[SURVEY]` block (M/SURVEY, injected once per target)

```
[SURVEY] — you are looking at this codebase for the first and only time.

You are not teaching. You are drawing the map every later turn navigates by.
Output = the spine in the DB. You write NO frontier; that is your next turn's job.

1. READ THE REAL CODE FIRST. Grep the entry points, then Read the files they
   reach. You may not invent a slice for code you have not read.
2. Cut the codebase into SLICES. A slice is ONE function or file the learner
   can write in one sitting, from a spec, behind a closed gate.
   Sizing test — a slice is correctly sized when:
     - it has a name he could say out loud ("group the pinned questions")
     - it has <= 2 concept-prereqs he does not already own
     - it can be judged: run it, or read it, and know PASS or FAIL
   Too big => cut it. Too small => it is not a slice, it is a line.
3. ORDER them into a spine: dependency order, not file order. Slice N may only
   need concepts and slices from before it. The FIRST slice must need the
   fewest unowned concepts — it is where he starts cold.
4. For each slice name its concept-prereqs. A concept is a thing that can be
   OWNED or not (`enumerate-index`), never a task (`write the loop`).
5. Build the concept DAG: every prereq becomes a concepts row with its edges.
   All start CANT — you have no evidence yet. Assume nothing about him.
6. RESEARCH (WebSearch/WebFetch) only for two questions: is this the standard
   NAME for this concept, and is edge X->Y a real prerequisite? Never to fetch
   tutorials or teaching material — that is not your job on this turn.
7. Write slice ROWS only — leave `spec_path` NULL. You author no spec files and
   no paths-to-nothing: M/PLAN writes each spec lazily AND sets `spec_path` in
   the same act, so a non-NULL path always means the file exists. `open_gate`
   refuses a NULL spec_path; the column is the fact.
8. Write it all through db(). Then STOP. One survey, then observe.
   You do not plan the first slice on this turn.
```

**Why specs are lazy (DECIDED).** M/SURVEY leaves `slices.spec_path` NULL and writes no
`library/slices/*.md`. M/PLAN authors that one spec when it plans that slice. Three
reasons: a spec written N slices early is written blind to the evidence the learner
will have produced by then; survey stays cheap (it is the turn with the least
information and the most leverage, so it should commit the least); and a spine repair
that drops or splits a slice throws away no written spec. **Invariant:** the spec file
must exist before its gate opens — M/PLAN writes it in the same turn it fills the gate
keys, and `open_gate` refuses a slice whose `spec_path` is missing.

### The wakeups — what makes M run again (all deterministic, no agent decides)

```
gate PASS ─► code archives frontier.md -> history/NNN-<slice>.md
            code writes a FRESH frontier.md: KEYS ONLY, all values empty
            code drops M's ContextManager        (F1: new slice = cold M)
                     │
                     ▼  the EMPTY frontier IS the wakeup
            M/PLAN wakes cold: [EVIDENCE] (probes since last turn) + [OVERLAYS]
            picks the earliest READY slice, writes its spec file, fills every key
                     │
                     ▼
            L's next turn reads the new frontier — L never knew M ran.
```

Same cell pattern, three triggers, one rule — **a filled/emptied cell is a wakeup**:

| wakeup signal | who wakes | keeps context? |
|---|---|---|
| empty `frontier.md` | M/PLAN | no — cold (new slice) |
| filled `slices.subhole_*` cell | M/SUBHOLE | **yes** — same slice, course correction |
| cleared subhole cell | L | mid-slice history persists |
| no `target` row at all | M/SURVEY | n/a — first turn of the project |

### How M discovers its tools (identical to L — one gateway, one menu)

M does **not** get a different tool mechanism. `db()` is role-filtered inside
`gateway.dispatch(db, role, ...)`: calling it with no args returns the menu for THAT
role in THAT state. M sees `upsert_slice`, `set_target`, `clear_subhole`; it
never sees `record_probe` or `open_gate` — those are L's. No order is prescribed and
none needs to be: the menu is a pure function of state, so an op that is not legal yet
is simply not listed.

**Tool-use discipline is rented context, never core prose (the G3/H1 lesson).** The
efficient-use rules for `Grep`/`Read`/`Web` do not live in G2 — they are one block
injected only on turns where those tools are live, exactly like the `db()` menu:

```
[TOOL DISCIPLINE]  ← injected on SURVEY turns (and M/SUBHOLE research turns)
 Grep  first, always. Pattern + path filter; never a bare pattern over the repo.
       You are locating, not reading. Cheap and wide.
 Read  only files Grep proved matter, and only the ranges it pointed at.
       A whole-file Read of something you have not located is a bug, not thoroughness.
 Web   two questions only: the standard NAME of a concept, and whether a
       prerequisite edge is real. Two calls is a lot; five means you are drifting.
 db()  last. It is the only write. menu -> describe -> commit.
```

### G3 — What is deliberately NOT in the instructions

- No phase names, no mode names — the road in frontier.md is the behavior.
- No table documentation — tools validate; agents don't need schema knowledge.
- No history-management prose — the wipe (F1) is the harness's job, not the agent's.
- No "remember to…" — anything an agent must remember every turn is a router block
  or a tool constraint, never a sentence in the prompt (the H1 lesson).

---

## What I need from you

Mark, line by line:
1. **DB cut (Part B)** — is 7 tables right? Is `slices` as a separate table from `concepts` correct, or should slices live only in `target.md`?
2. **Two layers (Part C/D)** — slice drives, concept is subordinate and taught only when a slice needs it. Right?
3. **The gate (Turn 4)** — is "teach the gap → open gate → he writes the real file unaided" the right rhythm, or should some slices skip the gap and go straight to gate?
4. **Routing (Part E)** — no global phase, slice + road drive the turn. Agreed, or do you still want an outer phase frame?
5. **Context lifecycle (Part F)** — wipe at slice-BUILT for L / at frontier-write for M; mid-slice history persists; subhole frames capped at 2. Right boundaries?
6. **Instructions (Part G)** — is the constant core small enough, and is anything missing that can't be carried by a router block instead?
7. **Frontier structure + lifecycle (Part C)** — the teaching-support keys (opening-question, connect-to, simplify-ladder, reveals-labels, justify, mapping-seed), the empty-keys reset at gate PASS, and append-only `library/history/`. Right keys? Anything the teacher needs that's still missing?
8. **Tool patterns (F5–F7)** — one gateway `db()` tool with menu disclosure, `ack + consequence` returns, per-turn compaction to one-line receipts. DECIDED: every op (incl. `record_probe`) goes through the menu — no first-class tools; and F7 is our own `ContextManager` (orchestrator-owned history), not SDK sessions.
