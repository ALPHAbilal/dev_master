# Braces, collections, and comprehensions

## The four brace/paren meanings (the big gotcha)

```python
(1, 2, 3)     # tuple   — round parens, fixed, can't change
[1, 2, 3]     # list    — square, ordered, duplicates OK
{1, 2, 3}     # set     — curly, NO colons, unique values, fast lookup
{"a": 1}      # dict    — curly WITH colons (key: value)
```

Same curly braces `{ }` mean **set** OR **dict** — the **colons** decide.
No colons → set. With `key: value` colons → dict.

Gotcha: the **empty set** is `set()`, NOT `{}`.
`{}` was already taken to mean an empty dict. `()` is a tuple, never a set.

## What a set is FOR (two reasons)

1. **No duplicates.** Adding a value that's already there changes nothing.
2. **Fast membership.** `x in myset` is basically instant no matter how big.
   In a list, `x in mylist` scans every element one by one — over thousands of
   items that's the difference that matters.

Real use in run_prompts.py:
```python
got = {json.loads(l)['custom_id'] for l in text.splitlines() if l.strip()}
...
if cid in got:   # "did this id come back?" — needs to be fast, needs uniqueness
```

## Comprehensions — build a collection inline

```python
nums  = [1, 2, 3, 4]
evens = [n for n in nums if n % 2 == 0]   # list comp -> [2, 4]
```

Read left to right:
- `for n in nums`  → walk each item
- `if n % 2 == 0`  → keep only the ones passing the filter
- `n` (the front)  → what to put in the result

Swap the brackets to change the container:
```python
[ ... ]   # list comprehension
{ ... }   # set comprehension (dedupes)

words   = ["hi", "yo", "hi", "hey", "yo"]
lengths = {len(n) for n in words}   # -> {2, 3}   (the four 2's collapse to one)
```

## Helpers seen alongside

- `text.splitlines()` → cut one big string into a **list of lines**
  (`"a\nb\nc".splitlines()` → `['a', 'b', 'c']`)
- `l.strip()` → remove whitespace from both ends; here `if l.strip()` skips
  blank lines (a blank line stripped is `""`, which is falsy)
