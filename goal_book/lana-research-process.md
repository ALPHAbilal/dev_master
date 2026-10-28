# Lana: the research process

Draft, 2026-10-28. Claude's proposal, not decided yet: change anything.
It stays in dev_master, outside `lana/`, like `lana-decisions.md`.

One research session is **one agent loop**, with the learner inside it at fixed
moments. The agent loads its skills when it needs them; the harness (Lana's
background and contract) holds the rules the model must not decide alone.

Example used throughout: *"What are the basics of Amazon S3?"*

## The loop

```
 START   a question arrives: the learner types it, or the Goal Book agent isn't sure
   │
 1 FRAME      the agent proposes what to find and what the course will get;
   │          the learner edits                     ◆ GATE: the learner approves the plan
   │
 2 SEARCH     wide, then narrow; results get verdicts on the search page itself
   │
 3 SPLIT      only when there's too much to read: the learner reads the key pages,
   │          the agent reads the rest in the background
   │                                                ◆ GATE: only the learner opens tabs
   │
 4 READ       the learner points to the answer and keeps finds; the agent compares
   │                                                ◆ GATE: only the learner keeps a find
   │
 5 CHECK      the plan against the finds; a gap ──► back to 2
   │
 6 FIT        find by find, into the course         ◆ GATE: the learner approves each change
   │
 END     a record: question · plan · queries · pages · finds · the path back to each passage
```

## Who does what

```
 STEP     LEARNER                          AGENT                              DIAL TODAY
 frame    edits and approves the plan      proposes the plan                  together
 search   writes the queries, judges       improves queries, runs searches,   learner leads
          results                          proposes verdicts
 split    reads the key pages              reads the rest in the background   together
 read     points and keeps                 compares, frames, explains         learner leads
 check    agrees or adds a gap             finds the gaps                     agent leads
 fit      decides                          proposes the frame and the place   together
```

**The dial moves with skill.** After three good queries in a row, the agent
stops suggesting better ones and only runs them. When the learner's picks keep
matching the agent's, it stops comparing. The agent hands over what the learner
has earned.

## The harness: rules the model can't break

```
 THE AGENT CAN, ALONE          search · read in the background · label results · point ·
                               highlight · compare · ask · propose
 ONLY WITH THE LEARNER         open a tab · keep a find · approve the plan · change the course
 ANYTIME, THE LEARNER CAN      ask in the chat · send a selection to the agent · overturn a
                               verdict · stop the session
 LIMITS                        searches and pages per session: to decide
```

The agent's skills, loaded when needed: search · label results · read a page ·
point to a part · ask the learner · compare picks · keep · fit into the course.

## The steps

For each step: what happens, what shows on the page, what shows in the panel,
and when the agent stops to ask. "To decide" marks what we haven't settled.

### 1 · Frame

- **What happens:** the agent turns the question into what we need to find
  (what S3 is for · buckets and objects · how you pay) and what the course will
  get (Definition · Diagram · Practice). The learner adds, removes, rewords.
- **Gate:** the learner approves the plan before any search.
- **On the page:** nothing.
- **In the panel:** to decide.
- **The agent stops when:** the plan is proposed.

### 2 · Search

- **What happens:** the learner writes the first query; the agent says how to
  make it better, then runs it. Start wide, then narrow.
- **On the page:** the results get verdicts on the search page itself:
  read · later · skip. The learner can overturn any verdict.
- **In the panel:** to decide.
- **The agent stops when:** to decide.

### 3 · Split

- **What happens:** only when there's too much to read. The learner opens the 1
  or 2 pages that matter most; the agent reads the rest in the background
  (Firecrawl) and reports what they add.
- **Gate:** only the learner opens tabs.
- **On the page:** to decide.
- **In the panel:** to decide.
- **The agent stops when:** to decide.

### 4 · Read

- **What happens:** on each page the learner opened, the learner points to
  where the answer is. The agent compares and frames its own pick if it
  differs, saying why. The learner keeps finds: text, code, image, table.
- **Gate:** only the learner keeps a find.
- **On the page:** the frame, the highlight, the scroll arrow, the selection
  menu (built).
- **In the panel:** to decide.
- **The agent stops when:** after each page.

### 5 · Check

- **What happens:** the agent holds the plan against the finds
  (what S3 is for ✓ · buckets ✓ · how you pay ✗). A gap sends the session back
  to Search, with a narrower query.
- **On the page:** nothing.
- **In the panel:** to decide.
- **The agent stops when:** a gap is found.

### 6 · Fit

- **What happens:** find by find, in conversation, with the course open in its
  own tab: the agent proposes a frame and a place, the learner decides.
- **Gate:** the learner approves each change to the course.
- **On the page:** the course tab shows the proposed block where it would land.
- **In the panel:** to decide.
- **The agent stops when:** each find.

## Open questions

- Searches and pages per session: how many before the agent stops?
- When is it "too much to read" for Split: how many good results?
- How does the dial remember the learner's skill across sessions?
- Does Fit always follow, or can a session end after Check?

## Where the ideas come from

```
 co-planning, pause and take over, action guards   Magentic-UI, Microsoft Research
 three modes: you browse · once · automatic        Comet Assistant, Perplexity
 from a conclusion back to its exact sources       InterDeepResearch
 wide then narrow · source quality rules           Anthropic, multi-agent research system
 one agent loop, skills on demand, the harness     Anthropic, "When to fold subagents into
 holds budgets and write gates                     your main agent loop", 2026-10-22
```

- https://www.microsoft.com/en-us/research/blog/magentic-ui-an-experimental-human-centered-web-agent/
- https://www.perplexity.ai/hub/blog/comet-assistant-puts-you-in-control
- https://www.alphaxiv.org/abs/2603.12608
- https://www.anthropic.com/engineering/multi-agent-research-system
- https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop
