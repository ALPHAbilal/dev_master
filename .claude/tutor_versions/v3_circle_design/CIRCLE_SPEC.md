# THE CIRCLE — full phase specification (v3)

The complete definition of the AI tutor's phases. Companion to `DESIGN.md`.
Grounded in the real anchor target: the `soufiane_prompts/prompts/` scripts (an
LLM batch pipeline). Nothing here is implemented yet.

## The governing law (applies to every phase)

**LAW 0** — the agent poses the **question first**, explains only the **residue**
the learner cannot reach, and never exceeds ~20% talk. Budget per session:
**20% explain / 60% he produces (code AND reasoning) / 20% review.** Source:
`knowledge.md` 23, 373-390, 440.

## The shape of a session

    INTAKE (session 1 only) ──► pick the next TARGET SLICE ──► run it through
    the CIRCLE ──► record which verbs passed/failed ──► next slice.

- **INTAKE** captures the anchor as DATA (see DESIGN "RADICAL SPINE"). The process
  is agnostic to what the target is.
- A **SLICE** is one real sub-task of the target (e.g. "write
  `build_translation_sources.py`", or just "the record-reshape loop inside it").
- The **CIRCLE** is the nine verbs below. Not all fire every slice: REASON and
  DESIGN skip when the slice is trivial, and the DB records the skip so the
  circle-map shows honest coverage, never a faked one.
- Concepts (v2's ladder) are no longer climbed up front. They are taught
  **just-in-time** the moment IMPLEMENT trips on one — using v2's intact
  probe→teach→gate machinery, as a subsystem of verb ⑤.

---

## ① UNDERSTAND

**Purpose.** Turn a vague task into a stated one: restate it, surface the
constraints, edge cases, and hidden assumptions — *before* any plan.

**Learner produces.** In his own words: what goes in, what comes out, and a list
of the constraints/edge-cases he can see.

**Pass-test (mechanical).** After he answers, the agent lists the *real*
load-bearing constraints. He passes if he caught the ones that would change the
code. A constraint only the agent found is a **MISS on `understand`** and is
recorded with the constraint as the "error".

**Grounded example.** `run_translation.py` raises max tokens to 4500 *"because the
longest records translate to slightly over 3000 and would otherwise be cut off
SILENTLY — OpenAI reports a truncated answer as a success."* Question to him:
*"what could go wrong that the program would not tell you about?"* If he never
names silent truncation, that is the exact gap UNDERSTAND exists to catch.

**DB.** `probe <slice> UNDERSTAND understand HIT|MISS`, error = the missed
constraint. New faculty `understand` (folds v2's `read`).

---

## ② DECOMPOSE

**Purpose.** Break the slice into ordered steps he could each implement. This is
the verb he named as his own freeze (2026-08-09).

**Learner produces.** A numbered plan in plain english or comments — **no code.**

**Pass-test.** Two mechanical checks: (a) every requirement from ① maps to at
least one step; (b) no step is a leap he cannot himself expand — a step he can't
break down further *is itself a new slice to recurse on*, not a failure to hide.

**This plan is the answer key.** IMPLEMENT (⑤) is graded against it, which is how
v3 keeps rigor without a fixed target file.

**Grounded example.** `build_translation_sources.py` decomposes to: [1] list the
(french-output → translation-source) file pairs; [2] for each file, stream records;
[3] per record: pop `response`, read `job_name`, build `prompt = "Job title:
<title>\n\n<french>"`; [4] write out as a top-level JSON array mirroring the path;
[5] make the dst directory if missing. If his plan omits [5], EVALUATE will later
break on a missing directory — and we will trace it back to this omission.

**DB.** `probe <slice> DECOMPOSE decompose HIT|MISS`; store the plan text as the
attempt artifact (`attempt snap`).

---

## ③ REASON

**Purpose.** When more than one approach is viable, choose deliberately.

**Learner produces.** ≥2 named options, compared on ≥1 real axis
(memory / speed / robustness / simplicity / cost), and a pick with a *because*.

**Skip rule.** If there is genuinely one sane way, he says so and the phase is
recorded `skipped` — not faked, not forced.

**Grounded example.** Reading the source file: `json.load(whole_file)` vs streaming
line-by-line. The real code streams — axis: memory, because these files hold
millions of records. Question: *"you have two ways to read this. what does each
cost, and which does the size of the data force?"*

**DB.** faculty `reason`. Pass = presence of options + axis + a because, not the
"correctness" of the pick.

---

## ④ DESIGN

**Purpose.** For anything with structure: the data shapes, the interfaces, where
state lives, the contracts between parts.

**Learner produces.** A drawing of data in→out and the named contracts. ASCII,
per the DRAW-IT rule.

**Skip rule.** Trivial slices skip, recorded.

**Grounded example.** The record contract: `{type, job_id, …, response:"<fr>"}` →
`{type, job_id, …, prompt:"Job title:…"}` — *ids are copied by the pipeline and
never sent to the model.* And the load-order contract in `run_translation.py`:
env vars **must** be set before `import run_prompts`, because the module reads them
at import. Missing that contract = a bug that runs and silently does the wrong
thing. Question: *"draw what one record looks like going in and coming out — what
must stay identical, what changes?"*

**DB.** faculty `design` (currently NEVER TESTED). This is where `arch`(8) and
`api`(11) parked concepts get pulled in JIT.

---

## ⑤ IMPLEMENT  (= v2, intact)

**Purpose.** Write the slice by hand, from his own plan, from an empty file.

**Learner produces.** Running code.

**Pass-test.** Runs, and its behaviour matches **his DECOMPOSE plan** and the
UNDERSTAND contract; `attempt snap` + diff + `--copy-checked` all as in v2.

**JIT concepts.** The instant he trips on a language/stdlib concept he doesn't own
(`json.loads`, `dict.pop`, `pathlib`, a generator), the v2 subsystem fires for
*that one concept*: probe → (miss) → teach at the floor → gate → transfer. The
concept ladder is now demand-paged, not climbed.

**DB.** faculty `implement` (alias of v2 `write`); everything v2 already records.

---

## ⑥ DEBUG

**Purpose.** `knowledge.md:255` — *hypothesis → experiment → evidence → diagnosis
→ fix → verify*, not *error → google → paste*. On **his own** code.

**Learner produces.** The chain, out loud, in order — a hypothesis stated *before*
he changes anything.

**Pass-test.** He states a falsifiable hypothesis first; gathers evidence; the fix
follows the evidence rather than shotgun edits; he verifies. Changing code before
stating a hypothesis is the MISS this phase measures.

**Grounded example.** Agent feeds `build_translation_sources` a record with no
`response` key → `KeyError`. Or a blank line. Or a record that translates to >4500
tokens. Question: *"it crashed. before you touch it — what do you think happened,
and what would prove it?"*

**DB.** faculty `debug`; pulls `failure`(13) parked concepts JIT.

---

## ⑦ EVALUATE

**Purpose.** He sees the problem in his own code *first* — `knowledge.md:239`.

**Learner produces.** Round-zero self-review: the failure modes HIS code can't
survive, before the agent lists any.

**Pass-test.** He names ≥ (agent's count − 1) of the real findings. A finding only
the agent sees is a **floor** (he could not see it even in his own code) → recurse
via DECOMPOSE/teach. Then normal v2 studio rounds run on the diff.

**Grounded example.** His reshape loop works on the happy path. Self-review
questions he must ask himself: *missing source file? malformed JSON line? dst
directory absent? empty input? a record already lacking `response`?* The real
script handles the missing file and mkdirs the directory — did his self-review
even raise them?

**DB.** faculty `evaluate`; v2 `reviews` table, with a new round-0 authored by him.

---

## ⑧ COMMUNICATE

**Purpose.** Explain the decision to another engineer; write the commit / docstring.
`knowledge.md:290-308`. Doubles as interview rehearsal.

**Learner produces.** A 3-sentence explanation of one real decision, and a commit
message or docstring for the slice.

**Pass-test.** The explanation names the load-bearing *why* and would let another
engineer act on it — graded on the presence of the reason, not eloquence. Mumbling
the *what* while missing the *why* is the MISS.

**Grounded example.** Write the `run_translation.py` docstring from scratch: explain
in three sentences why the env vars are set before the import and why 4500 tokens.
If he can teach it, he owns it; if he can only use it, he doesn't.

**DB.** new faculty `communicate`. Also feeds a future `interview` mode.

---

## ⑨ IMPROVE

**Purpose.** Close the loop: fix on evidence, iterate, retire false beliefs.

**Learner produces.** The fixes for ⑥/⑦ findings; a re-snap; and — where a
misconception drove the miss — production that no longer exhibits it.

**Pass-test.** A finding that survives round 2 is a **floor**, not a slip → descend.
A misconception is `retire`d only on an artifact that doesn't show it (v2 rule).
Then the session advances to the next SLICE, or the next slice of the target.

**DB.** v2 `misconceptions` + `reviews` round 2; ladder_log the floors found.

---

## THE CIRCLE-MAP (what he sees)

Furniture only, never pasted (v2 rule holds). `tree`/`PROGRESS.md` gains a header:

    TARGET: soufiane pipeline   slice 3/~14: build_translation_sources.py
    UNDERSTAND ▓▓▓░  DECOMPOSE ▓░░░  REASON ░░░░  DESIGN ░░░░
    IMPLEMENT  ▓▓▓▓  DEBUG     ▓░░░  EVALUATE ▓░░  COMMUNICATE ░░░░
                                            ▲ your journey, all 9 verbs

One glance says which faculty of the whole engineer is starving — not "21/97
language concepts."

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

## STILL OPEN (for Bilal)

- Does every slice run all nine, or is there a "small task" fast-path (①②⑤⑦ only)
  for tiny things, with ③④⑥⑧ reserved for meatier slices?
- Is `interview` a tenth, learner-chosen phase (timed, "explain to a CTO", mock
  system-design over the target), or just the COMMUNICATE verb turned up?
- Order of build: INTAKE + circle-map first (so you feel it this week), or write
  every verb's DB enforcement first (so it can't drift)?
