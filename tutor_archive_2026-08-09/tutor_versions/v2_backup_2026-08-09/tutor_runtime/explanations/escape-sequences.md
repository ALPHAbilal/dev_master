# escape-sequences — the canonical explanation

Rung INSERTED 2026-08-07 via `revise --trigger BLIND_SPOT`. It was not in the
original 96: `string-literal` covered quoting and never covered escapes, so this
sat unreachable underneath `file-iteration`, `context-manager` and the whole
JSONL format his pipeline depends on.

Floor found after 2 descents. Explains: file-iteration, len-builtin, jsonl-format.

## How it surfaced

Review finding #1 (an unstripped newline) **survived a full round-2 fix**, even
after he was told it was one method call on a string he had used four times two
gates earlier. A finding that survives round 2 is a floor. Descending:

```
len(line) where the name is 13 chars   -> "23"        MISS
len('abc') / len('abc ') / len('abc\n') -> 3 / 4 / 5   PARTIAL  <- floor
len('a\nb') + what print(s) shows       -> "four" / "two lines"
```

The last one is the shape of it exactly: **he knows the EFFECT of the escape and
not its REPRESENTATION.** He correctly predicted two lines of output while
counting the escape as two characters. He could not strip a character he did not
believe was a single character.

Misconception `escape-is-two-chars` [language] opened on this evidence.

## The one idea

```
   SOURCE CODE (what you type)          VALUE IN MEMORY (what exists)

   ' a \ n b '                          ┌───┬────┬───┐
     │  └─┬─┘ │                         │ a │ \n │ b │
     │    │   │                         └───┴────┴───┘
     │    │   └──────────────────────────────────┘        len = 3
     │    └── the parser EATS the backslash,
     │        emits ONE character, value 10
     └───────────────────────────────────┘

   5 characters on screen  ──►  3 characters in the string
```

The backslash is an instruction to the parser, not data. It is consumed while the
string is being built. By the time the string exists there is no backslash in it,
only a single character with numeric value 10.

## In his own code

- `f.write(line + '\n')` — adds ONE character per line. He wrote this correctly
  in gate #6 without knowing what it was.
- Reading back: `'Côte d’Ivoire\n'` is 14 characters. `.strip()` removes the 14th.
  This is review finding #1.
- `run_prompts.py:553` — `f.write(json.dumps(req, ensure_ascii=False) + '\n')`
  is the only thing making the output JSON *Lines* instead of one 900 MB line.
- `run_prompts.py:216` — `text = text.replace("\\'", "'")`. `\\` is an escape for
  the backslash itself, because there the backslash IS data: `M\'Sila` arrived
  from SQL with a real backslash, which silently truncated OpenAI's constrained
  decoder. That entire bug is this concept.
- Raw strings `r'...'` turn the mechanism off, which is why every regex in the
  file uses them. That is the next rung, not this one.
