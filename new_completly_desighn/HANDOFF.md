# Handoff: continue here

Updated 2026-10-14. Claude's memory stays on the laptop it was made on. This file carries everything a new session needs, including how to work with the user (§4).

## 0. Where we stopped

Every hole of `LEGO.md` §16 is closed (§3 below). We are now going through **Claude's own choices 1 to 7**, which Claude wrote up without the user. **Choice 1** was explained, and the user has not answered yet.

**Choice 1 · who decides that an issue is finished?**

```
 the evaluator           a separate model that sees only what the learner said and
                         answers met | not met | unclear; independent, one more call
 the orchestrator alone  it gives the green flag itself; no second model
```

```
 understanding                              doing
 ─────────────────────────────────────      ─────────────────────────────────────
 concept · task_meaning · reading_the_code  planning · writing_code · tools_and_setup
                                            debugging · testing_and_checking

 issue · what a mock is              kind concept
   closes when: explains what a mock replaces
   learner: "a mock replaces the real OpenAI client"
   ──► someone has to judge whether that explanation is right    the evaluator

 issue · how to run pytest           kind tools_and_setup
   closes when: the tests run
   learner: pastes "3 passed"
   ──► the output says it                                        the orchestrator alone
```

```
 a  split by kind    understanding ──► the evaluator; doing ──► the orchestrator   ◄ Claude's pick
                     alone
 b  always           the evaluator for every issue; safest, one more call each time
 c  never            the orchestrator alone for every issue; cheapest, no second check
```

**To resume with Claude,** open Claude Code in `dev_master` and say:

> Read `new_completly_desighn/HANDOFF.md` and follow §4. We continue at choice 1: I answer a, b or c.

## 1. The queue, in order

```
 1  choice 1   which issues the evaluator judges                          ◄ now
 2  choice 2   no bouncing: a new "now" only when something changes
 3  choice 3   priority 3 vs 4: a side question = 4
 4  choice 4   the pick order: wish · priority 1 to 3 · the focus's own work · 4
 5  choice 5   on the task itself, the tutor's style = the turn's kind of work
 6  choice 6   a new map line "↳ Picked up"
 7  choice 7   IDs in the API: "task-3", "issue-1"
 then          write every answer into the docs in one pass; walk task 3 through
               the final design; build step 1 (BACKEND_SPEC.md §20)
```

## 2. Where we are

```
 [x] the agentic layer designed                      LEGO.md 0.21
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
 2  LEGO.md                     the agentic layer, draft 0.21; §16 has every decision, every
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

## 3. Decided

```
 2026-10-12
 Supabase        restored
 sign-in         a link by email only
 the backend     tutor_graph replaces tutor_v2 completely, in the current Fly app
 quotes          removed everywhere: the evaluator answers met | not met | unclear only;
                 no learner_words anywhere; the tutor has the exact words in its history
 kinds of work   names, not numbers: "kind_of_work": "debugging"
 labels          every ID in full: task 3, issue 1, never T3 or I1; a model reads and
                 writes word + number + name; engine/names.py makes every label
 the waiting     LEGO.md §17: every need is an issue; ordered by priority, 1 to 4 since
 room            2026-10-14; the order is the user's; the orchestrator names issues and gives the
                 green flag, code does the rest; the learner wins a switch; any number
                 of switches, nothing lost; left unfinished ──► on hold; issues inside a
                 cleared issue move up; the stuck counter is per issue, kept on hold;
                 the task closes only when the waiting room is empty; no dropping
 the word        "issue" stays; there is no separate "needs" list
 on screen       the task panel's Issues group is the waiting room: dark now, pale on
                 hold, grey cleared

 2026-10-14
 hole 19         b: a box stays ☑ forever, but while its concept is unchecked the
                 evaluator may judge it again; met ──► checked again
 hole 4          c: before a checked concept goes back to unchecked, code asks the
                 evaluator whether this turn really shows it; met ──► unchecked;
                 not met or unclear ──► it stays checked
 hole 13         showing_mastery removed: "I get it" with no proof is UNCERTAIN;
                 frustration removed everywhere: the kind of work, the stuck why,
                 priority 1, encourage_pause ──► 8 kinds of work, 4 priorities
 hole 16         a: in an issue, evaluate may also judge the task's boxes
 hole 18         a difficulty is JSON with a label and a text:
                 { "turn": 3, "label": "missing", "text": "<the GAP's issue title>" }
                 { "turn": 10, "label": "wrong_idea", "text": "<its what_went_wrong>" }
 tutor pieces    the 9 new texts are written during the build, step 3, and judged
                 in a real task 3 session, step 6
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
 one at a time one hole or choice per message, explained from the basics; on an
               answer, go straight to the next one; write nothing into the docs
               until every answer is in, then write them all in one pass
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
             and Fly deploy; a push there rebuilds production. The frontend in both
             is the same since 2026-10-14
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
