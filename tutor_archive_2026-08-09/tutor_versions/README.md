# TUTOR — VERSION ARCHIVE

Every version of the tutor is frozen here before the next one replaces it, with
the evidence that justified the change. Nothing is deleted; versions accumulate.

```
tutor_versions/
├── README.md              ← this file
└── v1_2026-08-05/
    ├── POSTMORTEM.md      ← what v1 was, what worked, what failed, why
    ├── system/            ← the running system, exactly as it was
    │   ├── tutor/         (tutor.db, tutor_db.py, tutor_hook.py, schema.sql, spine/)
    │   ├── skill/         (SKILL.md + phases/)
    │   ├── settings.json
    │   └── settings.local.json
    └── evidence/          ← the raw material the postmortem was built from
        ├── teacher-lab.raw.jsonl   session cd6bd584, 744 records, 2026-07-24 → 08-05
        ├── lab.exchanges.md        readable digest, 55 exchanges
        ├── lab.user.md             every learner turn, verbatim
        ├── log.md.final            the answer file as it survived (252 bytes)
        └── spine.py                the streaming extractor used to build the digest
```

## Rule for freezing a version

A version is frozen **before** it is altered, never after. The freeze must
include:

1. the running system (code + database + skill + hook wiring),
2. the raw conversation that the system produced,
3. a postmortem that names each failure and points at the evidence for it.

If a postmortem cannot cite evidence for a failure, the failure is a guess and
does not justify a change.

## Versions

| version | frozen | ran | outcome |
|---|---|---|---|
| **v1** | 2026-08-05 | 2026-07-23 → 2026-08-05, 12 sessions, ~9h | 18 APPLIED / 241 concepts. Doctrine sound, bookkeeping failed. See `v1_2026-08-05/POSTMORTEM.md`. |
| **v2** | *(live)* | from 2026-08-05 | Two states, four phases, attempts archived and diffed, error classes, a clock, mechanical copy-check, reviews inside the build. Freeze it here before v3. |

## v1 → v2, in one line each

| # | change | v1 failure it answers |
|---|---|---|
| D1 | depth 3+ parked (138 concepts off the ladder, still in the bank) | F1 |
| D2 | the agent picks every rung; the learner never chooses a concept | F8 |
| D3 | `map` / `ladder` are no longer things he types | F8 |
| D4 | `UNKNOWN/SEEN/EXPLAINED/APPLIED` → `CANT/CAN` (v1 value kept in `state_v1`) | F6 |
| D5 | one sweep, ever | F1 |
| D6 | toy data retired once the real file is open | F7 |
| A1 | four phases: `FLOOR → READ → BUILD_V1 → BUILD_V2` — his only choice | F8, F9 |
| A2 | `due-slice`: reviews are scheduled as slices of the real file | F4, F7 |
| A3 | `attempt snap` archives + diffs every submission before grading | F3, F4 |
| A4 | `--error-class gap\|syntax\|typo\|bleed\|fatigue`, typos never demote | F4 |
| A5 | `--seconds` required; automatic FATIGUE warning | F5 |
| A6 | `assume` / `assume --veto` — stated prerequisites, logged blind spots | F2 |
| A7 | `promote CAN` refuses without `--copy-checked` | F3 |
| A8 | wide multi-concept gates at FLOOR | F9 |

Verification at cutover: `python3 .claude/tutor/test_tutor.py` → **65 passed, 0 failed**.
Live DB integrity `ok`; row counts unchanged from v1 (241 concepts, 73 probes,
12 sessions); no id or historical value rewritten.
