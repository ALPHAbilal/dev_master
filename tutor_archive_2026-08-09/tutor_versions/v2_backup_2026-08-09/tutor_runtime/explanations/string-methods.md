# string-methods — the canonical explanation

Floor found 2026-08-06 after 3 descents (239s -> 143s -> 76s).
Explains: string-methods, tuple-unpacking.

## The real gap is not the methods. It is HARDCODING.

Three rounds, same tool, two outcomes:

```python
# round 1 (MISS)  -- he knew .replace() and still typed the ANSWER in
s.stripe().replace(""gpt-4.1-nano"", "gpt-4.1-nano")

# round 3 (HIT)   -- the transformation, not the answer
u.replace("-", "")
```

Same failure in sweep Q4: asked to split `PROMPT_MODEL=gpt-4.1-nano`, he wrote
`dict_hold['PROMPT_MODEL'] = "gpt-4.1-nano"`.

**The rule:** the program must not know the data, it must know the SHAPE of the
data. `run_prompts.py` runs over 304,920 records; none of them can be typed. What
can be typed is *strip the ends, drop the quote, split on the first `=`*.

By round 2 he had already corrected this himself — he replaced the character, not
the whole string. The rest was mechanics.

## Mechanic 1 — a quote inside a quote

`t.replace(""", ...)` cannot be read: a string ends at its matching delimiter.
Wrap it in the other kind:

```python
'"'    # one double-quote character
"'"    # one single-quote character
```

His own code, `run_prompts.py:53`: `value.strip().strip('"').strip("'")`

## Mechanic 2 — mutate or return, never both

He asked this himself, unprompted, having noticed his own `f.append('line')`:
*"what is the difference between .append() and s.strip() — does it change the
object itself?"* That is the correct question and it is the whole idea.

| | changes the object? | hands back |
|---|---|---|
| `list.append(x)` | yes (mutable) | `None` |
| `str.strip()` | no — impossible (immutable) | a new string |

A method that mutates has no result to give, so it returns `None` — which is the
`none-identity` idea he had just been promoted on, arriving from the other side.
A method that cannot mutate can only return; throw the return away and it
accomplished nothing.

Strings, numbers and tuples are immutable. Lists, dicts and sets are mutable.
Because each string method returns a string, calls chain:

```python
s.strip().strip('"')
```

## Prediction check (passed, 2026-08-06)

```python
p = '   ##hello##   '
print(p.strip())                      # -> ##hello##
print(p.strip().replace('#', ''))     # -> hello
print(p)                              # -> '   ##hello##   '  UNCHANGED
```
All three correct. Prediction only — does not promote.

## Copy-check note

The teach text showed `value.strip().strip('"').strip("'")` verbatim, so
quote-stripping in the gate is REPRODUCIBLE and is not evidence. Gate #2 was
built so the promotion rests on parts never shown: split-on-first-separator,
skipping blank/comment lines, and accumulating into a dict.
