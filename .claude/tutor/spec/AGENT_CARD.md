# TUTOR — THE AGENT CARD (the blueprint every agent is derived from)

Status: LIVE. One blank form. Every agent (MAPPER · TEACHER · JUDGE · DISTILLER)
is DEFINED by filling this one card. Fill the card once → the engine knows how to
run that agent. Add a fifth agent later → fill the card again. Nothing else.

---

## THE ONE IDEA: only BODY is the agent

An agent is a contractor you hire for one job. CODE preps the job, the AGENT does
the work, CODE inspects the result. **The agent only ever sees the BODY.**

```
        CODE (harness)              │          AGENT (the AI)
   ───────────────────────────────  │  ─────────────────────────────
    PRE:  GATE · ASSEMBLE · GRANT   │
          builds the prompt +       │
          attaches only this        │
          job's tools               │
                                    │──►  BODY: the agent runs.
                                    │      its PROMPT = IDENTITY + RULES +
                                    │      METHOD + TOOL-WHEN + SELF-CHECK +
                                    │      ESCALATE + SAY-shape.
                                    │      it thinks, calls tools, EMITs.
    POST: VALIDATE · ENFORCE ·   ◄──│
          COMMIT · DELIVER          │
          checks, saves, publishes  │
```

So every blank on this card is ONE of two kinds:

    [PROMPT]  becomes text the AGENT reads   (lives in BODY)
    [CONFIG]  becomes code AROUND the agent   (PRE/POST — the AI never sees it)

Belt-and-suspenders law: a hard rule is written in BOTH — as a [PROMPT] rule the
agent is told, AND as a [CONFIG] guard code enforces if the agent forgets.
(Agents are fallible; code refuses.)

---

## THE BLANK CARD

```
 ╔══════════════════════════════════════════════════════════════════════╗
 ║  AGENT CARD :  «name»                                                 ║
 ║ ─────────────────────────── STABLE SHELL ─────────────────────────── ║
 ║  [PROMPT] IDENTITY  «who it is + stance (ally-ish / skeptical)»       ║
 ║  [PROMPT] RULES     «the standing laws it must ALWAYS obey»           ║
 ║  [CONFIG] HANDBACK  «STOP (yield to learner) | RETURN (back to code)» ║
 ╚══════════════════════════════════════════════════════════════════════╝
         │  shell wraps every call · rails below run each time
         ▼
 ┌───── PRE  [code — agent not awake yet] ──────────────────────────────┐
 │ [CONFIG] GATE      «precondition: when is this step legal?» (may BLOCK)│
 │ [CONFIG] ASSEMBLE  READS «stones/slices» → inject «the minimal packet»│
 │ [CONFIG] GRANT     tools: «exact set, nothing more» (scoped + revoked)│
 └──────────────────────────────────────────────────────────────────────┘
         ▼
 ┌───── BODY  [ai — this whole box IS the agent's prompt] ──────────────┐
 │ [PROMPT] METHOD     «the reasoning steps it follows to do its job»    │
 │ [PROMPT] TOOL-WHEN  «the trigger for each granted tool»               │
 │ [PROMPT] SELF-CHECK «its own last check before emitting (mirrors      │
 │                     ENFORCE, so it passes first try)»                 │
 │ [PROMPT] ESCALATE   «what to emit when it CAN'T finish — never guess» │
 │ [PROMPT] EMIT       SAY: «prose to learner, or —»                     │
 │                     STAMP: «the return.* shape, or —»                 │
 └──────────────────────────────────────────────────────────────────────┘
         ▼
 ┌───── POST  [code — agent already gone] ──────────────────────────────┐
 │ [CONFIG] VALIDATE  stamp ↔ schema · say ↔ say-rules   (reject → retry)│
 │ [CONFIG] ENFORCE   «invariants on the RESULT»         (may BLOCK/alter)│
 │ [CONFIG] COMMIT    WRITES «stones» — guarded writer, only now         │
 │ [CONFIG] DELIVER   SAY → learner (only after VALIDATE)                │
 │ [CONFIG] NEXT      HANDBACK: STOP (wait for reply) | RETURN (route)   │
 └──────────────────────────────────────────────────────────────────────┘

   THE ORDERING LAW (never broken):
       VALIDATE → ENFORCE → COMMIT → DELIVER
   nothing touches a stone or the learner until it has passed the guards.
```

---

## WHAT IS FILL vs FIXED

```
 FILL per agent:
   [PROMPT] IDENTITY · RULES · METHOD · TOOL-WHEN · SELF-CHECK · ESCALATE
            · SAY · STAMP
   [CONFIG] HANDBACK · GATE · READS/inject · tools · schema(VALIDATE)
            · ENFORCE invariants · WRITES

 FIXED by the engine (identical for everyone, you never rewrite):
   the PRE→BODY→POST order · the VALIDATE→ENFORCE→COMMIT→DELIVER law ·
   tools are scoped-and-revoked each call · every write goes through the
   one guarded writer · the agent can read ONLY the injected packet
```

To build an agent you fill two things at once: its **prompt** (the [PROMPT]
blanks → the BODY) and the **guard-rails code wraps around it** (the [CONFIG]
blanks → PRE/POST).

---

## THE FOUR CARDS (all filled — see spec/agents/)
- [x] MAPPER      — builds the ladder (SCAN), lazy/batched     → agents/MAPPER.md
- [x] TEACHER     — POINT / PROBE / TEACH / TEST (faces learner)→ agents/TEACHER.md
- [x] JUDGE       — grades an answer → verdict + category       → agents/JUDGE.md
- [x] DISTILLER   — saves proof + resets                        → agents/DISTILLER.md

Note: TEACHER covers several steps (point/probe/teach/test). Each step reuses the
same shell but swaps the [CONFIG] rails (different GRANT/READS/HANDBACK per step),
exactly as the wakeup.* templates in CATALOGS.md already specify.
