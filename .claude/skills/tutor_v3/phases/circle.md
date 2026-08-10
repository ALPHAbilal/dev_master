# BIG BUILD — the nine build-verbs

Every example is *drawn from the learner's own scanned codebase at run time*, never
baked in here.

## The governing law (applies to every phase)

**LAW 0** — pose the **question first**, explain only the **residue** he cannot
reach, never exceed ~20% talk. Budget per session: **20% explain / 60% he produces
(code AND reasoning) / 20% review.** And LAW 0.6: **proximity** — only what is
relevant to the target he is building; never a verb run to look thorough.

## The shape of a session

    INTAKE (once) ──► pick the next TARGET SLICE ──► run it through the CIRCLE
    ──► record which verbs passed/failed ──► next slice.

- A **SLICE** is one real sub-task of the target — a whole script, or one loop
  inside it. Chosen by proximity: the next thing needed to move the build forward.
- The **CIRCLE** is the nine verbs below. Not all fire every slice: REASON and
  DESIGN skip when the slice is trivial, and the DB records the skip so the
  circle-map stays honest.
- Concepts are taught **just-in-time** the moment IMPLEMENT trips on one, using the
  intact probe→teach→gate machinery as a subsystem of verb ⑤.

**How every "example" below works:** the tutor takes the shape described and finds
its instance *in the learner's real scanned code*, then asks about that. No toy
data; no assumption about what the codebase contains.

---

## ① UNDERSTAND
**Purpose.** Turn a vague task into a stated one: restate it, surface the
constraints, edge cases, and hidden assumptions — before any plan.
**Learner produces.** In his words: inputs, outputs, and the constraints he sees.
**Pass-test.** After he answers, the agent lists the real load-bearing
constraints. He passes if he caught the ones that would change the code. One only
the agent found = MISS on `understand`, recorded with the constraint.
**Example shape (from the scanned code).** Find a place where the code guards a
non-obvious failure — a silent error, a truncation, an ordering assumption — and
ask: *"what could go wrong here that the program would not tell you about?"* If he
cannot name the guarded failure, that is the gap this verb exists to catch.
**DB.** `probe <slice> UNDERSTAND understand HIT|MISS`, error = the missed
constraint.

## ② DECOMPOSE
**Purpose.** Break the slice into ordered steps he could each implement. The verb
he named as his own freeze.
**Learner produces.** A numbered plan in plain english or comments — no code.
**Pass-test.** (a) every requirement from ① maps to ≥1 step; (b) no step is a leap
he cannot expand — a step he can't break down is itself a new slice to recurse on.
**This plan is the answer key:** IMPLEMENT (⑤) is graded against it. This is how
v3 keeps rigor without a fixed target file.
**DB.** `probe <slice> DECOMPOSE decompose HIT|MISS`; store the plan via `attempt
snap`.

## ③ REASON
**Purpose.** When more than one approach is viable, choose deliberately.
**Learner produces.** ≥2 named options, compared on ≥1 real axis (memory / speed /
robustness / simplicity / cost), and a pick with a *because*.
**Skip rule.** One sane way → he says so, recorded `skipped`, not forced.
**Example shape.** Find a decision the real code made where an alternative existed
(read-all vs stream, sync vs async, retry vs fail) and ask which the constraints
force, and why.
**DB.** faculty `reason`. Pass = options + axis + a because, not the "right" pick.

## ④ DESIGN
**Purpose.** For anything with structure: data shapes, interfaces, where state
lives, the contracts between parts.
**Learner produces.** A drawing of data in→out and the named contracts (ASCII).
**Skip rule.** Trivial slices skip, recorded.
**Example shape.** Find a data transformation or a load-order/interface contract in
the code and ask: *"draw one item going in and coming out — what stays identical,
what changes, and what breaks if the contract is ignored?"*
**DB.** faculty `design`. This is where parked `arch`/`api` concepts return JIT.

## ⑤ IMPLEMENT
**Purpose.** Write the slice by hand, from his own plan, from an empty file.
**Learner produces.** Running code.
**Pass-test.** Runs, and its behavior matches **his DECOMPOSE plan** and the
UNDERSTAND contract; `attempt snap` + diff + `--copy-checked`.
**JIT concepts.** The instant he trips on a concept he does not own, the concept
subsystem fires for that one concept: probe → (miss) → teach at the floor → gate →
transfer. The ladder is demand-paged, not climbed.
**DB.** faculty `implement`.

## ⑥ DEBUG
**Purpose.** *hypothesis → experiment → evidence → diagnosis → fix → verify*, not
*error → google → paste*. On **his own** code.
**Learner produces.** The chain, out loud, in order — a hypothesis stated *before*
he changes anything.
**Pass-test.** Falsifiable hypothesis first; evidence gathered; the fix follows
the evidence, not shotgun edits; he verifies. Editing before a hypothesis is the
MISS.
**Example shape.** Feed his working code a breaking input — a missing key, a blank
line, an oversized record — and ask, before he touches it: *"what do you think
happened, and what would prove it?"*
**DB.** faculty `debug`; pulls parked `failure` concepts JIT.

## ⑦ EVALUATE
**Purpose.** He sees the problem in his own code *first*.
**Learner produces.** Round-zero self-review: the failure modes HIS code cannot
survive, before the agent lists any.
**Pass-test.** He names ≥ (agent's count − 1) of the real findings. A finding only
the agent sees is a **floor** → recurse via DECOMPOSE/teach. Then normal studio
rounds run on the diff.
**Example shape.** After a happy-path pass, prompt the self-review: *missing input?
malformed record? absent directory? empty file? partial failure midway?* — drawn
from what this slice actually touches.
**DB.** faculty `evaluate`; the `reviews` table, with a round-0 authored by him.

## ⑧ COMMUNICATE
**Purpose.** Explain the decision to another engineer; write the commit /
docstring. Doubles as interview rehearsal.
**Learner produces.** A 3-sentence explanation of one real decision, and a commit
message or docstring for the slice.
**Pass-test.** The explanation names the load-bearing *why* and would let another
engineer act on it — graded on the reason, not eloquence. The *what* without the
*why* is the MISS.
**DB.** faculty `communicate`; feeds a future `interview` mode.

## ⑨ IMPROVE
**Purpose.** Close the loop: fix on evidence, iterate, retire false beliefs.
**Learner produces.** Fixes for ⑥/⑦ findings; a re-snap; and, where a misconception
drove the miss, production that no longer exhibits it.
**Pass-test.** A finding surviving round 2 is a **floor**, not a slip → descend. A
misconception is retired only on an artifact that doesn't show it. Then advance to
the next slice.
**DB.** `misconceptions` + `reviews` round 2; ladder_log the floors found.

---

## THE CIRCLE-MAP (furniture, never pasted)

`tree`/`PROGRESS.md` gains a header — the target name comes from the DB, so it is
whatever the learner set at intake:

    TARGET: <name from targets table>   slice k/~N: <current slice>
    UNDERSTAND ▓▓▓░  DECOMPOSE ▓░░░  REASON ░░░░  DESIGN ░░░░
    IMPLEMENT  ▓▓▓▓  DEBUG     ▓░░░  EVALUATE ▓░░  COMMUNICATE ░░░░
                                            ▲ his journey, all nine verbs

One glance says which faculty of the whole engineer is starving.

## PHASE / VERB / DB SUMMARY

| # | verb | faculty | pass-test in one line | JIT pulls |
|---|---|---|---|---|
| ① | UNDERSTAND | understand | caught the load-bearing constraints | — |
| ② | DECOMPOSE | decompose | every requirement → a step; plan = answer key | — |
| ③ | REASON | reason | ≥2 options, an axis, a because | pattern |
| ④ | DESIGN | design | drew data in→out + named the contract | arch, api |
| ⑤ | IMPLEMENT | implement | runs, matches his plan, copy-checked | language, stdlib |
| ⑥ | DEBUG | debug | hypothesis before edit; fix follows evidence | failure |
| ⑦ | EVALUATE | evaluate | found his own failure modes first | — |
| ⑧ | COMMUNICATE | communicate | explanation names the why, transferable | — |
| ⑨ | IMPROVE | (cross) | round-2 survivors = floors; misconceptions retired | — |
