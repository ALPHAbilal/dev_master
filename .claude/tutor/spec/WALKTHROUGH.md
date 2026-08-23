# TUTOR — ONE COMPLETE WORKED EXAMPLE

Status: LIVE — the grounding doc. Every other doc is abstract. This one takes ONE
real unit and walks it end-to-end, showing the ACTUAL value of every variable at
every moment, and defining each term the first time it appears. If a term in
DATA.md / CATALOGS.md confuses you, find it here with a real value next to it.

---

## THE CAST (the concrete example we'll use the whole way)

The learner: **bilal**.
The codebase (the objective): **run_prompts.py**.
The one unit we'll teach fully below — real code:

```python
# run_prompts.py   lines 120–131
def _pinned_qa_group(questions):
    groups = {}
    for q in questions:
        groups.setdefault(q.pin_id, []).append(q)
    return groups
```

Everything below is this unit going from "never seen" to "owned."

---

## PART 1 — EVERY VARIABLE, WITH A REAL VALUE

Instead of abstract names, here is each variable with (a) one plain sentence and
(b) the actual value it holds for THIS unit at the moment shown.

### The unit's own facts  (DB table `units`)
```
 slug        the unit's short name              → "pinned_qa_group"
 file        which file it lives in             → "run_prompts.py"
 lo, hi      its line range                     → 120, 131
 kind        do we OWN it or just pass through? → "TARGET"  (must fully own)
             TRANSIT would mean "a stepping stone, prove-lite and move on"
 depth       0 = a real chapter; >0 = a dive    → 0
 parent_id   if this was a dive, from where?    → null (it's top-level)
 state       where we are in teaching it        → changes every step (see Part 2)
```

### The report card  (DB table `axes` — one row per angle of understanding)
An "axis" = one WAY of understanding the code. This unit demands four of them.
Each starts UNGRADED and ends SOLID before the unit can be owned:
```
 axis          the question it answers                         starts   ends
 ─────────────────────────────────────────────────────────────────────────
 COMPREHEND    "what does setdefault actually do here?"        UNGRADED  SOLID
 RATIONALE     "why a dict keyed by pin_id, not a list?"       UNGRADED  SOLID
 ROBUSTNESS    "what happens if two q's share a pin_id?"       UNGRADED  SOLID
 INTEGRATION   "who consumes `groups` downstream?"             UNGRADED  SOLID

 verdict       the grade on one axis    → UNGRADED | SOLID | SHAKY | MISSING
 shaky_count   times he was half-right on this axis → 0, then 1, then =MISSING at 2
 evidence_ref  a pointer to the PROOF   → "transcript:turn-4"  (never self-report)
```

### The "where was I?" memory  (DB table `stack_frames`)
```
 resume_q    the exact question we paused if we had to dive
             → "why a dict and not a list of tuples?"
 pending     sibling gaps noticed but not opened yet
             → [{slug:"ordered_keys", why:"he assumed dict order matters"}]
 hop_budget  how many reasoning jumps a question may ask of him; shrinks when
             he's shaky so questions get smaller → starts 3, drops to 2, to 1
 is_top      only the DEEPEST frame is teachable → true
```

### The one dial  (DB table `meta` — exactly one row)
```
 current_unit  the unit we're on right now  → 12  (the id of pinned_qa_group)
 phase         the big chapter              → "LOOP"  (SCAN done, GRADUATION later)
 target        the objective codebase       → "run_prompts.py"
```

### What we know about bilal as a person  (folder `learner-model/model.json`)
This is the ONLY thing that survives forever, across every codebase:
```
 can            proven skills   → ["predict f-string output", "read pathlib.Path"]
 cant           known gaps      → ["reason about when NOT to use a structure"]
 misconceptions wrong beliefs   → [{belief:"dict order is a guarantee to rely on",
                                     disproved_by:"unit:pinned_qa_group"}]
 shown          exposed-but-unproven → ["generators"]
```

### The transient photo  (stone 0 `snapshot` — rebuilt every single turn)
```
 his_message    what he just typed this turn
 last_category  how his previous answer was labeled → "SHAKY"
 current_axis   which axis we're working now         → "RATIONALE"
 hop_budget     copied from the stack                → 2
```

---

## PART 2 — THE TIMELINE (turn by turn, real values changing)

Each turn = one engine cycle: WAKEUP (code→agent) → agent acts → RETURN
(agent→code) → ROUTE (code picks next). Watch the stores change on the right.

```
════════════════════════════════════════════════════════════════════════════
 TURN 0 — SCAN  (happens once for the whole codebase, before this unit)
════════════════════════════════════════════════════════════════════════════
 WAKEUP  wakeup.map → MAPPER reads all of run_prompts.py
 RETURN  return.map → a ladder of units. Our unit is born:
         units row {id:12, slug:"pinned_qa_group", state:"NEW", ...}
         axes rows: 4 rows, all verdict="UNGRADED"
         ladder.json written to codebase-map/
 ROUTE   phase set to LOOP, meta.current_unit = 12

────────────────────────────────────────────────────────────────────────────
 TURN 1 — POINT + PROBE  (axis = COMPREHEND)
────────────────────────────────────────────────────────────────────────────
 WAKEUP  wakeup.probe → TEACHER
         INJECTED (minimal): lines 120–131 + axis "COMPREHEND" + his level
 TEACHER says → "Read line 123. In your words, what does
                 groups.setdefault(q.pin_id, []).append(q) do to `groups`?"
 STORE   stack_frames.resume_q = "what does setdefault do here?"
         units.state: NEW → POINTED → PROBED

 bilal answers → "It looks up pin_id in groups; if it's missing it puts an
                  empty list there first, then appends q. So it buckets
                  questions by their pin_id."

────────────────────────────────────────────────────────────────────────────
 TURN 2 — GRADE + ROUTE  (that answer was strong)
────────────────────────────────────────────────────────────────────────────
 WAKEUP  wakeup.grade → JUDGE
         INJECTED: his words + axis COMPREHEND + evidence_bar
 RETURN  return.grade stamp:
         { axis:"COMPREHEND", verdict:"SOLID", category:"correct-deep",
           evidence_ref:"transcript:turn-1" }
 STORE   axes[COMPREHEND].verdict = SOLID
 ROUTE   category "correct-deep" + axes remain → advance to next axis
         current_axis → "RATIONALE"

────────────────────────────────────────────────────────────────────────────
 TURN 3 — PROBE  (axis = RATIONALE)
────────────────────────────────────────────────────────────────────────────
 WAKEUP  wakeup.probe → TEACHER
 TEACHER says → "Why a dict keyed by pin_id — why not just a list of
                 (pin_id, question) tuples?"
 STORE   resume_q = "why a dict and not a list of tuples?"

 bilal answers → "Because dicts keep the order I insert, so the groups stay
                  in order."   ← half-right reason, wrong grounds

────────────────────────────────────────────────────────────────────────────
 TURN 4 — GRADE + ROUTE  (half-right → SHAKY, first time)
────────────────────────────────────────────────────────────────────────────
 RETURN  return.grade stamp:
         { axis:"RATIONALE", verdict:"SHAKY", category:"working code,
           wrong reasoning", evidence_ref:"transcript:turn-3",
           hidden_gap:{slug:"dict-vs-list-lookup", why:"reason is about
           ORDER, real reason is O(1) grouping by key"} }
 STORE   axes[RATIONALE].verdict = SHAKY ; shaky_count = 1
         learner-model.misconceptions += {belief:"dict order is the reason"}
 ROUTE   category "wrong reasoning" → re-PROBE narrower, hop_budget 3 → 2

────────────────────────────────────────────────────────────────────────────
 TURN 5 — PROBE narrower  (still RATIONALE, smaller question)
────────────────────────────────────────────────────────────────────────────
 TEACHER says → "Forget order for a second. If you had 10,000 questions,
                 how fast is 'find the bucket for pin_id 57' with a dict
                 vs a list?"
 bilal answers → "...oh. Dict is instant, list I'd scan all 10,000. So the
                  real reason is fast lookup by key, not order."

────────────────────────────────────────────────────────────────────────────
 TURN 6 — GRADE + ROUTE  (now solid)
────────────────────────────────────────────────────────────────────────────
 RETURN  { axis:"RATIONALE", verdict:"SOLID", category:"correct-deep" }
 STORE   axes[RATIONALE].verdict = SOLID
         learner-model.can += "reason about dict vs list by access pattern"
 ROUTE   advance → current_axis = "ROBUSTNESS"

────────────────────────────────────────────────────────────────────────────
 TURN 7 — TEST  (axis = ROBUSTNESS — a challenge he can't fake)
────────────────────────────────────────────────────────────────────────────
 WAKEUP  wakeup.test → TEACHER (evidence_bar for ROBUSTNESS = "predict a break")
 TEACHER says → "Two questions both have pin_id = 5. Walk me through what
                 `groups` looks like after both. Then: what if a question
                 has pin_id = None?"
 bilal answers → "Both land in the same list under key 5 — that's fine, it's
                  grouping. None becomes a key too, so there'd be a None
                  bucket. Might be a bug if callers don't expect it."

────────────────────────────────────────────────────────────────────────────
 TURN 8 — GRADE + ROUTE
────────────────────────────────────────────────────────────────────────────
 RETURN  { axis:"ROBUSTNESS", verdict:"SOLID", category:"correct-deep" }
 STORE   axes[ROBUSTNESS].verdict = SOLID
 ROUTE   advance → current_axis = "INTEGRATION"

     ... (INTEGRATION runs the same probe→grade shape, ends SOLID) ...

────────────────────────────────────────────────────────────────────────────
 TURN 9 — ROUTE detects ALL axes SOLID → unit OWNED
────────────────────────────────────────────────────────────────────────────
 ROUTE   axes = [SOLID,SOLID,SOLID,SOLID]. Invariant check: no open child? OK.
         units.state → OWNED
 FIRE    wakeup.distill

────────────────────────────────────────────────────────────────────────────
 TURN 10 — DISTILL + RESET
────────────────────────────────────────────────────────────────────────────
 WAKEUP  wakeup.distill → DISTILLER
 RETURN  return.distill writes concept-archive/pinned_qa_group.json:
         { unit:"pinned_qa_group", final_verdict:"OWNED",
           axes_tested:[COMPREHEND,RATIONALE,ROBUSTNESS,INTEGRATION],
           tests:[...the turn-7 test...], evidence:["transcript:turns 1-8"] }
         learner-model updated ; handoff/latest.md written
 CODE    clears working memory (axes rows, stack frame)
 ROUTE   meta.current_unit → next unit in ladder. Round begins again.
════════════════════════════════════════════════════════════════════════════
```

---

## PART 3 — WHAT IF HE HAD FAILED? (one branch shown concretely)

Say at TURN 5 he STILL couldn't reach the lookup-speed reason:

```
 RETURN  { axis:"RATIONALE", verdict:"SHAKY", category:"SHAKY" }
 STORE   shaky_count = 2   ← the second shaky on this axis
 CODE    pure-code rule fires: 2nd SHAKY = MISSING (no agent involved)
         axes[RATIONALE].verdict = MISSING
 ROUTE   category MISSING → PUSH A CHILD UNIT:
         new units row {id:13, slug:"dict-vs-list-lookup", depth:1,
                        parent_id:12, state:"NEW"}
         stack push: frame depth 1, is_top=true ; unit 12 frozen with
         resume_q = "why a dict and not a list of tuples?"
 NEXT    we now teach unit 13 (the sub-hole) with the SAME engine, from POINT.
         When 13 becomes OWNED → pop back to 12 → replay its resume_q →
         finish RATIONALE on the parent.
```

That is descent and climb-back, with real rows. Unit 12 cannot become OWNED
while unit 13 is live (the invariant). The paused question is never lost.

---

## PART 4 — READ THIS TO CHECK ANY ABSTRACT DOC
If DATA.md or CATALOGS.md names something you can't picture, map it here:
```
 "step"          → one row in the TIMELINE (one wakeup)  e.g. TURN 7 = the test step
 "axis"          → COMPREHEND / RATIONALE / ...          e.g. the 4 report-card rows
 "category"      → the label on his answer               e.g. "working code wrong reasoning"
 "verdict"       → the grade                             e.g. SHAKY then SOLID
 "stamp"         → the return.* JSON the agent hands back e.g. TURN 4's return.grade
 "wakeup packet" → what code injects to the agent        e.g. "lines + axis + level"
 "descent"       → PART 3 (push child unit 13)
 "distill"       → TURN 10 (write the archive, clear)
```
