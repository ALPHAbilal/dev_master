# LEGO: the intelligence layer, piece by piece

Draft 0.19 · 2026-10-11 · `?` = waiting for your answer

**Naming rule, for everything:** no abbreviations. Every field name is a full phrase, and every ID (task T3, issue I1, concept 15, box 2) appears with its name.

```
 §0  the idea                   §1  the two axes            §2  the loops
 §3  the question tree          §4  leaf → what the tutor gets
 §5  the seven kinds of piece   §6  the three agents        §7  the cards
 §8  one real turn              §9  the stuck ladder        §10 the task sheet
 §11 contracts                  §12 the tray                §13 before learners
 §14 old names → new names      §15 the gold patterns       §16 decided · proposals · open
```

---

## 0. The idea

```
   GRAPH ───read───► ENGINE (code) ───► picks a CARD   "where are we?"
     ▲                                       │
     │                                       ▼
     │                     snaps PIECES onto each agent's PLATE
     │                                       │
     │                                       ▼
     │                 AGENT (LLM) walks its QUESTION TREE to ONE LEAF
     │                                       │
     └──────write──── EFFECTS (code) ◄───────┘

   LLMs judge.  Code reads, snaps, checks and writes.  Code never judges.
```

Three levels, like LEGO:

```
   PIECE ───snaps onto a───► PLATE ───plates sit on a───► CARD
   one part                  one agent call               one loop

   example: the piece "teach_one_concept" sits on the tutor's plate,
            on the card "in an issue"
```

How a piece gets onto a plate:

```
   ■  fixed    code always snaps it in
   ◆  picked   the orchestrator picks it
   ◇  gated    code snaps it in only when a check is true
   □  open     on the shelf: the agent reads it with a tool if it wants
```

---

## 1. The two axes

```
              WHERE                                  STATE
     (code reads the graph)              (the orchestrator names it from the
                                          message; a few come from code)
  on the task · in an issue (any         on track · side question · uncertain ·
  depth) · saved issues waiting ·        stuck · gap found · needs something
  just came back                         first · several gaps · wants a saved
                                         issue · solved · already knew ·
                                         all boxes ☑
               │                                       │
               ▼                                       ▼
  what the ORCHESTRATOR gets, and        the MOVE on the graph, and what
  which branches of its tree exist       the TUTOR gets
               ▲                                       │
               └────────────── next turn ◄─────────────┘
```

The states come from the architecture spec: §2 (the learner does anything, in any order), §4 (the assessments), §5 (ten kinds of difficulty), §7C (several issues open at once), §20 (a saved issue picked up later).

---

## 2. The loops

```
┌─ LOOP 1 · TASKS ──────────────────────────────────────────────────────┐
│                                                                       │
│  task 1 ──► LOOP 2 ──► all boxes ☑ ──► close ──► task 2 ──► LOOP 2 …  │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘

┌─ LOOP 2 · ONE TURN: every learner message, at any depth ──────────────┐
│                                                                       │
│  LEARNER does anything, in any order:                                 │
│  read · plan · edit · test · debug · ask · experiment · learn         │
│     │                                                                 │
│     ▼                                                                 │
│  CODE          where are we? ──► the tree for "on the task" or "in an │
│                issue"                                                 │
│     │                                                                 │
│     ▼                                                                 │
│  ORCHESTRATOR  walks the question tree (§3), one question per level   │
│     │          may call the EVALUATOR on the way                      │
│     ▼                                                                 │
│  CODE          task done? ────────────────► DONE ──► LOOP 1           │
│                no progress for N turns? ──► stuck level + 1           │
│                one level deeper? ─────────► LOOP 3                    │
│                issue over? ───────────────► BACK one step             │
│     │                                                                 │
│     ▼                                                                 │
│  TUTOR         acts with the pieces code snapped in ──► LEARNER       │
└───────────────────────────────────────────────────────────────────────┘

┌─ LOOP 3 · DETOUR = LOOP 2 again, one level deeper ────────────────────┐
│                                                                       │
│   task ──► issue ──► deeper issue ──► …   each level runs LOOP 2      │
│   task ◄── issue ◄── deeper issue         solved or already knew:     │
│                                           back ONE step               │
│                                                                       │
│   saved issues stay open; picked up later, even in another task       │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 3. The question tree: one small question per level

The orchestrator never sees a flat menu. It answers one question, and only that answer's sub-branches exist.

```
 BEFORE: one flat menu, 13 choices         NOW: a tree, at most 4 choices per question
 on track · side question · uncertain ·    Question 0   still an issue?   (in an issue only)
 stuck · gap · needs something first ·     Question 1   progress | problem | turns away
 several gaps · saved issue · solved ·     Question 2   unsure | wrong idea | missing | stuck
 already knew · wrong idea · done          Question 3   go there now? no | yes
```

```
 [in an issue only]
 QUESTION 0 · still an issue?                    ← the evaluator decides
     ├─ no (met) ─────────────────────────────────► BACK          one step up
     └─ yes ──► Question 1

 QUESTION 1 · what does the message show?        ← on the task, start here
     ├─ progress ─────────────────────────────────► ON_TRACK      + its kind
     │
     ├─ a problem ──► QUESTION 2 · what problem?
     │                ├─ unsure they get it ──────► UNCERTAIN     one short probe
     │                ├─ a wrong idea ────────────► WRONG_IDEA    + what went wrong, their words
     │                ├─ something missing ───────► GAP           + the gaps
     │                │                               each gap: does it block the work?
     │                │                                 yes ► one level deeper (the first one)
     │                │                                 no  ► saved for later
     │                └─ ◇ still stuck ───────────► STUCK         + why (this level's set, §9)
     │                   (only from stuck level 1)
     │
     └─ the learner turns away ──► QUESTION 3 · go there now?
                                   ├─ no, just wondering ──► SIDE_QUESTION
                                   │                         answer briefly, save it
                                   └─ yes ─────────────────► WANTS_TO_GO
                                                             one level deeper
                                                             (a new issue, or ◇ a saved one)

 decided by CODE, never offered to the orchestrator:
   the job box ☑ + every concept checked ──► DONE
   no progress for N turns ──► stuck level + 1
```

What the orchestrator sees for each option: one short description. It never sees the tutor's instructions.

```
 QUESTION 0 · still an issue?                    (in an issue only)
     yes            the closing condition isn't shown yet
     no             the evaluator said met (call evaluate first)

 QUESTION 1 · what does the message show?
     progress       moves forward on the current work, or asks about it
     problem        wrong, blocked, unsure, or not moving
     turns_away     asks about something off the current path

 QUESTION 2 · what problem?                      (under "problem")
     unsure         may or may not get it; one short probe will tell
     wrong_idea     believes or does something wrong about the current work
     missing        something they need isn't there yet (a gap)
     ◇ stuck        not moving; pick why          (only from stuck level 1)

 QUESTION 3 · go there now?                      (under "turns_away")
     no             just wondering: answer briefly, save it
     yes            wants to go there now: one level deeper

 KIND                                            (for progress, each gap, a new issue)
      1 · task meaning          unsure what the task asks
      2 · reading the code      finding or following the code
      3 · a concept             an idea they need
      4 · planning              choosing how to approach it
      5 · writing code          knows the idea, can't write it yet
      6 · tools and setup       editor, running, installing
      7 · debugging             finding why it fails
      8 · testing and checking  making sure it works
      9 · showing mastery       showing they really understand
     10 · frustration           upset, tired, close to giving up

 WHY STUCK                                       (only this level's set is shown)
     level 1    didnt_get_it          the explanation didn't land
                hasnt_said_view       we don't know what they think yet
     level 2    step_too_big          the step asks too much at once
                lost_where_to_look    they don't know where to look
     level 3    needs_one_done        they need to see a similar one done
                too_many_paths        too many options; they can't pick
     any level  frustrated            upset or tired
```

Which branch exists when:

```
 branch                        exists only when                          decided by
 ────────────────────────────  ────────────────────────────────────────  ──────────────────────────
 Question 0 · still an issue?  in an issue                               the evaluator
 BACK                          Question 0 = no (the evaluator said met)  code
 WANTS_TO_GO · a saved issue   a saved issue exists                      the orchestrator
 evaluate a box                on the task, an unticked box exists       the orchestrator
 Question 2 · still stuck      stuck level 1 or higher (code counts)     the orchestrator picks why
 DONE                          the job box ☑ + every concept checked     code
 everything else               always                                    the orchestrator
```

Code builds the answer format from this tree each turn, so a branch that can't exist isn't in it at all:

```
 { "still_an_issue": true,                       ← only in an issue
   "shows": "problem",                           ← Question 1: 3 options
   "problem": {                                  ← exists only under "problem"
     "type": "missing",                          ← Question 2: 3 or 4 options
     "gaps": [ { "title": "a loop variable only exists if the loop ran",
                 "kind": 3, "blocks": true,
                 "closes_when": "explains why label is unbound for a guest" } ],
     "return_note": "you have the traceback; line 722 reads label" } }
```

---

## 4. Leaf → what the tutor gets

```
 leaf             the learner's state (spec §4)               decided by          what the tutor gets (code snaps it)
 ───────────────  ──────────────────────────────────────────  ──────────────────  ────────────────────────────────────────
 ON_TRACK         on track                                    the orchestrator    the piece for its kind (below)
 UNCERTAIN        understanding uncertain                     the orchestrator    probe_understanding
 WRONG_IDEA       a misconception about the current work      the orchestrator    the same piece + misconception_to_watch;
                                                                                  the difficulty goes into the task sheet
 GAP that blocks  gap found · needs something first           the orchestrator    the piece for the gap's kind (below)
 several GAPs     several gaps                                the orchestrator    the piece for the first one that blocks;
                                                                                  the others are saved
 GAP, no block    a gap that can wait                         the orchestrator    nothing new (the gap is saved)
 SIDE_QUESTION    side question                               the orchestrator    answer_side_question, for one turn
 WANTS_TO_GO      wants to go there now, or to a saved issue  the orchestrator    the piece for its kind (below)
 STUCK            stagnating                                  code: the level     the piece for that why (§9)
                                                              orchestrator: why
 BACK             solved · already knew                       the evaluator       bridge_back + the piece the step above
                                                                                  had before the detour
 DONE             task completed (the job box ☑ + every       code                close_task
                  concept checked)
```

The kind of work picks the tutor's piece (spec §2 activities = spec §5 kinds):

```
 kind                        tutor piece
 ──────────────────────────  ──────────────────────────────────────  ───
  1 · task meaning           clarify_goal                            NEW
  2 · reading the code       guided_trace
  3 · a concept              teach_one_concept · experiment_first
  4 · planning               plan_approach                           NEW
  5 · writing code           guide_fix
  6 · tools and setup        fix_setup                               NEW
  7 · debugging              guide_debugging
  8 · testing and checking   check_results                           NEW
  9 · showing mastery        probe_understanding
 10 · frustration            encourage_pause                         NEW
```

So the orchestrator only names a **leaf + kind (+ why when stuck)**. Code snaps the tutor's pieces.

---

## 5. The seven kinds of piece

```
   kind          what it is                                  made by         used by
   ────────────  ──────────────────────────────────────────  ──────────────  ────────
   instruction   text that tells an agent how to act         you (config)    an agent
   fact          one value copied from the graph ("state")   code            an agent
   file          a file the agent may read                   the crafters,   an agent
                                                             the learner
   tool          an action the agent may call, with its      code            an agent
                 guide (what · when · how)
   leaf          one end of the question tree                you (config)    code
   effect        what code does to the graph for a leaf      code            —
   check         a yes/no question code asks the graph       code            —

        BEFORE the call              DURING the call                  AFTER the call
   ─────────────────────────   ──────────────────────────────   ──────────────────────
   checks pick the card, the    instructions · facts · files ·   a leaf comes back
   gated pieces and the         tools go IN to the agent         effects write the graph
   tree's branches
```

**Studs.** A piece can bring other pieces with it. Every instruction piece lists the facts it needs, and code snaps them in. Nobody picks facts by hand.

---

## 6. The three agents

Every agent call has the same plate:

```
   ┌─ PLATE ────────────────────────────────────────────────
   │ instructions   [ ] [ ] [ ]   how to act
   │ facts          [ ] [ ] [ ]   what is true now
   │ files          [ ] [ ]       what it may read
   │ tools          [ ] [ ]       what it may do
   │ message        what the learner said (+ pasted code)
   ├────────────────────────────────────────────────────────
   │ answer         its question tree ──► exactly one leaf
   └────────────────────────────────────────────────────────
```

What may **ever** go on each agent's plate:

```
 ORCHESTRATOR · the boss · knows the most                 ████████████████
   instructions   orchestrator pieces, with a short description for every option
   facts          every graph fact
   files          concepts · repository · journeys · task sheets
                  (it reads them if it wants)
   tools          read_concept · read_file · search_repo · read_journey · evaluate ·
                  pull_checkpoints · Read · Grep (in its temporary folder)
   message        the learner's message + pasted code · the tutor's last reply
   answer         the question tree (§3)
   decides        its leaf · when to call the evaluator
   never          the answer key · the tutor's instructions · talks to the learner

 EVALUATOR · the judge · knows the least                  ████
   instructions   evaluator.task_box or evaluator.closes_when
   facts          ONE target: a box, or an issue's closing condition
   files          the answer key (task boxes only)
   tools          pull_checkpoints · Read · Grep (in its temporary folder)
   message        the learner turns the orchestrator points to, copied word for word
   answer         VERDICT: met | not met | unclear + the learner's own words
   never          the graph · the orchestrator's labels · gives hints

 TUTOR · the voice · knows what it needs                  ██████████
   instructions   the instructions for this turn, in the system prompt, rebuilt
                  every turn: the pieces code snapped in (from leaf + kind + why)
   facts          the facts its pieces need (studs), inside those instructions
   files          the task sheet of its task (always) · concepts · repository
   tools          read_concept · read_file · search_repo · write_journey (at close)
   history        the whole task as it happened: the learner's messages, its own
                  tool calls and their results, its replies (never an old
                  instruction, never old thinking; §11.5)
   answer         REPLY: free text to the learner
   never          grades · decides what comes next · the answer key ·
                  the orchestrator's answer
```

---

## 7. The cards: which pieces go on which plate, per loop

```
                       ┌──────────────────┐
                       │  A · OPEN TASK   │   code + tutor
                       └────────┬─────────┘
                                ▼
                ┌────────────────────────────────┐   all boxes ☑   ┌──────────────┐
          ┌────►│  B · ON THE TASK               │────────────────►│ E · CLOSE    │
          │     └───────────────┬────────────────┘                 └──────┬───────┘
          │                     │ one level deeper                        ▼
          │                     ▼                                   next task ──► A
          │     ┌────────────────────────────────┐
          │     │  C · IN AN ISSUE (any depth)   │◄─────┐
          │     └───────┬──────────────┬─────────┘      │ one level
          │             │ BACK         └────────────────┘ deeper
          │             ▼
          │     ┌────────────────────────────────┐
          └─────│  D · BACK ONE STEP             │──► C, if the step above
                └────────────────────────────────┘    is an issue

     on top of B or C:   the stuck ladder (§9)
```

### A · open task

```
╔═ A · OPEN TASK ════════════════════════════ code + tutor, no learner message
║ WHEN          check.task_just_opened
║ CODE          stack = the task · a fresh task sheet: every box ☐ (§10)
║               story line "• Started <task>"
╠═ TUTOR ═════════════════════════════════════════════════════════════════════
║ instructions  ■ tutor.base  ■ introduce_task  ■ keep_goal_in_view
║               ◇ bridge_back (if a task came before)
║ facts         ■ studs: task_goal · task_sheet
║ files         ■ the fresh task sheet (§10)
║               ◇ the journey of the previous task (if a task came before)
╠═ NEXT ══════════════════════════════════════════════════════════════════════
║ card B
╚═════════════════════════════════════════════════════════════════════════════
```

### B · on the task

```
╔═ B · ON THE TASK ═══════════════════════════════════════════════════════════
║ WHEN          check.on_task
╠═ 1 · ORCHESTRATOR ══════════════════════════════════════════════════════════
║ instructions  ■ orchestrator.base  ■ orchestrator.on_task
║               ◇ orchestrator.stuck (check.stuck)
║               ◇ orchestrator.saved_waiting (check.has_saved)
║ facts         ■ task_goal  ■ task_sheet  ■ next_box  ■ stack  ■ recent_progress
║               ■ stuck_level  ◇ saved_issues (check.has_saved)
║ files         □ concepts  □ repository  □ journeys  □ task sheets
║ tools         ■ read_concept  ■ read_file  ■ search_repo  ■ read_journey
║               ■ pull_checkpoints  ■ Read  ■ Grep
║               ◇ evaluate (any unticked box, in any order) (check.has_unticked_box)
║ message       the learner's message + pasted code · the tutor's last reply
║ answer        the question tree (§3), from Question 1 (no Question 0 here)
╠═    the EVALUATOR, only when the orchestrator calls evaluate ═══════════════
║ instructions  ■ evaluator.task_box
║ facts         ■ the box, with its text
║ files         ■ the answer key of this task
║ tools         ■ pull_checkpoints  ■ Read  ■ Grep
║ message       the learner turns the orchestrator points to, word for word
║ answer        VERDICT { box, met | not met | unclear, the learner's words }
║               met ──► effect.check_box at once (records the turn; checks the
║               concept when all its boxes are ☑)
╠═ 2 · CODE AFTER ════════════════════════════════════════════════════════════
║ every leaf                      ──► effect.record_progress · stuck counter
║ GAP that blocks · WANTS_TO_GO   ──► effect.open_issue ──► card C
║ GAP, no block · SIDE_QUESTION   ──► effect.save_issue
║ WRONG_IDEA                      ──► effect.record_difficulty (task sheet)
║ then: the task is done          ──► card E
╠═ 3 · TUTOR (from the card the turn ends in, §8) ════════════════════════════
║ instructions  ■ tutor.base  ■ keep_goal_in_view
║               ■ the piece for the leaf + kind (§4)
║               ◇ the stuck piece for the orchestrator's why (§9)
║ facts         ■ the studs of its pieces
║ files         ■ the task sheet (always, §10)
║               ◆ files the orchestrator unlocked, each with a reason
║ tools         ■ read_concept  ■ read_file  ■ search_repo
║ answer        REPLY
╚═════════════════════════════════════════════════════════════════════════════
```

### C · in an issue

```
╔═ C · IN AN ISSUE ═══════════════════════════════════════════════════════════
║ WHEN          check.in_issue
╠═ 1 · ORCHESTRATOR ══════════════════════════════════════════════════════════
║ instructions  ■ orchestrator.base  ■ orchestrator.in_issue
║               ◇ orchestrator.stuck (check.stuck)
║               ◇ orchestrator.saved_waiting (check.has_saved)
║               ◇ orchestrator.deep (check.deep: "still serving the task?")
║ facts         ■ task_goal  ■ task_sheet  ■ stack  ■ current_focus  ■ closes_when
║               ■ return_to  ■ recent_progress
║               ■ stuck_level  ◇ saved_issues (check.has_saved)
║ files         □ concepts  □ repository  □ journeys  □ task sheets
║ tools         ■ read_concept  ■ read_file  ■ search_repo  ■ read_journey
║               ■ pull_checkpoints  ■ Read  ■ Grep
║               ■ evaluate (this issue only)
║ message       the learner's message + pasted code · the tutor's last reply
║ answer        the question tree (§3), from Question 0
╠═    the EVALUATOR, only when the orchestrator calls evaluate ═══════════════
║ instructions  ■ evaluator.closes_when
║ facts         ■ the issue, with its closing condition
║ files         none (an issue has no answer key)
║ tools         ■ pull_checkpoints  ■ Read  ■ Grep
║ message       the learner turns the orchestrator points to, word for word
║ answer        VERDICT { issue, met | not met | unclear, the learner's words }
╠═ 2 · CODE AFTER ════════════════════════════════════════════════════════════
║ every leaf                      ──► effect.record_progress · stuck counter
║ BACK                            ──► card D, this turn
║ GAP that blocks · WANTS_TO_GO   ──► effect.open_issue ──► card C, deeper
║ GAP, no block · SIDE_QUESTION   ──► effect.save_issue
║ WRONG_IDEA                      ──► effect.record_difficulty (task sheet)
║ rule: the evaluator said met  ⇔  BACK   (code rejects anything else)
╠═ 3 · TUTOR ═════════════════════════════════════════════════════════════════
║ instructions  ■ tutor.base
║               ■ the piece for the leaf + kind (§4)
║               ◇ the stuck piece for the orchestrator's why (§9)
║ facts         ■ the studs of its pieces
║ files         ■ the task sheet (always, §10)
║               ■ the issue's linked concept file, if any
║               ◆ files the orchestrator unlocked, each with a reason
║ tools         ■ read_concept  ■ read_file  ■ search_repo
║ answer        REPLY
╚═════════════════════════════════════════════════════════════════════════════
```

### D · back one step

```
╔═ D · BACK ONE STEP ═════════════════════════════════ code + tutor, same turn
║ WHEN          BACK (the evaluator said met)
║ CODE          effect.back_one_step · story line "★ Cleared — <issue>", or
║               "✕ Already knew it — <issue>" when met on the issue's first turn
║               focus = the issue above, or the task
║               story line "↩ Came back to … · picking up: <return note>"
╠═ TUTOR ═════════════════════════════════════════════════════════════════════
║ instructions  ■ tutor.base  ■ bridge_back (this turn only)
║               ■ the piece the step above had before the detour
║ facts         ■ studs: return_to + what the pieces need
╠═ NEXT ══════════════════════════════════════════════════════════════════════
║ card C if the step above is an issue · card B if it is the task
╚═════════════════════════════════════════════════════════════════════════════
```

### E · close task

```
╔═ E · CLOSE TASK ════════════════════════════════════ code + tutor, same turn
║ WHEN          check.task_done (the job box ☑ + every concept checked)
║ CODE          effect.close_task · story line "★ Done — <goal>"
╠═ TUTOR ═════════════════════════════════════════════════════════════════════
║ instructions  ■ tutor.base  ■ close_task
║ facts         ■ studs: task_sheet · journey_so_far
║ tools         ■ write_journey
╠═ AFTER THE REPLY ═══════════════════════════════════════════════════════════
║ code archives the task sheet and adds the raw discoveries to the
║ concept bank (§10)
╠═ NEXT ══════════════════════════════════════════════════════════════════════
║ card A for the next task: fresh agents, a fresh task sheet
╚═════════════════════════════════════════════════════════════════════════════
```

---

## 8. One real turn

```
   the ORCHESTRATOR plate comes from the card the turn STARTS in
   the TUTOR plate comes from the card the turn ENDS in
```

Task T3 (guests always get the generic error). The learner pastes the traceback:

```
   learner: "UnboundLocalError: label"
     │
     ▼ START  card B · on the task                          stack: T3
     │  orchestrator ── evaluate(box 2) ──► evaluator ──► met ──► code ticks box 2
     │  Question 1: a problem ──► Question 2: something missing ──► GAP
     │      title:         a loop variable only exists if the loop ran
     │      kind:          3 · a concept
     │      blocks:        yes
     │      closes_when:   explains why label is unbound for a guest
     │      return_note:   you have the traceback; line 722 reads label
     │  code: opens issue I1 · task T3 keeps its return note · one level deeper
     ▼ END    card C · in issue I1                          stack: T3 ▸ I1
        tutor: tutor.base + teach_one_concept + experiment_first (kind 3) ──► REPLY
```

The learner explains why `label` is unbound:

```
   learner: "the loop never ran for a guest, so label was never set"
     │
     ▼ START  card C · in issue I1                          stack: T3 ▸ I1
     │  Question 0: orchestrator ── evaluate(I1) ──► evaluator ──► met ──► BACK
     ▼        card D   code: ★ Cleared I1 · one step back
     ▼ END    card B · on the task                          stack: T3
        tutor: bridge_back + keep_goal_in_view + guide_debugging
               (the piece task T3 had before the detour) ──► REPLY
     ▼ NOTE   concept 15 is not checked yet: only its box (box 3) can check it,
              and boxes are judged on the task, on the next turn
```

---

## 9. The stuck ladder (on top of B or C)

```
   code counts, per focus, the turns with no progress
   (no progress, no box ☑, no "met") ──► the LEVEL

   from level 1, the tree grows one branch: Question 2 · ◇ still stuck ──► WHY?
   each level has its OWN prepared set; the orchestrator picks one why,
   and code snaps that why's tutor piece

   turns with no progress  level  why stuck (the orchestrator picks)         tutor piece (code snaps)
   ──────────────────────  ─────  ─────────────────────────────────────────  ────────────────────────
   0 – 1                   0      (the question doesn't exist)               —
   2                       1      didn't get the explanation                 reframe_explanation
                                  hasn't said what they think                ask_their_view · NEW
   3                       2      the step is too big                        smaller_step · NEW
                                  doesn't know where to look                 point_to_place · NEW
   4 or more               3      needs to see one done                      worked_example · NEW
                                  (a similar one, never this task's answer)
                                  too many paths open                        offer_choices · NEW
   any                     any    frustrated or tired                        encourage_pause · NEW

   any progress ──► back to level 0
   the answer itself ──► NEVER, at any level

   at every level the orchestrator also gets ◇ orchestrator.stuck:
   "is a missing piece behind this? then GAP, blocks: yes"
```

The levels and their sets are lists in config. Changing them is a config change, not a code change.

---

## 10. The task sheet

One task sheet per task, per learner. It holds the task's boxes, grouped the way teachers design learning: first the job itself, then each concept with the boxes that prove it. **Code writes all of it, at once,** from two sources only: the evaluator's verdicts and the orchestrator's leaves. There is no recorder. When the task closes, the sheet is archived and the next task starts a fresh one.

```
 TASK T3 · make guests get a real answer
 │
 ├─ THE JOB IS DONE
 │    ☐ box 1 · the fix works: a guest gets a real answer
 │
 └─ THE IDEAS ARE UNDERSTOOD
      ├─ concept 17 · a broad except hides the real error
      │    ☐ box 2 · finds the real error behind the generic message
      ├─ concept 15 · loop variables outlive the loop
      │    ☐ box 3 · explains why label is unbound for a guest
      └─ concept 13 · OpenAI tool calling
           ☐ box 4 · explains what the label decides in the request

 a concept is checked  =  all of its boxes are ☑
 the task is done      =  the job box ☑  +  every concept checked
```

**Why it exists:** the tutor reads it to decide what to teach, what to stress, and what not to teach again. The orchestrator reads it every turn.

```
 WHO READS IT       WHAT IT DECIDES WITH IT           SO THE SHEET HOLDS
 ─────────────────  ────────────────────────────────  ──────────────────────────────────
 the tutor          skip it, or still teach it?       checked: yes / not yet
 (always)           what exactly to stress?           the difficulties, in order, with
                                                      the learner's own words
                    did they have it, then lose it?   had_it_then_missed
 the orchestrator   which box to judge next?          the boxes and their ticks
 (every turn)       is this a wrong idea about a      checked + the difficulties
                    concept they already showed?
```

**The file** (JSON, one concept shown):

```json
{
  "task": "T3 · Guests always get the generic error",
  "the_job_is_done": {
    "box": "box 1 · the fix works: a guest gets a real answer",
    "ticked_at_turn": 9
  },
  "concepts": [
    {
      "concept": "concept 15 · loop variables outlive the loop",
      "boxes": [
        { "box": "box 3 · explains why label is unbound for a guest", "ticked_at_turn": 8 }
      ],
      "checked": true,
      "times_it_came_up": 5,
      "difficulties": [
        { "turn": 4,
          "what_went_wrong": "expected label to have a value after a loop that never ran",
          "learner_words": "None? In JS it would be undefined." }
      ],
      "had_it_then_missed": []
    }
  ]
}
```

```
 key                    description (every key is written by code)
 ─────────────────────  ──────────────────────────────────────────────────────────
 task                   the task: its ID and its title
 the_job_is_done        the box that proves the job itself is done (not an idea)
 concepts               every concept this task needs, as the task crafter listed
                        them; one entry each
 concept                the concept's ID and its name, from the concept bank
 boxes                  the boxes that prove this concept (from the task crafter)
   box                  the box's number and what the learner must show
   ticked_at_turn       the turn the evaluator said met; null until then; the
                        turns also show the order the boxes were ticked in
 checked                true when all of this concept's boxes are ticked; back to
                        false when a WRONG_IDEA or a GAP about it comes after
 times_it_came_up       how many turns touched this concept: a leaf named it, the
                        focus issue is linked to it, or one of its boxes was judged
 difficulties           every WRONG_IDEA or GAP about this concept, in order
   turn                 the turn it showed
   what_went_wrong      one sentence, from the orchestrator's leaf
   learner_words        the learner's exact words, from the leaf; code checks that
                        they are really in that turn
 had_it_then_missed     every time the concept was checked and a WRONG_IDEA or a
                        GAP about it came after
   turn                 the turn it broke
   issue                the issue opened for it, if a GAP opened one
   angle_they_missed    the leaf's what_went_wrong: the new angle where it broke
   learner_words        their exact words

 read by:        the tutor (always) · the orchestrator (every turn)
 never read by:  the evaluator
```

**Where the sheet changes** (always code, always at once):

```
 point in the loops                 what changes
 ─────────────────────────────────  ────────────────────────────────────────────────────────────
 a task opens (card A)              a fresh sheet: every box unticked, every concept unchecked,
                                    every count 0
 the evaluator says met on a box    that box gets ticked_at_turn; if it was the concept's last
                                    unticked box, the concept becomes checked
 a WRONG_IDEA or a GAP names a      a new difficulty; if the concept was checked: checked =
 concept (or the focus issue is     false and a new had_it_then_missed entry
 linked to one)
 any turn that touches a concept    times_it_came_up + 1
 the task closes (card E)           archived; the raw discoveries go into the concept bank
 anywhere else                      nothing
```

**Where the orchestrator has instructions about concepts:**

```
 where                        the piece                    what it asks
 ───────────────────────────  ───────────────────────────  ──────────────────────────────────────
 every turn (cards B and C)   orchestrator.base            read the task sheet: which box to judge
                              (a few lines)                next; a wrong idea about a checked
                                                           concept is a real signal, so name it
 when it answers WRONG_IDEA   the leaf's "concept" field   name the concept when it is one; that
 or GAP                       and its description          is how the sheet knows where it broke
 everywhere else              nothing about concepts       —
```

**Discoveries at the close.** Code adds a raw entry to the learner's concept bank, labeled discovered, for each saved side question and each concept-kind gap (kind 3) that had no bank concept. In T3: issue I3 becomes `discovered concept 1 · a test can swap the real OpenAI client for a fake one`. Issue I2 was about this codebase's flow (kind 2), so it stays in the journey only.

---

## 11. Contracts: what each agent sees and answers

### 11.1 Who talks to whom

Agents never talk to each other. Code carries and checks every message.

```
      LEARNER      CODE        ORCHESTRATOR      EVALUATOR       TUTOR
         │           │               │               │             │
  1      ├─ message ►│               │               │             │
  2      │           ├─ plate ──────►│               │             │
  3      │           │◄─ evaluate ───┤               │             │
  4      │           ├─ plate ───────┼──────────────►│             │
  5      │           │◄─ verdict ────┼───────────────┤             │
  6      │           ├─ result ─────►│               │             │
  7      │           │◄─ answer ─────┤               │             │
  8      │           ├─ pieces ──────┼───────────────┼────────────►│
  9      │◄──────────┼───────────────┼───────────────┼──── reply ──┤

  1   the learner's message (+ pasted code)
  2   code builds the orchestrator's plate (§11.2)
  3   tool call evaluate(box 2, turns 12–13): a target and turn numbers, no free text
  4   code builds the evaluator's plate: the target, the answer key, the turns
      copied word for word (§11.4)
  5   the verdict and the learner's own words
  6   code checks it (the right target; the words are really in those turns),
      ticks the box if met, and returns the result to the orchestrator
  7   the orchestrator's answer (§11.3)
  8   code checks it, writes the graph and the story lines, snaps the tutor's pieces
  9   the tutor's reply; stored, and the orchestrator reads it next turn
```

```
 ORCHESTRATOR ──► EVALUATOR      a target and turn numbers           (no free text)
 EVALUATOR    ──► ORCHESTRATOR   a verdict and the learner's own words
 ORCHESTRATOR ──► TUTOR          labels only; code turns them into pieces
 TUTOR        ──► ORCHESTRATOR   its last reply, read on the next turn
 EVALUATOR    ──► TUTOR          nothing, ever
```

### 11.2 The orchestrator: what it sees in each scenario

```
                                             on the task       in an issue       rough tokens
   ────────────────────────────────────────  ────────────────  ────────────────  ────────────
   orchestrator.base (role, how to walk)     ■                 ■                 600
   the card's piece (on_task or in_issue)    ■                 ■                 150
   the question tree + option descriptions   ■ questions 1–3   ■ questions 0–3   400
   kinds 1–10 + their descriptions           ■                 ■                 200
   task_goal                                 ■                 ■                 30
   next_box                                  ■                 —                 15
   stack + return notes                      ■                 ■                 60
   current_focus + closes_when               —                 ■                 50
   task_sheet (boxes, concepts, difficulties)  ■                 ■                 200
   recent_progress (the last 5)              ■                 ■                 100
   stuck_level                               ■                 ■                 5
   tools + their guides                      ■                 ■                 600
   the learner's message + pasted code       ■                 ■                 50 – 2,000
   the tutor's last reply                    ■                 ■                 200
   ── gated ──
   stuck: orchestrator.stuck + the why set   ◇ level ≥ 1       ◇ level ≥ 1       150
   saved: orchestrator.saved_waiting + list  ◇ if any saved    ◇ if any saved    80
   deep: orchestrator.deep                   —                 ◇ depth ≥ 4       50
   ────────────────────────────────────────  ────────────────  ────────────────  ────────────
   total: about 2,500 – 4,500 tokens per call, far under the 100K price step

   NEVER:      the answer key · the tutor's instructions
   ON DEMAND:  older turns, through pull_checkpoints (§11.6)
```

### 11.3 The orchestrator's answer format

```
 ON THE TASK                             IN AN ISSUE
 {                                       {
   "shows": "progress"                     "still_an_issue": true,
          | "problem"                      "shows": …   same as on the task
          | "turns_away",                }
   …the fields of that branch…
   "progress":    [ … ]    optional      { "still_an_issue": false }
   "tutor_files": [ … ]    optional        nothing else; only after "met"
 }
```

```
 leaf            its fields
 ──────────────  ─────────────────────────────────────────────────────────────
 ON_TRACK        "shows": "progress", "kind": 7,
                 "progress": [ { "did": "reproduced the bug as a guest", "turn": 3 } ]
 UNCERTAIN       "shows": "problem",
                 "problem": { "type": "unsure", "probe_target": "box 3" }
 WRONG_IDEA      "shows": "problem",
                 "problem": { "type": "wrong_idea",
                              "what_went_wrong": "expected label to have a value after
                                                  a loop that never ran",
                              "learner_words": "None? In JS it would be undefined.",
                              "concept": "concept 15" }
 GAP             "shows": "problem",
                 "problem": { "type": "missing",
                              "gaps": [ { "title": …, "kind": 3, "blocks": true,
                                          "closes_when": …, "why_for_learner": …,
                                          "concept": "concept 15", "misconception": … } ],
                              "return_note": … }
 STUCK           "shows": "problem",
                 "problem": { "type": "stuck", "why": "step_too_big" }
 SIDE_QUESTION   "shows": "turns_away",
                 "turns_away": { "go_now": false, "question": … }
 WANTS_TO_GO     "shows": "turns_away",
                 "turns_away": { "go_now": true,
                                 "new_issue": { "title", "kind", "closes_when",
                                                "why_for_learner" }
                                 or "saved_issue": "I3",
                                 "return_note": … }
 BACK            "still_an_issue": false
 on any leaf     "progress": [ … ]  ·  "tutor_files": [ { "path", "reason" } ]
```

Code builds the allowed values into the answer format each turn, so a wrong value can't be written:

```
 field               its allowed values
 ──────────────────  ────────────────────────────────────────────────────
 still_an_issue      exists only in an issue
 problem.type        unsure · wrong_idea · missing · stuck (stuck only
                     from level 1)
 why                 this level's set only (§9)
 kind                1 – 10
 probe_target        the unticked boxes + the task's concepts
 saved_issue         the saved issue IDs (only if any exist)
 concept             the concept bank's IDs
 turn                the turn numbers of this task
```

Code checks after the answer: `still_an_issue: false` only after "met" this turn · a gap that blocks needs a `return_note` · every `tutor_files` path exists and passes the gates.

### 11.4 The evaluator

```
 IN   (built by code; nothing comes from the orchestrator's own words)
   [instructions]   evaluator.task_box  or  evaluator.closes_when
   [target]         box 2: "found the real error (label unbound)"
                    or issue I1's closing condition:
                    "explains why label is unbound for a guest"
   [answer key]     the answer key of task T3        (task boxes only)
   [learner turns]  turn 12 · learner: "…"           copied word for word
                    turn 13 · learner: "…"

 TOOLS  (as many steps as it needs)
   pull_checkpoints   more turns of this task: what the learner and the tutor
                      said, never the orchestrator's labels
   Read · Grep        in its temporary folder

 ANSWER  (the only format allowed)
   { "target":        "box 2",
     "verdict":       "met" | "not_met" | "unclear",
     "learner_words": "the learner's own words that show it" }   ("" if not met)

 CODE CHECKS
   the target is the one asked · learner_words are the learner's own words,
   word for word, from this task's turns · no other fields
   any failure ──► counted as "unclear"
```

It sees what was said, never what the orchestrator thought, so its verdict stays independent. Its only free text is the learner's own words, and code checks them, so the answer key can't leak.

### 11.5 The tutor: instructions are never history

Every call, code rebuilds the instructions. The only history the tutor carries is what was said and done in this task.

```
 HISTORY   (kept, the whole task)              INSTRUCTIONS   (never kept)
 ───────────────────────────────────────       ──────────────────────────────────
 the learner's messages (+ pasted code)        rebuilt by code every turn,
 the tutor's tool calls                        in the system prompt only
 the results of those tool calls
 the tutor's replies
```

What the tutor receives on turn 4:

```
 SYSTEM  (rebuilt this turn)
   tutor.base: who you are, how you teach
   instructions for this turn: teach_one_concept · experiment_first
     current focus:        issue I1 · a loop variable only exists if the loop ran
     closes when:          they explain why label is unbound for a guest
     wrong idea to watch:  expected label to have a value after a loop that never ran
     files you may read:   concept concept 15
     task sheet:           { … }

 MESSAGES  (everything that happened, in order)
   learner · turn 1     "Reproduced it. Same message every time as a guest…"
   tutor   · turn 1     "Good, you can see it yourself…"
   …
   learner · turn 3     "UnboundLocalError on `label`! …"
   tutor   · turn 3     tool call:   read_concept("concept 15")
   tool result          "concept 15 · loop variables outlive the loop · examples: last([]) …"
   tutor   · turn 3     "That's the real error… What do you predict last([]) returns?"
   learner · turn 4     "None? In JS it would be undefined."            ◄ now

 ANSWER  REPLY: free text to the learner
 NEVER   the orchestrator's answer · the answer key · the graph
```

**One thing is not kept: the tutor's old thinking** (its hidden reasoning before it answers). The newest models check that everything before an old thinking block, system prompt included, is unchanged, and the system prompt changes every turn. The current turn's thinking stays during its own tool calls, which is all the model needs.

The orchestrator and the evaluator already work this way: they start fresh on every call, with nothing from earlier turns except what they pull on purpose (§11.6).

### 11.6 Checkpoints: the history, pulled on demand

Every turn, code stores one checkpoint, signed with the orchestrator's leaf:

```
 ┌─ checkpoint · turn 14 ─────────────────────────────────────────────────
 │ the learner said        "the loop never ran for a guest, so label was never set"
 │ the orchestrator chose  in issue I1 · Question 0 met ──► BACK    ← its sign
 │ the evaluator said      issue I1 met · "the loop never ran for a guest"
 │ the tool calls          orchestrator: evaluate(I1, turn 14) · tutor: none
 │ the tutor replied       "Right. Back to task T3: …"
 │ where we were           stack T3 ▸ I1 · box 2 ticked · stuck level 0
 └────────────────────────────────────────────────────────────────────────
```

By default the orchestrator sees only the newest message and the tutor's last reply. For anything older it pulls:

```
 pull_checkpoints(which) ──► code writes  <temporary folder>/checkpoints_N.md
                         ──► the agent reads it with Read · Grep (that folder only)

 which =   last N turns
         | since an issue (or the task) opened
         | every turn signed with one leaf     (for example GAP)
         | every turn about an issue or a box  (for example issue I1, box 3)
```

Best practices, written in the tool's guide:

```
 to decide …                         pull
 ──────────────────────────────────  ──────────────────────────────────────────────
 still an issue?                     since the issue opened
 a short answer ("yes", "ok")        the last 2 turns: what was it answering?
 a saved issue comes back            every turn about that issue
 stuck: why?                         every turn about the focus, signed STUCK
 the learner says "like before"      every turn signed BACK, or about that issue
```

Different moments need different history, so the orchestrator chooses, guided by these practices. The evaluator pulls the same way, but its copy holds only what the learner and the tutor said.

Read and Grep come built in with the Agent SDK. On the plain Claude API we write them as two small tools limited to the temporary folder.

---

## 12. The tray: every piece we have now

```
── instructions ─────────────────────────────────────────────────────────────

  ORCHESTRATOR                     snapped
  orchestrator.base                ■ always            who you are · how to walk the tree ·
                                                       how to read the task sheet
  orchestrator.on_task             ■ card B
  orchestrator.in_issue            ■ card C
  orchestrator.stuck               ◇ check.stuck       "is a missing piece behind this?"
  orchestrator.saved_waiting       ◇ check.has_saved   "notice if they want a saved issue"
  orchestrator.deep                ◇ check.deep        "are we still serving the task?"

  EVALUATOR
  evaluator.task_box               ■ card B            judge one box, with the answer key
  evaluator.closes_when            ■ card C            judge one issue's closing condition

  TUTOR                            needs (studs)                    used for
  tutor.base                       —                                always
  introduce_task                   task_goal · task_sheet           card A
  keep_goal_in_view                task_goal · task_sheet           on the task
  clarify_goal                     task_goal                        kind 1     NEW
  guided_trace                     current_focus                    kind 2
  teach_one_concept                current_focus · closes_when ·    kind 3
                                   misconception_to_watch
  experiment_first                 current_focus                    kind 3
  plan_approach                    current_focus · task_goal        kind 4     NEW
  guide_fix                        current_focus                    kind 5
  fix_setup                        current_focus                    kind 6     NEW
  guide_debugging                  current_focus                    kind 7
  check_results                    current_focus                    kind 8     NEW
  probe_understanding              probe_target                     kind 9 · UNCERTAIN
  encourage_pause                  —                                kind 10    NEW
  answer_side_question             side_question                    SIDE_QUESTION, 1 turn
  bridge_back                      return_to                        after BACK
  close_task                       task_sheet · journey_so_far      card E
  reframe_explanation              current_focus                    stuck level 1
  ask_their_view                   current_focus                    stuck level 1   NEW
  smaller_step                     current_focus                    stuck level 2   NEW
  point_to_place                   current_focus                    stuck level 2   NEW
  worked_example                   current_focus                    stuck level 3   NEW
  offer_choices                    current_focus                    stuck level 3   NEW
```

```
── facts: values code copies from the graph ("state") ──────────────────────

  task_goal                  task T3 · guests must get a real answer
  task_sheet                 the task sheet (§10): the job box, each concept with
                             its boxes, checked, difficulties
  next_box                   box 3 · the first unticked box in the suggested order
  stack                      T3 ▸ I1 ▸ I2
  current_focus              issue I2 · why the loop runs 0 times for a guest
  return_to                  "you get last([]); now connect it to label"
  closes_when                explains why label is unbound for a guest
  misconception_to_watch     expected label to have a value after an empty loop
  recent_progress            ✓ found the except on line 821 · ✓ ran last([])
  stuck_level                1
  saved_issues               issue I3 · how does the test fake OpenAI?
  probe_target               box 4 · explains what the label decides
  side_question              how does the test fake OpenAI?
  journey_so_far             the story lines of this task
```

```
── files: what an agent may read (each through its read tool) ───────────────

  concept file               one concept of the bank        read_concept
  repository file            the learner's code             read_file(path, around) · search_repo
  journey                    a past task's story            read_journey
  task sheet (JSON)          this task's, or archived       Read · Grep
  answer key                 LOCKED                         the evaluator only · never the tutor
```

```
── tools ────────────────────────────────────────────────────────────────────

  read_concept · read_file · search_repo · read_journey        reading
  evaluate(target, turns)    the orchestrator only. Code runs the evaluator and
                             returns its verdict as the tool result. turns = which
                             learner turns to judge; code copies them word for
                             word. As many calls as needed.
  pull_checkpoints(which)    the orchestrator and the evaluator. Code writes the
                             chosen checkpoints (§11.6) into the agent's temporary
                             folder and returns the file's path.
  Read · Grep                primitive tools, in that temporary folder only
  write_journey              the tutor only, at close
```

```
── leaves: the ends of the question tree ────────────────────────────────────

  ORCHESTRATOR   every leaf may also carry "progress" (what the learner showed)
  ON_TRACK        kind
  UNCERTAIN       probe_target
  WRONG_IDEA      what_went_wrong · learner_words · concept (optional)        NEW
  GAP             the gaps: title · kind · blocks · closes_when · why_for_learner ·
                  concept (optional) · misconception (optional)
                  return_note (for the step we leave, if a gap blocks)
  STUCK           why (one of this level's set, §9)
  SIDE_QUESTION   the question
  WANTS_TO_GO     a new issue (title · kind · closes_when · why_for_learner)
                  or a saved issue · return_note
  BACK            still_an_issue = false (allowed only after the evaluator's "met")

  EVALUATOR      VERDICT { target, met | not_met | unclear, learner_words }
  TUTOR          REPLY: free text to the learner
```

```
── effects: what code does to the graph (each also writes its story line) ───

  record_progress            evidence rows · "✓ Did …"
  check_box                  ☑ forever in this task · records the turn · checks the
                             concept when all its boxes are ☑ · "☑ …"
  record_difficulty          a WRONG_IDEA or a GAP about a concept goes into the task
                             sheet · a checked concept goes back to unchecked, with a
                             had_it_then_missed entry
  open_issue                 a new issue · the step we leave keeps its return note ·
                             one level deeper
  save_issue                 saved for later · "○ Saved for later …"
  back_one_step              "★ Cleared — …" or "✕ Already knew it — …" · one step back
  remember_piece             each focus remembers its last tutor piece (used after BACK)
  raise_stuck_level ·        the no-progress counter for this focus (§9); WRONG_IDEA
  reset_stuck_level          counts as no progress
  create_task_sheet          a fresh sheet when a task opens
  archive_task_sheet         when the task closes, with the raw discoveries
  close_task                 "★ Done — …" · next task
```

```
── checks: yes/no questions code asks the graph ─────────────────────────────

  task_just_opened           no learner message yet in this task
  on_task                    the stack holds only the task
  in_issue                   the stack holds the task and at least one issue
  has_unticked_box           an unticked box exists (any of them can be judged)
  has_saved                  a saved issue exists (this task, or carried)
  evaluator_met              the evaluator said met this turn
  task_done                  the job box ☑ and every concept checked
  stuck                      no progress for N turns on this focus (§9)
  deep                       the stack is 4 or more levels deep
```

---

## 13. Before learners: the crafting line

```
   repository ──► prepare (code) ──► CONCEPT CRAFTER ──► check ──► TASK CRAFTER ──► check ──► LADDER (code)
                                                                        │
                                         NEW: writes for every task ────┘  the job box, then each concept
                                                                           with its boxes: box 1 … box N,
                                                                           in a suggested order,
                                                                           each box with its concepts
                                                                           the answer key (locked)
```

```
┌─ PLATE · TASK CRAFTER        Agent SDK · once per codebase · before any learner
│ instructions   ■ crafter.tasks
│ files          □ the repository (Read · Glob · Grep)    □ the concept files
│ tools          ■ list_concepts  ■ read_concept  ■ write_task
│ answer         TASK { goal · tier · files · the job box ·
│                       concepts, each with its boxes (box 1 … box N, in a
│                       suggested order) · answer key (locked) }
└──────────────────────────────────────────────────────────────────────────
```

---

## 14. Old names → new names

`BACKEND_SPEC.md` still uses the old names. When we update it:

```
   BACKEND_SPEC            this file
   ──────────────────────  ────────────────────────────────────────────────────────────
   continue                ON_TRACK (carries progress)
   start_detour            GAP that blocks · WANTS_TO_GO
   return_from_detour      BACK (Question 0) ──► card D
   verify_learning         UNCERTAIN ──► one probe · and the boxes
   change_approach         STUCK: code sets the level, the orchestrator picks why
   complete_task           DONE: code, when all boxes are ☑ ──► card E
   park_task               removed: there are no long pauses
   side questions          SIDE_QUESTION · or WANTS_TO_GO
   decision menu           the question tree: a branch that can't exist isn't in it
   template names          the orchestrator only names leaf + kind + why;
                           code snaps the pieces
   position pieces         orchestrator pieces snapped by the card and the checks
   state_keys              studs: each tutor piece brings its facts
   tutor_kit               the instructions for this turn, in the tutor's system
                           prompt, rebuilt every turn (§11.5)
   known_concepts          the task sheet: "checked"
   pending_discoveries     raw entries code writes when the task closes
   answer-key gate         dropped: the answer is never revealed;
                           only the evaluator holds the key
```

---

## 15. The gold patterns

These rules made the design. They work anywhere an LLM has to choose inside a system.

```
  1  ZONE + BRANCH            code reads the state and picks the zone;
                              the LLM only picks a branch inside it
  2  NESTED TREE              one small question per level; a branch exists only
                              under its parent and its condition
  3  ANSWER FORMAT PER TURN   code builds the answer format from the tree each
                              turn, so an impossible answer can't be written
  4  CATEGORIZE, DON'T        the LLM names a label (each with a short description);
     COMPOSE                  code maps the label to prepared pieces from config
  5  STUDS                    a piece declares the facts it needs; code fills them
  6  CODE CARRIES EVERY       agents never talk directly; code checks every handoff
     MESSAGE
  7  NARROW JUDGE             a small agent with ONE target holds the secret,
                              returns only a verdict + the learner's words, and
                              never sees the boss's opinion
  8  QUOTE, DON'T PARAPHRASE  evidence is the learner's own words; code checks
                              they are really there
  9  ESCALATION LADDER        code counts; the level unlocks a set; the LLM picks
                              within the set
 10  STACK WITH RETURN NOTES  leaving writes a note; ending goes back ONE step
 11  FRESH AGENTS, MEMORY     no agent remembers anything; the graph does
     IN THE GRAPH
 12  EFFECTS ARE CODE         every LLM answer becomes graph changes + story lines
                              through code, in one step
 13  KNOWLEDGE BY ROLE        the boss sees most, the judge least, the voice only
                              what it needs
 14  PULL, DON'T PUSH         a small default context; the agent pulls more through
                              a scoped tool into a temporary file, then searches it
 15  WRITE AT THE SOURCE      the agent that sees a fact names it in its answer;
                              code stores it at once; no agent re-reads the past
                              just to take notes
 16  NO ABBREVIATIONS         every name is a full phrase; every ID comes with its
                              name
 17  INSTRUCTIONS ARE NEVER   every call, code rebuilds the instructions from the
     HISTORY                  graph; an agent's history holds only what was said
                              and done
```

---

## 16. Decided · my proposals · still open

```
 DECIDED (you)
   ✓ code picks the card; an LLM only walks its question tree
   ✓ two axes: WHERE (code, from the graph) × STATE (the learner, spec §4)
   ✓ the branches are nested: each one exists only under its loop and condition
   ✓ the orchestrator only CATEGORIZES (leaf + kind + why); each option has a
     short description; it never reads the tutor's instructions; code snaps
     the pieces we planned
   ✓ in an issue the first question is always "still an issue?"
   ✓ any issue ends ──► back ONE step (to the issue above, or the task)
   ✓ progress can ride on any leaf
   ✓ a side question is just a side question: answer briefly, save it
   ✓ task → concepts → boxes, plus one box for the job itself; a concept is
     checked when all its boxes are ☑; the task is done when the job box is ☑
     and every concept is checked
   ✓ the boxes have a suggested order, but can be ticked in any order; the
     sheet records the turn of each tick
   ✓ the learner sees the boxes (frontend later)
   ✓ "checked" goes back to false after a WRONG_IDEA or a GAP about the
     concept; had_it_then_missed keeps when, which issue, and the angle
   ✓ the orchestrator calls the evaluator · only the evaluator sees the answer key
   ✓ the orchestrator knows more than the evaluator
   ✓ the orchestrator writes closing conditions · the evaluator judges them
   ✓ the answer is NEVER revealed, at any stuck level
   ✓ stuck: each level has its own prepared set (§9); the orchestrator picks
     why; more guidance as the level rises
   ✓ every turn is a checkpoint, signed with the orchestrator's leaf; agents
     pull older ones on demand into a temporary file and read it with Read · Grep
   ✓ the evaluator is a small agent: as many steps as it needs, its own tools,
     and never the orchestrator's labels
   ✓ a broken orchestrator answer: try once more; if still broken, nothing
     changes, the tutor answers with the pieces it already has, it is logged
   ✓ primitive tools: Read + Grep only; more later, as custom tools or the
     Agent SDK's own tools
   ✓ NO recorder: code writes the task sheet at once, from the evaluator's
     verdicts and the orchestrator's leaves (§10)
   ✓ a new leaf, WRONG_IDEA: a wrong idea about the current work, with what
     went wrong and the learner's own words; it counts as no progress
   ✓ one task sheet per task per learner, JSON, written by code only; archived
     when the task closes; the next task starts a fresh one
   ✓ the tutor always gets the task sheet of its task
   ✓ no stop button: card F, PARK and RESUME are removed (no long pauses)
   ✓ no abbreviations, anywhere
   ✓ instructions are never history: code rebuilds every agent's instructions on
     every call; the tutor's history keeps everything said and done (the
     learner's messages, its tool calls and their results, its replies); old
     thinking is not sent back (§11.5)
   ✓ "kit" is renamed "instructions for this turn"
   ✓ a new task's sheet is always fresh: nothing is carried over from earlier
     tasks
   ✓ concepts are named "concept 15", never "concept 15"

 MY PROPOSALS (say no to any)
   · the evaluator reads the learner turns the orchestrator points to, copied
     word for word by code
   · "I already know this" is checked by the evaluator, not believed; code labels
     it "already knew it" when met on the issue's first turn
   · the question tree in §3
   · the contracts in §11

 STILL OPEN (you)
   · the NEW tutor pieces (§12): write them now, or during the build?

 HOLES FOUND WITH THE WALKTHROUGH
   "checked"
   hole 1   closed: every box sits under one concept; checked = all its boxes ☑
   hole 2   closed: a box belongs to exactly one concept
   hole 3   closed: every concept has at least one box
   hole 4   the link from an issue to a concept is the orchestrator's guess
   hole 5   closed: checked goes back to false; had_it_then_missed keeps the angle
   "the learner's words are really in that turn"
   hole 6   an exact match is fragile (one changed space or quote mark)
   hole 7   it proves the words exist, not that they prove the box
   hole 8   proof spread over two turns needs more than one quote
   hole 9   when the proof is pasted code, the "words" are code
   "kind"
   hole 10  one field, two meanings: what the learner does (ON_TRACK),
            what is missing (GAP)
   hole 11  a turn can mix kinds, but only one piece is snapped
   hole 12  the kind can flip every turn, and the tutor's instructions with it
   hole 13  overlaps: kind 9 with UNCERTAIN, kind 10 with the stuck ladder
   hole 14  "kind": 7 is a code number; "kind_of_work": "debugging" is clearer
   from the walkthrough page
   hole 15  closed: a wrong answer is the WRONG_IDEA leaf (no progress)
   hole 16  a box explained inside an issue is ticked only on the next turn
   hole 17  closed: no recorder; code counts at once
```
