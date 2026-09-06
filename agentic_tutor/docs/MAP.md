# THE MAP — learning process → agents, tools, context, state

The agreed process (v2). Every step names: who runs it, what wakes it, the tools it
holds, what is injected, and the rows it must leave. **Evidence-or-it-didn't-happen:
each step's gateway op requires the previous step's row.**

Agents: **M** plans (never seen), **L** teaches (the only voice), **CODE** routes
(no model: wakeups, context blocks, wipes, refusals, the review queue).

## The loop

```
⓪ REACTIVATE  ─ session open ─▶ ② PROBE ─▶ ③ STUDY ─▶ ④ COMPLETE ─▶ ⑤ PRODUCE
                                   │  (probe routes the entry point ──▶ ③/④/⑤)
                                   ▼
   ⑧ ABSTRACT ◀─ ⑦ VARY ◀─ ⑥ NAME ◀─┘        MISS at ⑤ drops ONE level, retries
        │ OWNED (machine-checked)
        ▼
   more unowned prereqs? ──yes──▶ M/REGAP (next gap) ──▶ ②
        │ no
        ▼
   ⑨ GATE ─▶ ⑩ JUDGE ─ PASS ─▶ BUILT ─▶ M/PLAN (next slice)
        ▲              └ FAIL: leaked concept re-enters at ④
   ⑪ CONSOLIDATE closes the session; its misses feed next ⓪
```

## Step table

| step | agent | wakeup (state cell) | live tools | injected (rented) | row required in → row out |
|---|---|---|---|---|---|
| ⓪ REACTIVATE | L | state poll + due reviews > 0 | db | [REVIEW] due questions only | queue → `review` rows; MISS demotes concept |
| ① FRAME | L | frontier published, L silent | db | [SLICE] why-this-slice | — |
| ② PROBE | L | gap unopened | db | [GAP] opening-question only | — → `probe kind=entry` (sets level 3/4/5) |
| ③ STUDY | L | entry=3 | db, Read | worked example; *predict-before-run* rule | entry → `probe kind=predict` per example |
| ④ COMPLETE | L | entry≤4 or drop | db, Read | completion task, holes list | predict/entry → `probe kind=produce(partial)` |
| ⑤ PRODUCE | L | entry=5 or climb | db (no write tools exist) | fresh task; prediction demanded before output judged | — → `probe kind=produce` HIT/MISS |
| ⑥ NAME | L | first ⑤ HIT | db | just-tell residue + real vocab | HIT → `promote_vocab` |
| ⑦ VARY | L | after ⑥ | db | 2–3 variant surfaces + owned mappings to interleave | HIT → `probe kind=vary` ×2 |
| ⑧ ABSTRACT | L | ⑦ done | db | mapping-seed trigger | vary×2 → `store_mapping` (HIS words) → `close_gap` |
| — REGAP | M | gap OWNED, prereqs remain | db | [EVIDENCE] fresh probes + [OVERLAYS] | probes → next gap in frontier |
| ⑨ GATE | L | all prereqs OWNED | db (wall denies spec-read/target-write) | [GATE] block only | `open_gate` (refuses NULL spec) |
| ⑩ JUDGE | L | learner says done | db, Read, Grep | spec vs code checklist | gate → `pass_gate`/`fail_gate(+concept)` |
| ⑪ CONSOLIDATE | L | slice BUILT | db | ask HIS summary | — → `session_note`; queue schedules today's misses |
| — PLAN | M | frontier empty/spent | db, Write | [EVIDENCE], [OVERLAYS], pre-seeded op menu | — → spec file + next frontier |
| — SURVEY | M | no slices | db, Read, Grep, Web | [SURVEY] + tool discipline | — → spine + concept DAG |

## Enforcement (gateway refusals, not prose)

- `close_gap` refuses without: ⑤ HIT + 2 `vary` HITs + a mapping in the learner's words.
- `open_gate` refuses while any prereq is unowned or the spec is NULL.
- `pass_gate` refuses without a judge note naming what was checked.
- Every refusal names the missing row — the refusal text *is* the protocol.

## Context law

- **Rented context**: a block appears only in the step-window it serves (table above). The answer (`just_tell`) enters at ⑥, never before.
- **Post-act steering**: after every db commit, CODE injects the one line that fits the new state (PostToolUse).
- **Pre-seeded menu**: each turn opens with the op signatures live for that step; zero discovery calls.
- **Scoped amnesia**: L wipes per slice, M per wake — but only after CODE distills the residue (trigger phrases, error patterns, calibration) into rows. Wipe transcript, never learning.

## Two UIs, firewalled

- **Learner page** (`/`): the journey only — map position, chat, progress. No pushes, no probe results, no phase names.
- **Dev page** (`/dev`): everything — full trace per turn (system prompt, tools, args, results), probes, vocab states, mappings, review queue, wakeup decisions. This is where the engineer judges and debugs; it never leaks into the chat.
