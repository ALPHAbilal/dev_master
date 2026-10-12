# LOOPS: every agent, every way

Draft 0.1 · 2026-10-09 · `?` = waiting for your answer

```
 One rule:
   CODE reads the graph → picks the LOOP          (never an LLM)
   the LOOP fixes each agent's   context · tools · output schema
   the AGENT picks a BRANCH inside its schema     (from the learner's message)
```

---

## 1. The cast: armor of each agent

```
 ┌─────────────── ENGINE (code) ───────────────────────────────────────┐
 │ reads graph → picks loop → builds every context → validates output  │
 │ applies changes → checks boxes → writes story lines → moves stack   │
 │ NEVER: judges understanding                                         │
 └─────────────────────────────────────────────────────────────────────┘

 ┌─────────────── ORCHESTRATOR (LLM, the boss) ────────────────────────┐
 │ IN    loop instructions · graph view · checklist · stack            │
 │       learner message + paste · last tutor turn                     │
 │ TOOLS read_concept · read_file · search_repo · read_journey         │
 │       evaluate(target)        ← only in loops L3, L6                │
 │ OUT   the loop's schema (branches, §3)                              │
 │ NEVER sees the answer key · speaks to the learner                   │
 └─────────────────────────────────────────────────────────────────────┘

 ┌─────────────── EVALUATOR (LLM, called by the orchestrator) ─────────┐
 │ IN    ONE target (a checkbox, or an issue's closes_when)            │
 │       learner message + paste · answer key (task checkbox only)     │
 │ TOOLS none                                                          │
 │ OUT   { target, verdict: met | not_met | unclear, evidence_quote }  │
 │ NEVER sees the graph · the conversation · speaks to the learner     │
 │       returns hints or solution text (verdict + quote only)         │
 └─────────────────────────────────────────────────────────────────────┘

 ┌─────────────── TUTOR (LLM, talks to the learner) ───────────────────┐
 │ IN    its conversation + <tutor_kit> (templates · state · files)    │
 │ TOOLS read_concept · read_file · search_repo                        │
 │ OUT   the reply to the learner                                      │
 │ NEVER grades · decides what comes next · sees the answer key        │
 │       (except under show_answer, L8)                                │
 └─────────────────────────────────────────────────────────────────────┘
```

Who knows more:

```
 ORCHESTRATOR  ████████████████  graph, stack, checklist, message, files
 TUTOR         ██████████        conversation, kit
 EVALUATOR     ████              one target, one message, answer key
```

---

## 2. The map: all loops

```
                        ┌──────────────┐
                        │ T1 OPEN TASK │  engine only
                        └──────┬───────┘
                               ▼
        ┌─────────────────────────────────────────────┐
        │            ON TASK  (stack = [T])           │
        │   L2 working          L3 a box may be met   │◄──────────┐
        └───┬──────────────────────┬──────────────────┘           │
            │ OPEN_ISSUE           │ all boxes ☑                  │
            ▼                      ▼                              │
        ┌───────────────────┐   ┌──────────────┐                  │
        │ IN ISSUE  [T,I..] │   │ T2 CLOSE     │ engine + tutor   │
        │ L5 working        │   └──────┬───────┘                  │
        │ L6 may be solved  │          ▼                          │
        └──┬─────────┬──────┘     next task → T1                  │
           │         │                                            │
           │ OPEN_   │ END (solved | wrong_guess)                 │
           │ ISSUE   ▼                                            │
           │      ┌────────────────────┐                          │
           │      │ T3 BACK ONE STEP   │ engine only ─────────────┘
           │      └────────────────────┘   (to the issue above, or the task)
           ▼
        nested issue = same L5/L6, one level deeper (no depth limit)

  overlays, on top of any loop:
     L8 STUCK      N turns on the same focus, no progress
     T4 PARK/RESUME  learner stops, comes back exactly here
  in any loop:
     SIDE QUESTION  a branch, not a loop
```

`L` = a loop with an orchestrator call. `T` = a transition the engine does alone.

---

## 3. The loops, one by one

Each loop: **when** → **evaluator** → **orchestrator schema** → **engine** → **tutor**.

### T1 · open task (engine only)

```
 when      task starts (first, or after the previous one closed)
 engine    stack = [T] · checklist all ☐ · story "• Started T"
 tutor     kit: introduce_task + keep_goal_in_view
           state: task_goal · checklist · known_concepts
           (after a previous task: bridge_back + journey of the last task)
```

### L2 · on task, working

```
 when      stack = [T] · no box looks reachable yet
 evaluator no
 orchestrator schema:

   stuck_on_something_new?
   ├─ yes ─► OPEN_ISSUE { title, category, closes_when, why_for_learner,
   │                      return_note, templates[] }
   └─ no ──► side_question?
             ├─ yes ─► SIDE { title }
             └─ no ──► STAY { progress[] }       progress = evidence, may be empty

 engine    OPEN_ISSUE → create I · pause T with return_note · push I
           SIDE       → save I (set aside) · stay
           STAY       → record progress
 tutor     OPEN_ISSUE → kit: templates chosen (teach_one_concept · guided_trace · experiment_first)
                        state: current_focus · return_to · closes_when
           SIDE       → kit: answer_side_question (one turn), then the previous kit again
           STAY       → same kit as before
```

### L3 · on task, a box may be met

```
 when      stack = [T] · ? the graph says a box may be reachable
 evaluator yes, the orchestrator may call evaluate(box)

   orchestrator ──evaluate(C2)──► EVALUATOR ──► { C2, met, "label is unbound…" }
        ▲                                              │
        └──────────────────────────────────────────────┘
                engine checks ☑ C2 at once (can't be unchecked)

 orchestrator schema: same as L2
 engine    as L2 · plus "☑ C2 …" on the story
 tutor     as L2 · state: checklist updated
```

### L5 · in an issue, working

```
 when      stack = [T, …, I] · closes_when doesn't look reachable yet
 evaluator no
 orchestrator schema:

   still_an_issue?
   ├─ no ──► END { why: wrong_guess, evidence }        (solved needs L6)
   └─ yes ─► stuck_deeper?
             ├─ yes ─► OPEN_ISSUE { … as L2 }          nested
             └─ no ──► side_question?
                       ├─ yes ─► SIDE { title }
                       └─ no ──► STAY { progress[] }

 engine / tutor   as L2 · END → T3
```

### L6 · in an issue, may be solved

```
 when      stack = [T, …, I] · ? the graph says closes_when may be met
 evaluator yes: evaluate(I) with the template issue_check (no answer key)

 orchestrator schema: as L5, but
   END { why: solved, evidence }   allowed only if the evaluator said met
```

### T3 · back one step (engine only)

```
 when      END (solved or wrong_guess)
 engine    mark I solved | wrong_guess · pop · focus = the one above
           story: "★ Cleared — I" or "✕ Not the problem after all — I"
                  "↩ Came back to … · picking up: <return_note>"
 tutor     kit: bridge_back (one turn) + the kit the parent had
```

### T2 · close (engine + tutor)

```
 when      every box ☑ (after any L3)
 engine    story "★ Done — goal · you now know …" · queued discoveries → bank
 tutor     kit: close_task · write_journey open
 then      next task → T1, with fresh agents
```

### L8 · stuck (overlay)

```
 when      ? N turns on the same focus, no new progress
 orchestrator schema: the loop's own schema + one branch:

   CHANGE_APPROACH { how: reframe | show_answer }

 tutor     reframe     → kit: reframe_explanation
           show_answer → kit: show_answer + the answer key readable
                         (the only time the tutor sees it)
```

### T4 · park / resume (engine only)

```
 park      learner stops (button) → run parked, stack kept
 resume    fresh agents · tutor kit: bridge_back with the focus's return_note
           story "↩ Came back to … · picking up: …"
```

---

## 4. One T3 turn through the whole machine

```
 learner: "it says UnboundLocalError: label"
     │
     ▼ ENGINE      stack=[T3] · box C2 "found the real error" looks reachable → L3
     ▼ ORCH        calls evaluate(C2)
     ▼ EVALUATOR   { C2, met, "UnboundLocalError: label" }
     ▼ ENGINE      ☑ C2
     ▼ ORCH        stuck_on_something_new? yes
                   OPEN_ISSUE { "a loop variable only exists if the loop ran",
                                closes_when: "explains why label is unbound for a guest" }
     ▼ ENGINE      create I1 · pause T3 · push I1 · story lines
     ▼ TUTOR       kit teach_one_concept + experiment_first → replies to the learner
```

---

## 5. Open (`?`)

```
 O1  How does the engine know a box or closes_when "may be reachable" (L3, L6)?
     a) the crafter writes per box what must happen first
     b) every turn where the learner pastes code or an answer
     c) the orchestrator flags it on the previous turn

 O2  Who writes an issue's closes_when?   proposal: the orchestrator, in OPEN_ISSUE

 O3  Done = all boxes ☑.  Do the task's concepts also need to be "known"?   yes / no

 O4  L8: how many turns is "stuck"?  And may show_answer be chosen at all?

 O5  wrong_guess: does the orchestrator decide it alone (L5), or does it need
     the evaluator too?
```
