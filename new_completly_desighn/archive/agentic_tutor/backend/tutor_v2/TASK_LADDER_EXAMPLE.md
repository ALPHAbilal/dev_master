# Task Ladder — a practical walkthrough

Brainstorm example, **not a spec**. It shows how the task-driven, per-concept design behaves
with a real learner: the tasks, what the TUTOR says, what the learner does, and what the
ENGINE and EXAMINER do behind the scenes.

The codebase is invented, so nothing in a real repo is spoiled. Times are illustrative.

---

## 0. The cast

```
 CARTOGRAPHER  reads the code once → concepts + task ladder. Never sees the learner.
 TUTOR         the only voice the learner hears. One task, one concept at a time.
 EXAMINER      turns evidence (runs, tests, answers) into HIT / MISS. Never talks to the learner.
 ENGINE        plain code. Owns all state, runs all code, picks every next step.
 SAM           the learner (they/them).
```

**Sam's profile:** 3 years of JavaScript/TypeScript (React, Node). Built `shortlink` with an AI
assistant last month. Goal: *own it*, meaning change it without the AI.
The profile is **only a hint**: it tells the engine which traps to probe first. It never marks
anything as known.

### Three rules used everywhere below

```
 RULE A  ladder rule   a HIT on a rung also passes every rung below it
                       (if you can perturb it, you can predict it)
 RULE B  fresh rule    a right answer AFTER the answer was shown earns no HIT;
                       a new question is needed
 RULE C  help rule     work finished with a direct hint (or in ally mode) is provisional (~);
                       a later unaided task or review confirms it
```

The 4 rungs, per concept: **predict** (say what it produces) → **perturb** (say what changes if
one line changes) → **produce** (write it) → **transfer** (use it where it wasn't taught).

---

## 1. The codebase: `shortlink`, a URL shortener

```
shortlink/
├── app.py      routes (FastAPI)
├── store.py    where links live (in memory)
├── codes.py    makes short codes
├── stats.py    counts clicks
└── tests/test_links.py
```

**app.py**
```python
 1  from fastapi import FastAPI, HTTPException
 2  from fastapi.responses import RedirectResponse
 3  from pydantic import BaseModel
 4
 5  from . import codes, stats, store
 6
 7  app = FastAPI()
 8
 9
10  class NewLink(BaseModel):
11      url: str
12      tags: list[str] = []
13
14
15  @app.post("/links")
16  async def create_link(body: NewLink) -> dict:
17      code = codes.unique_code(store.codes())
18      store.save(code, body.url, body.tags)
19      return {"code": code}
20
21
22  @app.get("/{code}")
23  async def follow(code: str) -> RedirectResponse:
24      link = store.get(code)
25      if link is None:
26          raise HTTPException(status_code=404, detail="unknown code")
27      stats.record_click(code)
28      return RedirectResponse(link["url"], status_code=307)
```

**store.py**
```python
 1  from datetime import datetime, timezone
 2
 3  _links: dict[str, dict] = {}
 4
 5
 6  def save(code: str, url: str, tags: list[str] | None = None) -> dict:
 7      link = {"url": url, "tags": tags or [],
 8              "created": datetime.now(timezone.utc)}
 9      _links[code] = link
10      return link
11
12
13  def get(code: str) -> dict | None:
14      return _links.get(code)
15
16
17  def codes() -> set[str]:
18      return set(_links)
```

**codes.py**
```python
 1  import secrets
 2  import string
 3
 4  ALPHABET = string.ascii_letters + string.digits      # 62 characters
 5
 6
 7  def new_code(length: int = 6) -> str:
 8      return "".join(secrets.choice(ALPHABET) for _ in range(length))
 9
10
11  def unique_code(taken: set[str], length: int = 6, tries: int = 5) -> str:
12      for _ in range(tries):
13          code = new_code(length)
14          if code not in taken:
15              return code
16      raise RuntimeError("no free code after several tries")
```

**stats.py**
```python
 1  from collections import Counter
 2
 3  _clicks: Counter[str] = Counter()
 4
 5
 6  def record_click(code: str) -> int:
 7      _clicks[code] += 1
 8      return _clicks[code]
 9
10
11  def top(n: int = 3) -> list[tuple[str, int]]:
12      return _clicks.most_common(n)
```

---

## 2. CARTOGRAPHER maps it (runs once, before Sam arrives)

### Overview (the first thing a learner sees)

```
 POST /links  → codes.unique_code → store.save → {"code": "aZ3k9Q"}
 GET  /{code} → store.get → stats.record_click → 307 redirect to the long URL
 State lives in two module-level objects: store._links and stats._clicks.
```

### Concept bank (excerpt)

| id | concept | kind | where | needs | common traps (by background) |
|---|---|---|---|---|---|
| C0 | names point to objects (two names, one list) | language | everywhere | — | — |
| C1 | `d[k]` raises, `d.get(k)` returns None | language | store.py:14 | — | from JS: `obj[k]` gives `undefined` |
| C2 | truthiness: `None`, `[]`, `0`, `""` are falsy | language | store.py:7 | — | from JS: `[]` is truthy |
| C3 | default arguments are evaluated **once** | language | store.py:6 | C0 | from JS: defaults run at every call |
| C7 | `secrets` vs `random` (unguessable codes) | stdlib | codes.py:8 | — | — |
| C8 | bounded retry loop, then fail loudly | failure | codes.py:11-16 | — | — |
| C9 | decorators register routes | api | app.py:15,22 | — | — |
| C10 | `async def` / `await` | language | app.py:16,23 | — | from JS: calling an async fn starts it |
| C11 | pydantic models: validation and defaults | api | app.py:10-12 | C9 | — |
| C12 | `HTTPException` → status codes | api | app.py:26 | C9 | — |
| C13 | `Counter` / `most_common` | stdlib | stats.py | C1 | — |
| C14 | module-level state: lost on restart, not shared across workers | architecture | store.py:3, stats.py:3 | C0 | — |
| C15 | redirect codes: 307 vs 301 (browser caching) | api | app.py:28 | — | — |
| C16 | timezone-aware datetimes | stdlib | store.py:8 | — | — |

### Task ladder (generated from this code, small → big)

| id | task | type | concepts it needs | done when |
|---|---|---|---|---|
| T1 | run it and predict 4 behaviours | understand | C9 C1 C15 C13 | every prediction compared with a real run |
| T2 | add `GET /top` (top 5 codes) | first change | C9 C13 | `test_top` passes |
| T3 | planted bug: links share tags | debug | C0 C2 C3 | `test_tags_not_shared` passes |
| T4 | links can expire: optional `expires_in_days`, 410 after | modify | C2 C12 C16 | `test_expiry` passes (frozen clock) |
| T5 | webhook: notify a URL when a link is created | assemble | C10 C11 C12 | the mock endpoint gets exactly 1 POST |
| T6 | store links in SQLite so they survive a restart | build (ally) | C14 + sqlite3 | `test_survives_restart` passes |
| T7 | rebuild `codes.py` from a blank page, no spec | solo | C7 C8 | EXAMINER reviews intent and forks |

Every task runs on a **learning branch**. Sam's main code changes only if Sam chooses to keep a change.

---

## 3. What Sam sees first

```
══════════════════════════════════════════════════════════════════════
 shortlink · a URL shortener (FastAPI)              14 concepts · 7 tasks
──────────────────────────────────────────────────────────────────────
 HOW IT WORKS
   POST /links  → codes.unique_code → store.save → {"code": "aZ3k9Q"}
   GET  /{code} → store.get → stats.record_click → 307 redirect

 YOUR CONCEPTS   0 owned · 14 not tested yet

 TASKS
   ► T1  run it and predict 4 behaviours           suggested
     T2  add GET /top
     T3  fix a planted bug
     T4  links can expire
     T5  webhook on create
     T6  survive a restart (SQLite)                 pair mode
     T7  rebuild codes.py from a blank page         solo
══════════════════════════════════════════════════════════════════════
```

Sam can pick any task. The engine *suggests* the one in Sam's stretch zone.

---

## 4. T1: understand (placement: fast lanes and slow lanes)

Four concepts, all untested. Each gets a **placement probe at perturb**.

**C9 decorators: fast lane**
```
[ENGINE]   T1 · C9 · perturb (placement)
TUTOR:     app.py, lines 22–28. Don't run anything yet.
           If I delete line 22 (@app.get("/{code}")), what happens when you open /aZ3k9Q?
SAM:       follow() isn't registered as a route anymore, so FastAPI answers 404 Not Found.
[ENGINE]   runs both versions → 404 {"detail": "Not Found"}
[EXAMINER] C9 perturb HIT → predict also passes (rule A).                 ⏱ 1 min
```

**C1 dict lookup: slow lane, JavaScript trap**
```
[ENGINE]   T1 · C1 · perturb (placement) · trap on: from JS
TUTOR:     store.py line 14 is `return _links.get(code)`.
           Change it to `return _links[code]` and open an unknown code, /nope. What happens?
SAM:       It returns undefined... I mean None. Then line 25 sees None and raises
           the 404. Same as before.
[ENGINE]   runs it → 500 Internal Server Error · KeyError: 'nope'
[EXAMINER] C1 perturb MISS · trap confirmed: JS obj[k] gives undefined,
           Python d[k] raises. Drop to predict.
TUTOR:     The server crashed with KeyError before line 25 ever ran.
           Predict this, then we run it:
             d = {"a": 1}
             print(d.get("b"), d.get("b", 0))
             print(d["b"])
SAM:       None 0, and then a KeyError.
[ENGINE]   runs it → None 0 / KeyError: 'b'
[EXAMINER] C1 predict HIT. Perturb stays open → asked again later with a fresh question (rule B). ⏱ 4 min
```

**C15 redirect codes: brand new; Sam runs the experiment**
```
[ENGINE]   T1 · C15 · perturb (placement)
TUTOR:     Line 28 answers 307. If it were 301 and you visit the same short link
           3 times in one browser, how many clicks does the server count?
SAM:       3. A redirect is a redirect.
TUTOR:     Try it: switch to 301, visit 3 times, then count the
           "GET /aZ3k9Q" lines in the server log.
SAM:       ...only one line. The other two never reached the server?
[EXAMINER] C15 perturb MISS (not a trap, just new).
TUTOR:     Open the browser's network tab and visit once more. What does it say
           next to the request?
SAM:       "(from disk cache)". So the browser remembers a 301 and skips us.
           A shortener that counts clicks can't use 301.
[EXAMINER] Right reasoning, but it came after the reveal → no HIT (rule B). Drop to predict.
TUTOR:     With 307, what does the browser do on the 4th visit?
SAM:       It asks our server again, every time.
[EXAMINER] C15 predict HIT. Perturb stays open.                             ⏱ 6 min
```

**C13 Counter: fast lane**
```
TUTOR:     stats.py. If line 7 were `_clicks[code] = 1`, what does top(3) return
           after record_click("x"), record_click("x"), record_click("y")?
SAM:       [("x", 1), ("y", 1)]. It overwrites instead of adding.
[ENGINE]   runs it → [('x', 1), ('y', 1)]
[EXAMINER] C13 perturb HIT → predict passes too.                            ⏱ 1 min
```

**After T1 (12 min):** the same task, but different speeds per concept.
```
                 predict  perturb  produce  transfer   lane
 C9  decorators     ✓        ✓        ·        ·       fast  (1 question)
 C13 Counter        ✓        ✓        ·        ·       fast  (1 question)
 C1  dict lookup    ✓        ✗        ·        ·       slow  (JS trap)
 C15 redirects      ✓        ✗        ·        ·       new
```

**The engine picks the next task in the stretch zone:** most concepts known, only 1–2 new.
```
 T2  add GET /top     needs C9 ✓✓  C13 ✓✓              → nothing new   ✓ pick (a first real change)
 T3  planted bug      needs C0 ?   C2 ?   C3 ?         → 3 untested
 T4  expiry           needs C2 ?   C12 ?  C16 ?        → 3 untested
```

---

## 5. T2: first change (the task finds a concept the bank missed)

```
SAM:       (adds the route at the bottom of app.py)
               @app.get("/top")
               async def top() -> list:
                   return stats.top(5)
[ENGINE]   test_top FAILS → GET /top returns 404 {"detail": "unknown code"}
SAM:       404 "unknown code"? My function doesn't even say that.
TUTOR:     Right, that message comes from line 26, in follow(). So which function ran,
           and what was `code`?
SAM:       follow() ran with code = "top"! /{code} matched first.
TUTOR:     What would give /top a chance?
SAM:       Register /top before /{code}.
[ENGINE]   test_top passes
[EXAMINER] C9, C13: produce HIT (in a real task).
           NEW concept, not in the bank: "routes match in order; a path parameter like
           /{code} catches anything registered after it" → added as C17 at app.py:22.
           C17 produce = provisional (found with a hint, rule C).            ⏱ 9 min
```

**What this shows:** the bank grows from real work. Nobody predicted this concept, but the task surfaced it.

---

## 6. T3: fix a planted bug (JavaScript trap, a detour, transfer, PR review, TIL)

The engine plants a bug in a **copy** of store.py, a one-line change from the original:

```python
 6  def save(code: str, url: str, tags: list[str] = []) -> dict:
 7      tags.append("new")                      # mark fresh links
 8      link = {"url": url, "tags": tags,
 9              "created": datetime.now(timezone.utc)}
```

**The trap**
```
[ENGINE]   T3 · C3 · perturb (placement) · trap on: from JS
TUTOR:     test_tags_not_shared fails. Don't fix anything yet.
           After save("a", "x") then save("b", "y"), what is _links["a"]["tags"]?
SAM:       ["new"]. Each call gets its own fresh [], like default params in JS.
[ENGINE]   runs it → ['new', 'new']
[EXAMINER] C3 perturb MISS · trap confirmed: JS evaluates defaults at every call,
           Python evaluates them ONCE, when `def` runs.
           It could also be a missing C0 (two names, one list) → check C0 first.
[ENGINE]   pushes a detour to C0 and saves the paused question exactly
```

**The detour: 2 questions, and it wasn't the gap**
```
TUTOR:     Side question. a = [1]; b = a; b.append(2). What is a?
SAM:       [1, 2]. Both names point at the same list, like JS arrays.
TUTOR:     Now b = b + [3] instead of append. What is a?
SAM:       Still [1, 2]. + builds a new list, and b points at that one now.
[EXAMINER] C0 perturb HIT → predict passes too. C0 was NOT the gap.         ⏱ 2 min
[ENGINE]   pops the detour → back to the paused question
```

**Back on the bug: Sam experiments instead of being told**
```
TUTOR:     Back to save(). You just showed two names can share one list.
           If save() is called 100 times without tags, how many lists did `tags=[]` create?
SAM:       ...one? Is the [] made when Python reads the def, not on each call?
TUTOR:     Don't trust me. In a fresh shell, print(save.__defaults__) before and after two calls.
SAM:       ([],) ... then (['new', 'new'],). The list lives ON the function!
[EXAMINER] Good reasoning, but it followed an experiment that showed the answer → no HIT yet (rule B).
TUTOR:     Fresh one. If the default were `tags: tuple = ()` and line 7 were
           `tags = tags + ("new",)`, would links still share?
SAM:       No. Tuples can't change, and + makes a new tuple on every call.
[ENGINE]   runs it → nothing shared
[EXAMINER] C3 perturb HIT (fresh question) → predict passes too.
```

**The fix (produce)**
```python
 6  def save(code: str, url: str, tags: list[str] | None = None) -> dict:
 7      tags = [*(tags or []), "new"]           # a new list on every call
```
```
[ENGINE]   test_tags_not_shared passes · all other tests pass
[EXAMINER] PR-style review:
           ✓ the bug is fixed, not hidden (no special case in the test)
           ✓ side effect: it no longer mutates a list the CALLER passed in
           → C3 produce HIT · C2 produce HIT (`tags or []`, written unaided)
```

**Transfer: using it where it wasn't taught**
```
TUTOR:     app.py line 12: NewLink has `tags: list[str] = []`. Same bug there?
SAM:       Yes. It's the same thing, a default [].
[ENGINE]   runs it → NewLink(url="a").tags is NewLink(url="b").tags → False
[EXAMINER] C3 transfer MISS: the rule is about FUNCTION defaults; pydantic creates a
           fresh value for each model. Sam doesn't know where the rule stops yet.
TUTOR:     They're different lists. So what's different between a function default
           and a pydantic field default?
SAM:       The function default is made once, at def. Pydantic must copy it for every model.
[EXAMINER] Understood after the reveal → transfer stays open; review will ask a new one.
```

**TIL in Sam's own words**
```
TUTOR:     Write today's TIL in 2–3 lines.
SAM:       "Python runs default arguments once, when def runs. A mutable default
            ([] or {}) is shared by every call. Use None and build the list inside.
            Pydantic fields are different: they copy the default for each model."
[EXAMINER] Own words, says WHY, and names the boundary → counts as explain evidence.    ⏱ T3: 24 min
```

---

## 7. T4: modify (a brand-new concept → example first)

```
[ENGINE]   T4 · C16 · perturb (placement)
TUTOR:     store.py line 8 uses datetime.now(timezone.utc). If it were datetime.now(),
           what would change?
SAM:       I've never used Python datetime. No idea.
[EXAMINER] C16 brand new → teaching mode: EXAMPLE FIRST.
           (For a brand-new concept Sam will have to WRITE, an example beats struggling from zero.)
TUTOR:     Read this, then I'll ask:
             from datetime import datetime, timedelta, timezone
             now   = datetime.now(timezone.utc)      # "aware": knows its timezone
             later = now + timedelta(days=7)
             later > now                             # True
           Predict: datetime.now() > later → ?
SAM:       False?
[ENGINE]   runs it → TypeError: can't compare offset-naive and offset-aware datetimes
TUTOR:     Neither. It refuses. Why would Python refuse instead of guessing?
SAM:       A naive time doesn't say which timezone it's in, so Python can't know which is later.
[EXAMINER] C16 predict MISS → understood after reveal. Re-checked during the task.
```

**Sam builds the feature**
```python
def save(code: str, url: str, tags: list[str] | None = None,
         expires_in_days: int | None = None) -> dict:
    link = {"url": url, "tags": tags or [], "created": datetime.now(timezone.utc)}
    if expires_in_days:                                    # ← the reviewer flags this
        link["expires"] = link["created"] + timedelta(days=expires_in_days)
    _links[code] = link
    return link

# in follow():
    if "expires" in link and datetime.now(timezone.utc) > link["expires"]:
        raise HTTPException(status_code=410, detail="link expired")
```
```
[ENGINE]   test_expiry passes (frozen clock)
[EXAMINER] PR-style review:
           ✓ aware datetimes on both sides → C16 produce HIT (unaided, in a real task)
             → predict and perturb pass too (rule A)
           ✗ expires_in_days=0 is falsy → that link NEVER expires. Intended?
             → C2 transfer MISS (Sam knew `tags or []`, but missed it on an int)
TUTOR:     Your reviewer flagged the `if expires_in_days:` line. What does `if 0:` do?
SAM:       Skips it. 0 is falsy (in JS too, actually). I meant "was it given?",
           so `if expires_in_days is not None:`.
[ENGINE]   new test test_expiry_zero passes
[EXAMINER] C2 transfer fixed with a hint → stays open (rule C).            ⏱ T4: 31 min
```

---

## 8. T5: assemble (the async trap)

```
SAM:       (in create_link)  notify(settings.webhook_url, {"code": code})
[ENGINE]   the mock endpoint got 0 calls ·
           RuntimeWarning: coroutine 'notify' was never awaited
SAM:       But I called it!
[EXAMINER] C10 MISS · trap confirmed: in JS, calling an async function starts it.
           In Python it only creates a coroutine; nothing runs until it is awaited.
TUTOR:     The warning says "never awaited". In Python, what does calling an
           async def actually give you back?
SAM:       ...a coroutine object, not something running. So: await notify(...).
[ENGINE]   the mock endpoint got 1 call
[EXAMINER] C10 produce: provisional (fixed with a hint, rule C). A later task re-checks it unaided.
```

---

## 9. Next day: spaced review (under a minute per concept)

```
[ENGINE]   Day 2. Due: C3 transfer (open) · C2 transfer (open).
TUTOR:     def remember(item, seen=set()):
               seen.add(item)
               return len(seen)
           remember("a"), remember("b"), remember("a") → ?
SAM:       1, 2, 2. One shared set across all the calls.
[EXAMINER] C3 transfer HIT (new place, unaided) → C3 OWNED. Next review in 3 days.   ⏱ 40 s
TUTOR:     clicks = 0
           if clicks:
               print("popular")
           What prints?
SAM:       Nothing. 0 is falsy. For "was it set?" I'd write `is not None`.
[EXAMINER] C2 transfer HIT → C2 OWNED.                                      ⏱ 30 s
```

---

## 10. T6: build, ally mode (the tutor switches voice)

```
[ENGINE]   T6 is a BUILD task → TUTOR switches to ALLY mode: pair with Sam, answer directly.
SAM:       How do I get rows back as dicts from sqlite3?
TUTOR:     Set conn.row_factory = sqlite3.Row, then row["url"] works.
           Want me to sketch the table?
SAM:       Yes.
TUTOR:     CREATE TABLE links(code TEXT PRIMARY KEY, url TEXT NOT NULL,
                              tags TEXT, created TEXT, expires TEXT)
           Store tags as JSON text. Keep store.py's function names the same,
           so app.py doesn't change at all.
   ... Sam builds it, asks 4 more direct questions, gets 4 direct answers ...
[ENGINE]   test_survives_restart passes
[EXAMINER] C14 produce: provisional (ally help, rule C).
           Glossed over: "why JSON text for tags?" → saved for a SOLO task.
```

In ally mode nobody plays Socrates. Finishing is the goal. What was glossed over gets tested in SOLO.

---

## 11. T7: solo (blank page, no spec; grade intent, defend forks)

```
[ENGINE]   T7: codes.py is hidden. Blank page. No spec, no tests shown.
TUTOR:     Rebuild short-code generation. Every choice is yours.
SAM:       (writes it: secrets.choice over 62 characters, 6 long, and
            `while True:` until a code is free)
[EXAMINER] Grades INTENT, not "same as the original":
           ✓ codes are unguessable. Asked "why secrets, not random?" →
             "private links like shared docs must not be guessable" → C7 transfer HIT → C7 OWNED
           ✗ `while True:` → what happens when the code space is nearly full?
SAM:       ...it would loop forever. I'd cap it and raise, so we notice.
[EXAMINER] C8 transfer MISS (found only after the question) → stays open.
           T7 counts as done; C8 comes back in review.
```

SOLO can fail on one concept. That's fine: the miss goes back into review, not back to the start.

---

## 12. Behind the scenes: what each agent actually saw (T3, first turn)

**TUTOR's packet:** small, one concept, no learner history beyond this concept.
```json
{
  "agent": "TUTOR",
  "mode": "adversary",
  "task":  {"id": "T3", "goal": "links must not share tags",
            "check": "tests/test_links.py::test_tags_not_shared"},
  "frame": {"concept": "C3", "name": "default arguments are evaluated once",
            "rung": "perturb", "level": "untested (placement)",
            "traps_on": ["from JS: defaults run at every call"]},
  "code":  {"file": "store.py (task copy)", "lines": "6-9"},
  "this_concept_so_far": [],
  "paused_question": null,
  "tools": ["read_code", "run_code"]
}
```

**EXAMINER: input.** It doesn't see the tutor's chat or Sam's claims about themselves.
```json
{
  "agent": "EXAMINER",
  "task": "T3", "concept": "C3", "rung": "perturb",
  "question": "after save('a','x') then save('b','y'), what is _links['a']['tags']?",
  "answer": "['new'] — each call gets its own fresh [], like default params in JS",
  "run": {"actual": "['new', 'new']"},
  "hints_given": 0,
  "traps_on": ["from JS: defaults run at every call"],
  "prereqs": ["C0"]
}
```

**EXAMINER: output.** The engine acts on it: records the MISS and pushes the C0 detour.
```json
{
  "verdict": "MISS",
  "evidence": "predicted ['new'], actual ['new', 'new']",
  "diagnosis": {"kind": "interference",
                "note": "JS evaluates defaults per call; Python once at def"},
  "check_first": "C0"
}
```

---

## 13. Sam's concept map at the end

```
                        predict perturb produce transfer   time     lane
 C9  decorators            ✓       ✓       ✓       ·       3 min    fast
 C13 Counter               ✓       ✓       ✓       ·       3 min    fast
 C0  names → objects       ✓       ✓       ·       ·       2 min    fast (detour, not the gap)
 C1  dict lookup           ✓       ✗       ·       ·       4 min    slow · JS trap · re-probe due
 C15 redirect codes        ✓       ✗       ·       ·       6 min    new · re-probe due
 C17 route order           ·       ·       ~       ·       9 min    found during T2
 C3  mutable defaults      ✓       ✓       ✓       ✓      25 min    slow · JS trap · OWNED
 C2  truthiness            ✓       ✓       ✓       ✓       6 min    OWNED (missed once on an int)
 C16 aware datetimes       ✓       ✓       ✓       ·      12 min    brand new · example first
 C10 async / await         ·       ·       ~       ·       8 min    slow · JS trap
 C14 module state          ·       ·       ~       ·       (T6)     provisional (ally help)
 C7  secrets vs random     ✓       ✓       ✓       ✓       (T7)     OWNED (defended in solo)
 C8  bounded retry         ✓       ✓       ✓       ✗       (T7)     open (missed in solo)

 ✓ HIT    ✗ missed, open    ~ provisional (done with help)    · not tested yet
```

Same learner, same codebase: 2–3 minutes for some concepts, 25 for others. **That's why there is no global phase.**

---

## 14. Who did what

| who | in this example |
|---|---|
| CARTOGRAPHER | ran once: overview, 14 concepts, 7 tasks. Never saw Sam. |
| ENGINE | suggested tasks in Sam's stretch zone, planted the bug in a copy, ran every prediction and test, pushed and popped the C0 detour, scheduled the reviews |
| TUTOR | asked before telling (adversary); gave an example first only for brand-new C16; pointed at evidence instead of handing over fixes; answered directly in T6 (ally) |
| EXAMINER | turned runs and tests into HIT/MISS; caught the 3 JS traps; refused credit after reveals; reviewed code like a PR; graded intent in SOLO |
| SAM | predicted before running; ran experiments (server log, `__defaults__`, network tab); fixed real code; wrote TILs; asked direct questions in T6; defended choices in T7 |

---

## 15. Research behind each behaviour

| behaviour in the example | research pattern |
|---|---|
| everything happens inside a real task (T1–T7) | learn on demand through concrete tasks (Karpathy, Meta bootcamp, Google, Brandt) |
| predict → run → compare; Sam runs experiments | run it, change it, watch (Carmack, GitHub, Feathers, Dagenais) |
| C9 in 1 minute, C3 in 25 | speed differs per concept (Carroll; Kalyuga) |
| JS traps probed first | prior knowledge misleads (Shrestha 2020) |
| TILs count as evidence | write it in your own words (Karpathy, GitHub, Willison) |
| day-2 review in under a minute | spaced repetition (Sivers; Dunlosky) |
| a passing test and a PR review close every task | progress validation (Dagenais; Peterman) |

---

## 16. Open questions this example raises

1. **Rule A:** should a HIT on a higher rung really pass all the lower ones? It makes placement fast, but it trusts the jump.
2. **Planted bugs:** OK to plant them on a learning-branch copy and never touch the learner's main code?
3. **Ally-mode credit:** OK that ally-mode work stays provisional (~) until a solo task or review confirms it?
4. **Background profile:** OK that it is only a hint for which traps to probe first, and never marks anything known?
