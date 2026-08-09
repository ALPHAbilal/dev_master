# open-modes — the canonical explanation

Floor: `context-manager` (2 descents, 2026-08-07). He owns `with open(...) as f:`
and `f.write(...)`. This is the single step above it.

## What he already had

Sweep Q9 he wrote `with open.(r'/path','a') as f:` then `f.append('line')`.
Descend round 1, unprompted and clean:

```python
with open('out.txt', 'w') as f:
    f.write('hello')
```

The `with` form and `f.write` are his. Two things were missing.

## 1. `encoding=` — there is no default, and that is the point

Asked what `open()` uses when `encoding` is omitted, and what breaks on accented
city names: **"no idea"** on both. Honest, and the first `vocabulary` probe ever
taken in this system.

THE AGENT WAS WRONG FIRST AND SAID SO. It was about to state the default is UTF-8,
or state cp1252 flatly as a language rule. Both false. See `lookup #1`.

> "In text mode, if *encoding* is not specified the encoding used is
> platform-dependent: `locale.getencoding()` is called to get the current locale
> encoding." — docs.python.org/3/library/functions.html#open
>
> "On Windows, return the ANSI code page."
> — docs.python.org/3/library/locale.html#locale.getencoding

```
   open('f.txt','w')                 open('f.txt','w', encoding='utf-8')

   his Windows box  ──► cp1252       his Windows box  ──► utf-8
   a Linux server   ──► utf-8        a Linux server   ──► utf-8
   a colleague's PC ──► cp932        a colleague's PC ──► utf-8
        │                                    │
        └─ same code, three files       └─ same code, one file
```

It is an operating-system decision read at runtime, not a Python one. `ô` exists
in cp1252 so it survives; `’` and `ệ` do not, and the write raises
`UnicodeEncodeError` at record 40,000, three hours into a run — or succeeds
locally and produces a file the server cannot read.

This is why `encoding='utf-8'` appears eleven times in his own `run_prompts.py`.

## 2. `write` adds nothing

`f.write('hello')` puts down exactly those characters. No newline. Called twice
it yields `hellohello` on one line. His own code:
`f.write(json.dumps(req, ensure_ascii=False) + '\n')` — the `+ '\n'` is the only
thing making it JSON *Lines* rather than one 900 MB line.

Reading back is the mirror: every line arrives WITH its `'\n'` still attached,
which is why `.strip()` appears on the read side of every loop he has.

## Gate #6

Built so the requirement is enforced by the machine, not by the agent: the data
contains `’` and `ệ`, which the Windows ANSI code page cannot encode. Omitting
`encoding='utf-8'` does not produce a subtly worse file — it raises
`UnicodeEncodeError` and stops. The contract cannot be partially read.
