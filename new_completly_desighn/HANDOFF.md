# Handoff: continue here

Updated 2026-10-12. Claude's memory stays on the laptop it was made on. This file carries everything a new session needs.

## 1. Read in this order

```
 1  HANDOFF.md                  this file
 2  LEGO.md                     the agentic layer, draft 0.20: pieces, plates, cards, the question
                                tree, the task sheet, the stuck ladder, checkpoints, the waiting
                                room (§17)
 3  BUILD_WITH_CLAUDE.md        every piece on the Claude API and the Agent SDK, checked
 4  FRONTEND.md                 the learner's screen, draft 0.6: built; its contract is §7–§8
 5  BACKEND_SPEC.md             the backend to build next, draft 0.3; its §0 lists what is still
                                open
 6  t3-agent-walkthrough.html   task 3, turn by turn, for every agent; drawn from LEGO.md 0.19,
                                so it still shows quotes and saved issues
                                https://claude.ai/artifact/ETjegAK3D4uBfi8jkezNFv
 7  sidebar-variations.html     the three minimalist styles; Quiet (variation 1) was chosen
                                https://claude.ai/artifact/U2LqzQA7FrtVQHErkJmZnX
```

Old designs are in `archive/` (see `archive/README.md`). Don't build from them.

**To resume with Claude on the other laptop,** open Claude Code in `dev_master` and say:

> Read `new_completly_desighn/HANDOFF.md`, then `LEGO.md` §16–§17 and `BACKEND_SPEC.md` §0. We close the open holes, then build step 1.

## 2. Where we are

```
 [x] the agentic layer designed                      LEGO.md 0.20
 [x] the Claude mapping checked                      BUILD_WITH_CLAUDE.md
 [x] the frontend rebuilt for the new design         agentic_tutor/frontend, demo mode, 0.6
 [x] the backend spec written                        BACKEND_SPEC.md 0.3
 [x] the 4 decisions of BACKEND_SPEC.md §22
 [~] LEGO.md's holes, one by one                     open: holes 4, 13, 16, 18 and the tutor's
                                                     new pieces
 [ ] build steps 1 to 9                              BACKEND_SPEC.md §20
```

## 3. Run the frontend

```
 cd agentic_tutor/frontend
 npm ci
 npm run dev           http://localhost:3000, in demo mode
 npm test              7 tests
 npm run typecheck
 npm run build
```

Demo mode plays task 3 from turn 6. Any message plays the next turn. The fifth ticks the last box while an issue still waits, so that issue is picked up; the sixth clears it, which closes task 3 and opens task 4. Importing any `https://` address shows the preparing steps.

## 4. Infrastructure

```
 Vercel      project agentic-tutor · https://agentic-tutor-lake.vercel.app · root: frontend
             live mode: empty screens until a backend exists
 Fly         app backend-withered-morning-5909 · Frankfurt · runs tutor_v2 today
             secret ANTHROPIC_API_KEY
 Supabase    organization ALPHAbilal · project agentic-tutor · ref rbsvlxqdmbpwenyxeobu
             eu-central-1 · Postgres 17 · restored 2026-10-12
 git         dev_master (this repository, which also tracks agentic_tutor/) and the nested
             agentic_tutor repository (GitHub ALPHAbilal/agentic-tutor), which Vercel and Fly
             deploy; a push there rebuilds production
             WSL has no GitHub login: push from Windows PowerShell
 not ours    devmind-web.vercel.app is a different, older project
```

## 5. The rules the user set

```
 naming       no abbreviations; every ID written in full: task 3, issue 1, concept 15,
              box 2, never T3, I1 or C15; a model reads and writes full labels (word +
              number + name), made by engine/names.py only
 screen       no numbering on the learner's screen (the brand rule); no helper sentences or
              descriptive labels: the design says it
 style        Quiet, minimalist: flat and still; no colored edge bars; no glow, pulse, shimmer,
              sweep or blinking; state is the text's tone: dark is proven or now, grey is done,
              pale is later; a box not proven yet is a blank bar
 references   copy a reference design's layout only; keep our colors: grey, and blue #4f7290
 sizes        measured on claude.ai: sidebar 287px; rows 32px tall, 1px apart, 14px text on
              21px lines, 38px in; section label 13px on 16px in a 24px row; reply 15px on 22px;
              your message 15px on 20px, padding 12px by 16px, 12px corners; composer 48px
              tall, 14px corners; small text 13px on 17px
 answers      short, only what matters, many ASCII diagrams; no side notes in parentheses
              inside diagrams; draw only what really exists
 choosing     show options as variations side by side, so the user picks
 teaching     the answer is never given; the answer key stays locked
 git          Claude commits; the user pushes, from Windows PowerShell
```

## 6. Decisions (BACKEND_SPEC.md §22 and LEGO.md §16)

```
 1  restore the Supabase project now               done
 2  how learners sign in                           a link by email only
 3  LEGO.md's holes                                one by one; see below
 4  where the new backend runs                     replaces tutor_v2 completely, in the
                                                   current Fly app
```

Decided on 2026-10-12, in LEGO.md 0.20:

```
 quotes          removed everywhere: the evaluator answers met | not met | unclear only
 kinds of work   names, not numbers: "kind_of_work": "debugging"
 labels          word + number + name; engine/names.py makes every one
 waiting room    LEGO.md §17: every need is an issue, ordered by priority 1 to 5; the
                 learner wins a switch; nothing is lost; the task closes only when the
                 waiting room is empty; on screen, the task panel's Issues group
 still open      holes 4, 13, 16, 18 · the tutor's new pieces: now or during the build
```
