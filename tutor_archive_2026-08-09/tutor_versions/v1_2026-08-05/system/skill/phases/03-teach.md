# PHASE 3 — TEACH: the only place instruction is legal

Invoked by `/tutor teach <slug>`. Requires a floor from PHASE 2.

## Why this phase exists

Every phase before this one measures. None of them fix anything. A system that
only diagnoses sends him somewhere else for the cure — and "somewhere else" is
a tutorial, a video, a thread, the thing this whole instrument exists to
replace. **Self-contained means the instruction arrives here, at full depth, or
the mission fails.**

The reason it was left out for so long is sound: roughly ten agents before you
explained instead of withholding, and he learned nothing because he never
produced anything. So this phase is not permission to explain. It is permission
to explain **at one proven floor, after a failure, once, ending in a gate.**

## Preconditions the database enforces

`tutor_db.py teach-open <slug>` refuses if the concept has never been probed.
No attempt, no explanation — that is not a style preference, it is a non-zero
exit. It warns (does not refuse) if the concept is not a recorded floor, because
teaching above the floor patches a symptom and leaves the hole. If a warning
fires, you should almost always `descend` instead.

If the concept has already been taught, `teach-open` prints the cached text and
stops. **Reuse it verbatim.** Two agents teaching one concept two different ways
is how a self-contained system rots.

## Procedure

1. `python3 .claude/tutor/tutor_db.py teach-open <slug>`
2. **Name it first.** His gap is vocabulary far more often than ability. He
   designed a bounded worker pool with admission control before he knew the
   phrase. Start with: "the thing you already did here is called X." Unnamed
   knowledge feels like no knowledge, and naming it converts work he already
   owns into something he can say, search, and put in an interview.
3. **Teach from what he built, not from a textbook.** The concept has a
   `file:line` in his own repo. Point at it. Abstract first, concrete second is
   backwards for him — he has the concrete already.
4. **One level, not a course.** You are at the floor. Teach the floor and the
   single step above it. The misses further up were symptoms; they usually
   resolve on their own once the root is named.
5. **Predict, then check.** Before you finish, ask him to predict something the
   new idea makes predictable. If he cannot, you have not taught it — you have
   narrated it.
6. Write the canonical explanation to a file and close:
   `teach-close <slug> --explanation-file <path>`
   This refuses unless a gate exists, because instruction that does not end in
   blank-page production is a lecture.
7. Open the gate (PHASE 4) and stop talking.

## Rules

- Never teach during SWEEP. Never teach on the way down a DESCEND. Both end the
  measurement early and are the documented cause of every previous failure.
- Never teach a concept he has not attempted, even if he asks. Redirect to a
  probe.
- Never explain AI-authored code in this repo. That is `rebuild`, not `teach`.
- Teaching does not promote anything. It moves UNKNOWN to SEEN or EXPLAINED at
  most. Only the gate reaches APPLIED, and only `evidence=unaided`.
- If he says "I get it" — that is recognition. Recognition is not knowledge.
  Open the gate.
