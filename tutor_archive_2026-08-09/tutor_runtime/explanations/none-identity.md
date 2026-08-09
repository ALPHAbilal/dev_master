# none-identity — the canonical explanation

Floor found 2026-08-05 after 3 descents. Explains: function-return,
dict-get-default, none-identity, slicing, generator-function.

## Where he already uses it

`prompts/run_prompts.py:196` — `extract_questions_lettered` returns `None` on
anything unexpected; `prompts/run_prompts.py:303` — `if qs is not None:` checks
for it. His own docstring: "anything unexpected returns None and the caller falls
back." The pattern is called a **fail-safe default**. He built it before he could
name it.

## The one idea

**`None` is a value.** Not an error, not "nothing", not `False`. It is an object,
like `5` or `"abc"` — Python's way of saying *there is a value here, and the value
is: no answer.*

## The four consequences (which were his four misses)

1. **It displays as `None`.** `x = None; print(x)` → `None`. Not blank, not
   `False`.

2. **`None` and `False` are different objects.** Both are falsy — `if not x:`
   triggers on either — but `None == False` is `False`. Falsy is not equal.
   *(He stated the opposite belief twice, in two separate sessions: sweep Q8 and
   descend round 2. This is the specific belief to kill.)*

3. **A function with no `return` hands back `None`, automatically, always.**
   ```python
   def f():
       print("hi")
   x = f()      # prints hi
   print(x)     # None
   ```
   His own `save_ledger` (`run_prompts.py:489`) writes a file and has no
   `return`; calling it gives `None`.

4. **`.get()` hands back `None` instead of raising — that is why it exists.**
   ```python
   record = {}
   a = record.get('prompt')   # None, no error
   b = record['prompt']       # KeyError, program stops
   ```
   `[]` means *this key must be there, crash if not*. `.get()` means *it might
   not be, hand me `None` and let me decide*. His loader at `run_prompts.py:519`
   uses `.get()` then `if not prompt:` — a record missing its prompt should be
   skipped, not crash a 300,000-record run.

## Prediction check (passed, 2026-08-05)

```python
def build(rel):
    print("building", rel)
d = {'model': 'gpt-4.1-nano'}
x = build('exec/pays_ville_exec.json')
print(x)                    # -> None
print(d.get('model'))       # -> gpt-4.1-nano
print(d.get('temperature')) # -> None
```
All three correct, unaided. Prediction only — does not promote. The gate decides.

## Copy-check note

His prediction mirrored the worked example structurally. The gate was therefore
built around a different shape (a function that returns a real value on one path
and `None` on the other) so a reproduced answer cannot pass as evidence.
