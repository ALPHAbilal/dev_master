# TUTOR — THE AXES & THEIR EVIDENCE BARS

Status: DRAFT (recommended defaults — you were unsure, so I proposed these;
revisit the wording any time). This is the table TEST reads (to choose a
challenge) and JUDGE reads (to decide what counts as proof) for each axis.

An "axis" = one way of understanding a unit. A unit is OWNED only when every
FIRING axis is SOLID. The evidence_bar is the answer to: **"for THIS axis, what
must he actually DO to prove it — such that faking is impossible?"**

Grounded on the running example:
```python
def _pinned_qa_group(questions):
    groups = {}
    for q in questions:
        groups.setdefault(q.pin_id, []).append(q)
    return groups
```

---

## THE TABLE

```
 axis         WHAT IT PROVES            EVIDENCE BAR (the un-fakeable test)        FAKE TELL (what a bluffer does)
 ───────────────────────────────────────────────────────────────────────────────────────────────────────────
 COMPREHEND   he knows what it DOES     restate the behavior in his own words;    re-reads the code aloud /
              (behavior, not syntax)    predict the return for a given input      repeats the keywords back
              e.g. "what is `groups`    "give me [q(pin=5),q(pin=5),q(pin=7)] —   without saying what it MEANS
              after this runs?"         what's in groups?"

 MECHANISM    HOW it works underneath   trace it line-by-line; explain what       hand-waves "it groups them"
              (the machinery)           setdefault does on hit vs miss            without the hit/miss branch
              e.g. "what does           "walk me through the 2nd iteration"
              setdefault do on a key
              that already exists?"

 RATIONALE    WHY this shape (design     justify THIS choice AND reject a          gives a plausible-but-wrong
              intent)                    concrete alternative                      reason (e.g. "dicts keep order")
              e.g. "why a dict keyed     "why not a list of (id,q) tuples?"        that happens to be true-ish
              by pin_id?"

 JUDGMENT     WHEN to use it, WHEN not   name a real case where you would NOT      says "always use a dict" /
              (the trade-off)            use this, with the cost                   can't name a downside
              e.g. "when would this      "when would a list actually be better?"
              grouping be the wrong
              tool?"

 ROBUSTNESS   what BREAKS it (edges,     predict the failure/edge before running   claims "it handles everything";
              failure)                   "what if pin_id is None? two share an     only sees the happy path
              e.g. "what input makes     id? the list is huge?"
              this misbehave?"

 INTEGRATION  how it FITS the system     name who calls it / what consumes         talks about the function in
              (up/downstream)            `groups` and what would break upstream    isolation, ignores callers
              e.g. "who depends on the   if the shape changed
              shape of `groups`?"        "if I returned a list instead, what
                                         downstream breaks?"

 EVOLUTION    how you'd CHANGE/extend/    make a correct modification (add a       describes a change in words but
              debug it                    feature / fix a planted bug / port it)   the edit is wrong or vague
              e.g. "add case-insensitive  "make it skip questions with no pin_id"
              grouping"                   — and he writes it right
```

---

## HOW TEST USES IT
`wakeup.test` reads the current axis's row, takes the EVIDENCE BAR column, and
generates a concrete challenge of that type on the real unit. The bar is the
*kind* of proof; TEACHER writes the specific question.

## HOW JUDGE USES IT
`wakeup.grade` reads the same row. SOLID requires the answer to clear the bar
(and NOT match the FAKE TELL). If it matches the fake tell, that's the
"faking / pattern-matched" category → route to a harder test.

## PROOF ESCALATION (predict → break → port)
The three strongest proof types, hardest to fake, in order:
```
 PREDICT  say the output/behavior BEFORE running it        (COMPREHEND/MECHANISM)
 BREAK    name the input that breaks it / the edge          (ROBUSTNESS/JUDGMENT)
 PORT     change it correctly — modify, extend, or fix       (EVOLUTION/INTEGRATION)
```
When an axis is borderline, escalate to the next proof type rather than accepting
a confident restatement.

## OPEN
- [ ] not every axis fires on every unit — MAPPER picks which (see MAPPER.md).
- [ ] wording of each bar is a first draft; tighten with real teaching data.
