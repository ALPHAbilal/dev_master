# Handoff: continue here

Updated 2026-10-12, end of the session. Claude's memory stays on the laptop it was made on. This file carries everything a new session needs, including how to work with the user (§4).

## 0. Where we stopped

We are closing the design holes one by one. The user is answering **hole 19** (`LEGO.md` §16). The question was asked and explained, and the user will answer it on the other computer.

**Hole 19 · a concept can lose its check and never get it back**

```
 the rules today
 1  a box, once ☑, stays ☑ forever in the task                     LEGO.md §12
 2  a concept is checked = all its boxes ☑                         LEGO.md §10
 3  a WRONG_IDEA or GAP about a checked concept ──► back to ☐      the user, 2026-10-11
 4  the task closes only when every concept is checked             LEGO.md §10

 turn 8    the learner explains why label is unbound for a guest; the evaluator: met
           box 3 · explains why label is unbound for a guest        ☑ forever
           concept 15 · loop variables outlive the loop             ☑ checked
 turn 10   learner: "so after any loop, the variable is None?"
           orchestrator: WRONG_IDEA about
           concept 15 · loop variables outlive the loop             ☐ unchecked
 turn 11+  box 3 · explains why label is unbound for a guest        still ☑ forever
           the evaluator only judges boxes that aren't ☑ ──► nothing left to judge
           concept 15 · loop variables outlive the loop             ☐ stuck forever
           task 3 · guests always get the generic error             never closes
```

```
 a. the box unticks too        the learner shows it again ──► ☑ ──► the concept ☑
 b. the box stays ☑, but can   while its concept is ☐, the evaluator may      ← Claude's pick
    be judged again            judge it again; met ──► the concept ☑ again
 c. a concept never unchecks   the wrong idea goes into the difficulties only;
                               this reverses the user's 2026-10-11 decision
```

How the task sheet reaches each agent, which the user asked about (`LEGO.md` §10, `BACKEND_SPEC.md` §4):

```
 the database rows ──► code builds the task sheet as text, every turn
                         ├──► the orchestrator: pasted into its prompt as the fact task_sheet
                         ├──► the tutor: pasted into its system prompt
                         ├──► the evaluator: never
                         └──► the screen: ☑ and ☐ only
 "checked" is a yes or no inside it; checked and unchecked concepts are both
 always shown; code's gate closes the task only when every concept is checked
```

**To resume with Claude,** open Claude Code in `dev_master` and say:

> Read `new_completly_desighn/HANDOFF.md` and follow §4. We continue at hole 19: I answer a, b or c.

## 1. The queue, in order

One numbering only: `LEGO.md`'s. Never renumber.

```
 1  hole 19       a concept can lose its check and never get it back   ◄ now
 2  hole 4        the link from an issue to a concept is the orchestrator's guess
 3  hole 13       overlaps: showing_mastery with UNCERTAIN; frustration as a kind of
                  work and as a why on the stuck ladder
 4  hole 16       a box explained inside an issue is ticked only on the next turn
 5  hole 18       a GAP about a concept writes a difficulty, but a GAP has no
                  what_went_wrong
 6  the tutor's   write the NEW tutor pieces now, or during the build?
    new pieces
 7  choice 1–7    Claude's own choices, written up without the user and marked
                  "NOT DECIDED" wherever they appear (LEGO.md §16):
                  1 which issues the evaluator judges
                  2 no bouncing: a new "now" only when something changes
                  3 priority 4 vs 5: a side question = 5
                  4 the pick order: wish · 1 to 4 · the focus's own work · 5
                  5 on the task itself, the tutor's style = the turn's kind
                  6 a new map line "↳ Picked up"
                  7 IDs in the API: "task-3", "issue-1"
 then           update the docs, walk task 3 through the final design, then build
                step 1 (BACKEND_SPEC.md §20)
```

## 2. Where we are

```
 [x] the agentic layer designed                      LEGO.md 0.20
 [x] the Claude mapping checked                      BUILD_WITH_CLAUDE.md
 [x] the frontend rebuilt for the new design         agentic_tutor/frontend, demo mode
 [x] the backend spec written                        BACKEND_SPEC.md 0.3
 [x] the 4 decisions of BACKEND_SPEC.md §22
 [~] the holes, one by one                           §1: the queue
 [ ] build steps 1 to 9                              BACKEND_SPEC.md §20
```

Read in this order:

```
 1  HANDOFF.md                  this file
 2  LEGO.md                     the agentic layer, draft 0.20; §16 has every decision, every
                                hole and choices 1 to 7; §17 is the waiting room
 3  BUILD_WITH_CLAUDE.md        every piece on the Claude API and the Agent SDK, checked
 4  FRONTEND.md                 the learner's screen, draft 0.6: built; its contract is §7–§8
 5  BACKEND_SPEC.md             the backend to build next, draft 0.3; its §0 lists what is open
 6  t3-agent-walkthrough.html   task 3, turn by turn, for every agent; drawn from LEGO.md 0.19,
                                so it still shows quotes and saved issues
                                https://claude.ai/artifact/ETjegAK3D4uBfi8jkezNFv
 7  sidebar-variations.html     the three minimalist styles; Quiet (variation 1) was chosen
                                https://claude.ai/artifact/U2LqzQA7FrtVQHErkJmZnX
```

Old designs are in `archive/` (see `archive/README.md`). Don't build from them.

## 3. Decided on 2026-10-12

```
 Supabase        restored
 sign-in         a link by email only
 the backend     tutor_graph replaces tutor_v2 completely, in the current Fly app
 quotes          removed everywhere: the evaluator answers met | not met | unclear only;
                 no learner_words anywhere; the tutor has the exact words in its history
 kinds of work   names, not numbers: "kind_of_work": "debugging"
 labels          every ID in full: task 3, issue 1, never T3 or I1; a model reads and
                 writes word + number + name; engine/names.py makes every label
 the waiting     LEGO.md §17: every need is an issue; ordered by priority 1 to 5 (the
 room            order is the user's); the orchestrator names issues and gives the
                 green flag, code does the rest; the learner wins a switch; any number
                 of switches, nothing lost; left unfinished ──► on hold; issues inside a
                 cleared issue move up; the stuck counter is per issue, kept on hold;
                 the task closes only when the waiting room is empty; no dropping
 the word        "issue" stays; there is no separate "needs" list
 on screen       the task panel's Issues group is the waiting room: dark now, pale on
                 hold, grey cleared
```

## 4. How to work with the user: follow this

These rules come from the user. Claude's memory of them stays on the first laptop, so they are written here.

```
 decisions     every design choice is the user's. Found a problem? Show it: the
               problem, a concrete example, options, your pick. Wait. Never write
               an undecided choice into the docs or the code, not even as a
               "proposal" deep in a section
 clarity       explain from the basics when asked: where a thing lives, who writes
               it, how it reaches each agent. The user decides only what they fully
               understand
 names         full names everywhere, even in quick examples: "box 3 · explains why
               label is unbound for a guest", never a bare "box 3"; no
               abbreviations: never T3, I1 or C15
 numbering     one numbering only, LEGO.md's; never renumber holes
 answers       short; mostly ASCII diagrams; complex things made simple; no side notes
               in parentheses inside diagrams; draw only what really exists
 choosing      show options side by side, so the user picks
 git           Claude commits, in WSL; the user does everything on GitHub and pushes
               from Windows PowerShell; never set up a GitHub login in WSL
 line endings  this repository has no .gitattributes, so Windows flips line endings;
               commit only real changes, with the file's line endings as in git
```

## 5. Run the frontend

```
 cd agentic_tutor/frontend
 npm ci
 npm run dev           http://localhost:3000, in demo mode
 npm test              7 tests
 npm run typecheck
 npm run build
```

Demo mode plays task 3 from turn 6. Any message plays the next turn. The fifth ticks the last box while an issue still waits, so that issue is picked up; the sixth clears it, which closes task 3 and opens task 4. Importing any `https://` address shows the preparing steps.

## 6. Infrastructure

```
 Vercel      project agentic-tutor · https://agentic-tutor-lake.vercel.app · root: frontend
             live mode: empty screens until a backend exists
 Fly         app backend-withered-morning-5909 · Frankfurt · runs tutor_v2 today;
             tutor_graph will replace it there · secret ANTHROPIC_API_KEY
 Supabase    organization ALPHAbilal · project agentic-tutor · ref rbsvlxqdmbpwenyxeobu
             eu-central-1 · Postgres 17 · restored 2026-10-12; a free project pauses
             when idle
 git         dev_master (this repository, which also tracks agentic_tutor/) and the
             agentic-tutor repository (GitHub ALPHAbilal/agentic-tutor), which Vercel
             and Fly deploy; a push there rebuilds production. On the laptop used on
             2026-10-12, agentic-tutor was not cloned: the frontend changes of that day
             live in dev_master only
 not ours    devmind-web.vercel.app is a different, older project
```

## 7. The screen's rules

```
 screen       no numbering on the learner's screen (the brand rule); no helper sentences or
              descriptive labels: the design says it
 style        Quiet, minimalist: flat and still; no colored edge bars; no glow, pulse, shimmer,
              sweep or blinking; state is the text's tone: dark is proven or now, grey is done,
              pale is later or on hold; a box not proven yet is a blank bar
 references   copy a reference design's layout only; keep our colors: grey, and blue #4f7290
 sizes        measured on claude.ai: sidebar 287px; rows 32px tall, 1px apart, 14px text on
              21px lines, 38px in; section label 13px on 16px in a 24px row; reply 15px on 22px;
              your message 15px on 20px, padding 12px by 16px, 12px corners; composer 48px
              tall, 14px corners; small text 13px on 17px
 teaching     the answer is never given; the answer key stays locked
```
