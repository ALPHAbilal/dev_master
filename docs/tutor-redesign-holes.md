# Tutor Redesign — Detected Holes Log

A running log of holes found in the current tutor system and the direction to fix
each. Append as new holes surface. Newest at the bottom.

Status legend: `OPEN` (identified, not fixed) · `PLANNED` (fix agreed) · `DONE`.

---

## H1 — Direct DB contact via Bash/CLI commands
**Status:** PLANNED

**The hole.** Every tutor state change today goes through `tutor_db.py` invoked as a
Bash shell command (e.g. `python3 .claude/tutor/tutor_db.py phase --set BUILD`,
`classify ...`, `draft ...`, `probe ...`). The AI reaches the database by typing
CLI commands. This is fragile for two reasons:

- The AI has to *remember a documented command exists* to use it — the mechanism
  lives in prose (SKILL.md, help text), not in anything the model sees every turn.
  A forgotten command means the state silently never changes.
- It couples the pedagogy to a shell + a CLI arg parser + a specific file path,
  and makes the interaction invisible/untestable as a first-class action.

**The fix — function-tool mindset.** Replace direct DB/CLI contact with **tools**
(function tools always present in the model's tool schema). The AI changes state by
calling a tool, not by shelling out. Rationale (from studying `qm`, `harness/goal.ts`):

- A tool sits in the model's tool list *every turn* — the model does not "forget" a
  tool the way it forgets a CLI command.
- Pair it with a **per-turn steering note** that re-injects the current state and how
  to change it, so the affordance travels with the context (qm's `goalSteeringNote`).
- Enforcement stays server-side: the tool validates/refuses exactly like the CLI
  refuses today; the model proposes, the tool disposes.

**Scope.** All of: `phase`, `classify`, `draft`, `show`, `probe`, `gate`, `attempt`,
`promote`, `pass`, `push`, `review`. The whole `tutor_db.py` subcommand surface
becomes a tool surface.

---

## H2 — Phase change is unenforced prose (sub-case of H1, called out separately)
**Status:** OPEN

**The hole.** `meta.phase` is the single source of truth for which phase we are in,
and it is only ever written by the AI running `tutor_db.py phase --set <P>`. Unlike
the *phase file read* (which the `phase-gate` hook walls), phase *changing* has NO
guard: no hook, no injected reminder, no wall. If the AI forgets the command, the row
stays stale and every turn injects the wrong phase's context. Also `tutor_db.py:2462`
auto-writes `phase='BUILD'` inside another command, so "one learner choice, four times
ever" is not strictly true — a code path moves it too.

**The fix.** Fold into H1's tool + steering-note model: the phase block injected each
turn states the current phase, since when, and the tool to change it. Audit that the
learner actually asked before a phase move. Remove/So surface the hidden auto-write.

---

# Design Decisions (foundational — not holes, but the target the redesign builds toward)

## D1 — Two-agent topology: Agent M (planner) + Agent L (teacher), library of maps
**Status:** DECIDED

- **Agent L** — the only agent that talks to the learner. Drives the live session,
  asks, judges, explains. Reads the map library; never writes it.
- **Agent M** — never talks to the learner. Builds and iteratively rewrites the
  **map library**: a folder tree of many named `.md` files (not one file), organized
  by aspect and by subgoal so both learner and agents can navigate it. Has a
  **research tool**. Consumes the learner's recorded mistakes from the DB, plans the
  next trajectory.
- **Handoff is one-directional through the library:** M writes maps → L reads maps.
  L's observations reach M only through the DB (recorded mistakes/evidence), never by
  writing maps back.
- **Stage 0 SCAN runs once** (result persists in DB, never repeats). **Stage 1** spawns
  a capped set of coverage subagents, each expert in one aspect of the stack, together
  covering all of it. **Stage 2** is the live M‖L loop until the DB is exhausted.

## D2 — Six sources of learning (not mistakes only); M sorts productive vs noise
**Status:** DECIDED

Learning is NOT mistakes-only. Six sources on the path A→B:
1. Error made & fixed (the richest) — L stays silent, he finds it.
2. Productive struggle (the reach strengthens memory even when he ends up right).
3. A genuine fork/judgment (no wrong answer) — L asks him to choose + defend (REASON).
4. Surprise/calibration (reality ≠ prediction) — the perturb rung.
5. Leveling up working code (it runs; there's a sharper way) — L reviews (IMPROVE).
6. Things to be TOLD (API names, conventions, one right answer) — L just explains (~20%).

**Agent M's core job is SORTING, not maximizing mistakes:** per subgoal decide
`worth failing at` (design flaws, wrong models, missed edges → let him hit it, L quiet)
vs `not worth failing at` (syntax, names, conventions → L just tells him). Manufacturing
mistakes in lane 6 (fumbling an import) teaches nothing — that is noise, the enemy.

## D3 — Learning-theory layer: every subgoal ends in a stored MENTAL MAPPING
**Status:** DECIDED

From Colin Galen's intuition model (`transcript_unlocking-your-intuition.md`).
Intuition = fast-brain pattern match ("what has worked before, will it work here?"),
built from stored **mental mappings** = `problem components → solution ideas`. More
mappings → stronger intuition → the confidence to build the whole codebase solo
(= the SOLO endpoint). Mistakes matter because each corrected one deposits a mapping
AND points at the missing association — but the mapping is the goal, not the mistake.

Three ROADS, all ending at "create mental mapping":
- **Slow solving** — solve fully + prove. Deep understanding, trains reasoning.
- **Fast mapping** — just read the solution, absorb the association. No mistake.
- **Intuition training** — guess the high-level idea → check → if wrong, prove/solve
  fully. This is the mistake road; ≈ the READ phase (predict → verify).

**Split across the two agents:**
- **Agent M owns the roads** — picks which road each subgoal takes, and picks problems
  "a bit too hard" (easy problems teach nothing). This IS M's productive-mistake
  engineering.
- **Agent L owns the mapping** — walks the road live, forces the JUSTIFY step (catch
  wrong intuitions), and writes the mental mapping into the library — including not
  just the answer but the thought-provoking questions, simplifications, and "how to
  come up with it."

**Caution (Galen's own):** cannot route everything through fast/intuition roads. If
intuition outruns reasoning the learner is "lost all the time." M must force enough
slow-solving (BUILD/SOLO, full effort, prove it) that reasoning keeps pace with
pattern-recognition.

## D4 — Sequencing model: prerequisite DAG + mastery overlay; plan one step, re-score
**Status:** DECIDED

M plans over ONE structure with TWO operations.

**Structure — a prerequisite DAG + a live mastery overlay.** Each concept is in one
of three states:
- `OWNED`  — passed all 4 rungs.
- `READY`  — every prerequisite OWNED, but this one isn't yet. **The READY set = the
  frontier.**
- `LOCKED` — at least one prerequisite still missing.

**Where the DAG comes from.** SCAN emits only a ROUGH order (roughly: what appears
later / builds on more = further out; the last-reached thing is called the frontier).
It does NOT need to get prerequisite edges right. **Agent M refines the real edges
over time**, using its **research tool** (docs, Wikipedia) to verify "does X actually
sit under Y / what is the edge." Cheap draft from SCAN, corrected continuously by M.

**Op 1 — "where to start" = find the frontier (the READY set).**
- Warm (has history): READY set is already computed from the overlay.
- Cold start (no learner evidence): M does NOT teach first — it CALIBRATES. Ask L to
  run predict-only probes walking DOWN the DAG from the target until OWNED stops and
  LOCKED begins. That locates the frontier. Then the real loop begins.

**Op 2 — "what next" = score the READY set, pick one.**
```
  score(readyNode) = w1·PROXIMITY   (distance to the target slice he's building)
                   + w2·ZPD_FIT     (is it "a bit too hard"? — see D5)
                   + w3·MAPPING_GAP (fills a mapping he lacks / hits a weak association)
                   + w4·ROAD_BALANCE(penalize the same road 3x in a row — D3 caution)
```

**Principle — one step, then observe. Never plan the whole tree.** M plans ONE
subgoal, L runs it, the mistake evidence updates the overlay, M re-scores from the new
state. Like a chess engine picking the best move for the current board, not scripting
40 moves. The research tool is for evaluating the CURRENT frontier well, not for
pre-planning.

**Build implication for SCAN output (per concept):** rough order + aspect tag
(lang/stdlib/design/…) + distance-to-target-slices + difficulty estimate. The
prerequisite edges start rough and M sharpens them.

## D5 — ZPD model: forward estimate, backward confirmation, calibrated on performance
**Status:** DECIDED

ZPD = the difficulty sweet spot: not too easy (no mistake, no learning), not too hard
(freezes, gets carried — teaches nothing), but the band where he can't do it alone yet
but CAN self-correct (maybe with one nudge). That struggle-then-recover is where the
mapping burns in. `ZPD_FIT` = M's estimate that a candidate task lands in that band for
THIS learner RIGHT NOW.

M can't know P(self-correct) before he tries, so it estimates forward then corrects
backward:

**Forward estimate (before the task) — two cheap signals:**
1. New-pieces-on-owned: count NEW pieces resting on already-OWNED pieces. 1–2 new on
   solid ground = sweet spot. 0 new = too easy. Many new / shaky prereq = too hard.
2. Recent self-correction trend: catching his own mistakes lately → push harder;
   getting crushed or carried → ease off.

**Backward confirmation (after the task) — the real ZPD meter = pushes-per-task:**
```
  0 pushes, no mistake        → TOO EASY   (raise difficulty)
  1–2 pushes, self-corrected  → PERFECT ZPD (sizing was right)
  4 pushes (cap), carried     → TOO HARD    (shrink the gap, insert a smaller subgoal)
```

**THE SECRET SAUCE — everything calibrates on the learner's actual performance.**
Every task M assigns is also a MEASUREMENT of whether M sized it right. M reads the
outcome (pushes-per-task, self-correction rate, which prereq turned out shaky) and
re-sizes the next task from it. Nothing is fixed or scripted; the difficulty, the road
choice (D3), and the prerequisite edges (D4) all self-tune to the individual learner
turn after turn. The health metric (from the PUSH design): **pushes-per-task trending
down while difficulty holds or rises** = he is getting stronger at the same edge = he
can build more of it himself, with confidence (the SOLO endpoint).

---
