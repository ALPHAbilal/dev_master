# Defects and optimisation targets

Compiled 17 Aug 2026 from live runs plus the Inspector record in `log.md`
(one M/SURVEY turn, 77 `db()` calls with an op).

---

## The headline number

**28 of 77 `db()` calls were refused — 36%.** And 24 of those 28 are the *same two
mistakes*, each repeated exactly 12 times:

| count | refusal | what the model sent |
|---|---|---|
| 12 | `missing required arg: slug` | `{name, status}` — no `slug` |
| 12 | `unknown arg: status` | `status` instead of `state` |
| 1 | `missing required arg: codebase_path` | `path` |
| 1 | `missing required arg: title` | — |
| 1 | `missing required arg: target_file` | — |
| 1 | `unknown arg: name` | — |

Plus 4 calls to operations that do not exist: `help`, `menu`, `describe`,
`upsert_concept_edge`.

37 `upsert_concept` calls produced 12 concepts. 33 `upsert_slice` calls produced 29
slices. Roughly a third of the turn was spent arguing with the schema.

---

## O1 — The refusal feedback loop is broken by parallel calls  · **highest value**

The 12× repeats are not the model failing to learn. It **issued all 12 calls before any
result came back**, so refusal #1 could not inform calls #2–12. One bad guess costs
twelve refusals, twelve round trips, and twelve times the tokens.

**Fix:** make a single refusal self-correcting — put the full schema *in the refusal
text*, not just the complaint. Today:

```
REFUSED: unknown arg: status
```

Should be:

```
REFUSED: unknown arg: status
upsert_concept accepts: slug (required), name (required), definition,
aspect, state, requires
  did you mean: state
```

A Levenshtein-1 "did you mean" on rejected arg names would have killed both 12× loops
outright. This is ~15 lines in `operations.validate`.

## O2 — `state` vs `status` is our inconsistency, not the model's

The model said `status` twelve times because **our own schema is inconsistent**:
`concepts.state`, `slices.state`, but `vocab.status`. It guessed the wrong one of two
words we ourselves use interchangeably.

**Fix:** either rename `vocab.status` → `vocab.state`, or accept `status` as an alias on
concept/slice ops. Renaming is cleaner; aliasing is cheaper and non-breaking.

## O3 — `describe()` carries no example

`describe()` returns field names and types. It does not show a filled call, so a model
that skips it loses nothing it can see, and a model that reads it still guesses at value
shapes. This is also the root of the `_probe_` junk rows (O6).

**Fix:** add one worked example per operation to `Operation.describe()`. One extra field
in the dataclass, rendered under `args:`.

## O4 — The menu is not discoverable by its own name

Four calls went to non-existent operations: `help`, `menu`, `describe`,
`upsert_concept_edge`. The first three are the model looking for the menu *by the
obvious names*.

**Fix:** accept `help`/`menu`/`describe`/`list`/`ops` as aliases that return the menu
instead of `no such operation`. Also: DAG edges are set through `requires` on
`upsert_concept`, which nothing advertises — hence the invented
`upsert_concept_edge`.

## O5 — `check=true` is underused (10 of 77 calls)

The dry run exists and works, but the model used it for 13% of calls and committed the
rest blind. The `[TOOL DISCIPLINE]` block mentions it; that is evidently not enough
against a model in a hurry.

**Fix:** name it in the refusal itself — "call again with `check: true` to validate
without writing" — so it is discovered exactly when it is needed.

## O6 — Junk rows survive from schema probing  · *open*

A survey wrote `_probe_` as both a slice and a concept, titled *"IGNORE - schema probe
artifact"*, purely to discover the schema. O1+O3 should remove the motive. If it
recurs, the harder fix is refusing obviously-placeholder slugs (`_probe_`, `test`,
`foo`) during SURVEY.

## O7 — Frontier quality is the weakest link  · *open, and the most important*

Structurally valid, pedagogically leaky. From the Haiku run on `load-dotenv`:

- `just_tell` contained the **entire solution** (`dict.setdefault(key, value) is the
  safe way to merge…`) on an `intuition-train` road, where he is supposed to guess.
  G2 scopes `just_tell` to names and conventions only.
- `vocab_ok` contained **`setdefault`** — the word the gap exists to discover. Compare
  the fixture: gap `enumerate-index`, and `enumerate` sits in **`vocab_hold`**.
- `vocab_hold` held sentences with parenthetical explanations, not terms.
- `gate_when` was circular: *"After writing load_dotenv and running basic tests"*. The
  fixture's shape is a concept condition: *"enumerate-index reaches OWNED"*.
- M asserted `"both LOCKED — already taught"`, which inverts what LOCKED means.

**Fix:** the frontier schema validates presence, not sanity. Add semantic checks to
`write_frontier`: the gap concept must appear in the slice's `concept_prereqs`; the gap
concept's own name must not appear in `vocab_ok`; `gate_when` must reference a concept
slug. Each is a few lines and each catches a real failure above.

## O8 — `spec_path` can be stored relative  · *latent*

The library root derives from the `--db` path. Launched with a relative `--db`,
`spec_path` is stored relative, and `open_gate` does a `Path.exists()` — so starting the
server from a different working directory would silently fail the gate.

**Fix:** resolve the library root to an absolute path when it is set.

## O9 — Transient API failure leaves a half-finished turn  · *low*

A 529 Overloaded killed one M/PLAN between `write_spec` and `write_frontier`. Recovery
worked (the spec persisted, the frontier was still missing, so the turn was simply still
due) but it is luck, not design. The surfaced error was also unhelpful:
`Claude Code returned an error result: success`.

**Fix:** retry once on 429/529, and surface `ResultMessage.result`/`errors` rather than
the generic wrapper text.

---

## Already fixed (regression-tested)

| # | Defect | Fix |
|---|---|---|
| F1 | M/SURVEY could never fire — adoption wrote the `target` row, and the wakeup keyed off that row | wakeup keys off an empty **spine** |
| F2 | Status dot pulsed as "working" when nothing ran | real `running`/`due`/`waiting` status; only execution animates |
| F3 | Survey output buffered — transcript empty for the whole run | events emit as they stream |
| F4 | Survey agent ran `Bash` and `Skill`, inheriting the host project's `.claude` | `setting_sources=[]` + explicit `disallowed_tools` |
| F5 | Indicator relabelled a running SURVEY as "M/PLAN due" the moment it wrote a slice | actual execution outranks the predicted wakeup |
| F6 | Model unpinned — runs not comparable | `DEFAULT_MODEL` + `--model`, shown in the header |
| F7 | Re-survey required wiping the DB by hand | auto-archive to `.tutor/runs/`, then clear |
| F8 | Dead end after the survey with no explanation | names the missing runner |
| F9 | "Can't run yet" and "say something to begin" shown together | blocked state suppresses the invitation |
| F10 | **M's prose leaked into the learner's transcript** — M must never speak to the learner | `agentrun.drive()` gates prose on `LEARNER_FACING` |

---

## Suggested order

1. **O1 + O2 + O3** — one pass over `operations.py`. Should remove most of the 36%.
2. **O7** — semantic validation in `write_frontier`. Teaching quality lives here.
3. **O4, O5, O8** — small, independent.
4. **O6, O9** — re-measure after 1; they may not survive it.

Re-run one M/SURVEY after step 1 and compare the refusal rate against the 36% baseline.
