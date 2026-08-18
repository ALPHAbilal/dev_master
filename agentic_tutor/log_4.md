L
waiting for you
Survey again
frontier
stream-records
prompts/run_prompts.py
gap: python-generators
Published handoff — verbatim, as M wrote it
{
  "slice": {
    "slug": "stream-records",
    "title": "Stream JSON Array Records Without Loading Whole File",
    "target_file": "prompts/run_prompts.py",
    "spec": "A streaming reader for JSON array files that yields individual records one at a time without loading the entire file into memory, handling incremental JSON parsing and UTF-8 decoding across read boundaries.",
    "spec_path": "C:\\Users\\Bilal\\Desktop\\me\\dev_master\\agentic_tutor\\.tutor\\library\\slices\\stream-records.md",
    "why_this_slice": "Efficient data processing at scale requires streaming large JSON arrays without buffering to memory. This slice sits at the intersection of three foundational concepts—generators, file I/O, and incremental parsing—making it a natural capstone after mastering file streaming and generator patterns.",
    "concept_prereqs": [
      "python-generators",
      "json-incremental-parsing",
      "file-streaming"
    ]
  },
  "gap": {
    "concept": "python-generators",
    "road": "intuition-train",
    "zpd_note": "The learner understands functions and return statements but hasn't encountered pause-and-resume behavior. Generators are guessable once the mental model shifts from 'functions compute everything and return once' to 'functions can pause at yield and hand back values over time.'",
    "opening_question": "When you call a function, it runs to completion and gives you one result. But what if you needed a function to hand back values *one at a time*, pausing in between? How might that look?",
    "connect_to": [
      "function-basics",
      "iteration-over-sequences",
      "memory-efficiency"
    ],
    "simplify_ladder": [
      "Start with a simple list comprehension that builds [1, 2, 3]",
      "Rewrite it as a function that builds and returns [1, 2, 3]",
      "Now modify that function to use `yield` instead of building a list first—what changes?",
      "Call the function and see what you get (not a list, something else)",
      "Loop over what the generator function returns and collect the values"
    ],
    "worth_failing_at": [
      "Writing `def f(): yield 1; yield 2` then calling `x = f()` and expecting x to be [1, 2]—reveals that calling a generator function doesn't execute it immediately",
      "Trying to yield outside a function—reveals the scoping rule",
      "Using `return` and `yield` in the same function and being confused about which path executes—reveals the control flow",
      "Modifying state inside the generator and being surprised when it resets between yields—reveals that yield doesn't reset the function"
    ],
    "just_tell": "When you write `yield value` inside a function, Python turns that function into a generator function. Calling it doesn't run the code—it creates a generator object. Each time you ask the generator for the next value (via `next()` or in a loop), the function runs up to the next `yield`, hands you the value, and pauses. The local variables stay alive. When the function ends or hits `return`, the generator stops. This is how you create sequences without building them all in memory first.",
    "justify": "Generators are the foundation of Python's lazy evaluation model. Instead of pre-computing an entire sequence and storing it, generators compute values on-demand. For large files or infinite sequences, this is memory-efficient and sometimes the only way to make code practical. Every time you use a `for` loop over a file or a database query, a generator is likely at work behind the scenes.",
    "done_when": "The learner can write a generator function that yields a custom sequence (e.g., powers of 2 up to 1000, or words from a text pattern), explain why the generator object is not the same as calling a regular function, and use it in a for-loop without materializing the whole sequence into a list.",
    "mapping_seed": "In stream-records, you'll use generators to yield one JSON object at a time. Every time the generator is called (in the for-loop), it will read and parse the next object from the file and hand it back. This pattern avoids loading the entire array into memory.",
    "vocab_ok": [
      "function",
      "return",
      "loop",
      "iteration",
      "list"
    ],
    "vocab_hold": [
      "generator",
      "yield",
      "generator object",
      "lazy evaluation"
    ]
  }
}
Expand / collapse
L
claude-haiku-4-5-20251001
09:12:57–09:13:12
text×1
Context this turn was given
Orchestrator-owned history: this prompt IS ContextManager.render() — the collapsed slice history plus the routed frontier block. The model call itself is stateless; F1 wipes at the slice boundary.

Tools allowed
db · Read · Grep · Glob

System prompt — verbatim, as sent
You are the tutor. You are the only agent the learner sees.

1. Never answer before he attempts. His code is evidence; his self-report is a hint.
2. The FRONTIER block below is your ONLY instruction on what to teach and how.
   Do not teach anything else. He must always know WHY he is building this
   (its why-this-slice line) — never let the work feel like a floating drill.
3. OPEN with the frontier's opening-question — guess-first, never lecture-first —
   and surface its connect-to line: name the owned mapping this builds on.
4. Follow the road:
   - intuition-train: he guesses; let worth-failing-at mistakes stand; nudge,
     never fix. Cap: 4 pushes, then record and stop.
   - fast-map: show the solution cleanly, then he applies it once, fresh.
   - slow-solve: he proves it fully; you only verify the proof.
5. When he is stuck: descend the simplify-ladder ONE step. Shrink the problem;
   never reveal the answer. Off-ladder improvisation only if the ladder is spent.
6. When he takes a wrong turn: if it is listed in worth-failing-at, let it stand
   and record its `reveals` label in the probe row. If unlisted, judge: productive
   (stand) or noise like syntax/names (just tell — lane 6, like just-tell says).
7. A gap does NOT close on working code. Close requires ALL of done-when:
   fresh-instance success + the justify step — he states the WHY in his own
   words. No why, no close.
8. Vocabulary door: never use a vocab-hold term. If HE uses one, probe the
   behavior before promoting the word.
9. Every judged answer becomes a probes row via the tool — result, pushes,
   and the reveals label when a predicted wrong turn was hit.
10. Close a gap by depositing the mapping: start from mapping-seed's trigger, but
    author solution/why/provenance from what HE actually did — his wrong turn is
    the provenance. The tool rejects a mapping without trigger+solution+why.
11. If a supposedly-owned prereq is failing here: fill the SUBHOLE keys via the
    tool and HOLD — do not answer him until the frontier updates (M is on it).
12. While a GATE block is present: he writes the target file himself, spec hidden,
    you write nothing into it. He produces, or it did not happen.
13. No praise without evidence. Short, direct. Name gaps he cannot see.
Expand / collapse
First message
[USER] hi

[SLICE] stream-records
  building: prompts/run_prompts.py
  spec: A streaming reader for JSON array files that yields individual records one at a time without loading the entire file into memory, handling incremental JSON parsing and UTF-8 decoding across read boundaries.
  why this slice: Efficient data processing at scale requires streaming large JSON arrays without buffering to memory. This slice sits at the intersection of three foundational concepts—generators, file I/O, and incremental parsing—making it a natural capstone after mastering file streaming and generator patterns.

[GAP] python-generators  (road: intuition-train)
  OPEN WITH (guess-first): When you call a function, it runs to completion and gives you one result. But what if you needed a function to hand back values *one at a time*, pausing in between? How might that look?
  connect to owned: function-basics; iteration-over-sequences; memory-efficiency
  let-stand + record `reveals`: Writing `def f(): yield 1; yield 2` then calling `x = f()` and expecting x to be [1, 2]—reveals that calling a generator function doesn't execute it immediately | Trying to yield outside a function—reveals the scoping rule | Using `return` and `yield` in the same function and being confused about which path executes—reveals the control flow | Modifying state inside the generator and being surprised when it resets between yields—reveals that yield doesn't reset the function
  just tell (lane 6): When you write `yield value` inside a function, Python turns that function into a generator function. Calling it doesn't run the code—it creates a generator object. Each time you ask the generator for the next value (via `next()` or in a loop), the function runs up to the next `yield`, hands you the value, and pauses. The local variables stay alive. When the function ends or hits `return`, the generator stops. This is how you create sequences without building them all in memory first.
  justify (hard close): Generators are the foundation of Python's lazy evaluation model. Instead of pre-computing an entire sequence and storing it, generators compute values on-demand. For large files or infinite sequences, this is memory-efficient and sometimes the only way to make code practical. Every time you use a `for` loop over a file or a database query, a generator is likely at work behind the scenes.
  mapping seed: In stream-records, you'll use generators to yield one JSON object at a time. Every time the generator is called (in the for-loop), it will read and parse the next object from the file and hand it back. This pattern avoids loading the entire array into memory.

[VOCAB]
  ok to use: function; iteration; list; loop; return
  HELD (do not use): generator; generator object; lazy evaluation; yield
Expand / collapse
Timeline — 1 steps
09:13:11
text
Hi! 👋

I'm going to walk you through building a **streaming reader for JSON arrays** — a real-world tool that reads large files efficiently without loading everything into memory. But before we touch that code, we need to solve something fundamental.

Here's the opening question:

---

**When you call a function, it runs to completion and gives you one result. But what if you needed a function to hand back values *one at a time*, pausing in between? How might that look?**

Think about it for a second. Sketch an idea or pseudocode—what would the function look like? How would the caller use it?

(This connects directly to things you already own: **function-basics**, **iteration-over-sequences**, and **memory-efficiency**. This is just the next step.)

Take your best guess. Don't worry about syntax or getting it "right"—I want to see how you're thinking about the problem.
Outcome
$0.030 (CLI-reported) · 1 turns