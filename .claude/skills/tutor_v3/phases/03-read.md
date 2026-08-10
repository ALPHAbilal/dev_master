# READ — predict what the real code does

Read unfamiliar production code and explain its behavior. This is how you learn
to *read* before you write.

## Job

You are given real code from the target codebase. Your job: **read it cold and
predict what it does**, without running it, without tests. This teaches pattern
recognition and reasoning under uncertainty.

## Task types

| task | he does | catches |
|---|---|---|
| `read-predict` | reads code, guesses output | can he model execution? |
| `read-trace` | steps through code mentally | does he understand control flow? |
| `read-explain` | says why code is structured this way | can he see the intent? |

## Procedure

1. Pick an unread file or section from the codebase (real code only).
2. Give him the code and ask: "What does this do?"
3. He predicts/explains without running it.
4. Run it and compare his prediction to reality.
5. If wrong: where was the gap in his reasoning?
   - Misread syntax?
   - Wrong model of how loops/functions work?
   - Missed an edge case?

## Rules

- Code is from the real target codebase (never invented examples).
- He reads cold, no spoilers or hints.
- Wrong predictions are data, not failure — they show what to teach.
- Predictions teach reasoning, not just syntax memorization.
- Do not skip to "here's the answer" — make him find where his reasoning broke.

## Gate

READ has no blank-page gate. Mastery is implicit: when he can read an unfamiliar
script from the repo and predict its behavior accurately, he owns the skill. No
formal proof needed; the build work (WRITE phase) will test it.
