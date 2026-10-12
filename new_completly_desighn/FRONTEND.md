# Frontend: what changes

Draft 0.6 · 2026-10-12 · companion to `LEGO.md` (draft 0.20)

**The rule:** we keep the screen we have and change only what the new design needs. The backend spec then serves exactly the contract in §7.

**Brand rule:** the screen never numbers things. No "task 3", "box 2", "concept 17" or "issue 1": the order of a list already says the order. IDs live in the data and in these design docs, never on screen.

**Style: Quiet** (chosen 2026-10-12 from three minimalist variations). Flat and still: no marks, no colored edges, no glow, pulse, sweep or blinking, and no helper sentences. State is the text's tone: dark is proven or happening now, grey is done, pale is not open yet. A box not proven yet is a blank bar. The only labels are the task's tier and its files, as small grey tags; a file tag opens the file in the Codebase panel. Sizes and spacing come from claude.ai; the fonts and colors stay ours:

```
 sidebar          287px wide; rows 32px tall, 1px apart, 8px corners; 14px text on 21px lines,
                  38px in from the row's edge
 section label    13px on 16px, normal case, in a 24px row, 5px above the first row
 panel title      15px on 22px, semibold
 tags             22px tall, 6px corners, 13px text
 reply text       15px on 22px
 your message     15px on 20px; padding 12px by 16px; 12px corners
 composer         48px tall, 8px padding, 14px corners; 15px text on 21px lines; send and
                  stop 32px
 small text       13px on 17px
```

**Status:** built in `agentic_tutor/frontend` (demo mode). Draft 0.6 adds the waiting room (§3, §4, §7). Typecheck clean, 7 of 7 tests pass, the production build succeeds.

---

## 0. Before

```
 production   https://agentic-tutor-lake.vercel.app  =  commit c34b390  =  the old screen
              it runs in live mode with no backend connected, so every screen is empty
 demo mode    cd agentic_tutor/frontend · npm run dev · http://localhost:3000
```

The main screen before, in demo mode:

```
┌──────────────────────┬──────────────────────────────────────────┬────────────────────────────┐
│                    < │          [ Map ]  Conversation           │ >  [ Editor ]  Codebase    │
│ + Add new codebase   │                                          │ test_pinned_qa.py        + │
│ Codebases            │ • Learned  pinned items stay in order    │ 1  def _pinned_qa_group(   │
│ v run_prompts.py 2/6 │ ✓ Proved   you can read pinned-first …   │ 2      pinned = [ … ]      │
│   load_prompts       │ ○ Noted for later  de-dupe across …      │ 3      rest   = [ … ]      │
│   normalize_row      │ @ aside  How does list.append differ …   │ 4      # TODO: id collis…  │
│   _pinned_qa_group > │ ⚠ Found a gap  the same id can appear …  │ 5      return pinned + rest│
│   _dedupe_by_id      │ ↳ Went to learn first — Dict identity …  │                            │
│   build_prompt_batch │ │  ↳ Needed first — Why keys must hash   │                            │
│   run_prompts        │ │  │  ★ Sealed — you own Why keys must … │                            │
│                      │ │  ↩ Came back to Dict identity vs value │                            │
│                      │ │       picking up: "which do two …"     │                            │
│                      │ ◉ You are here — answer what the …       │                            │
│ ⚙ Settings           │                                          │           Submit           │
└──────────────────────┴──────────────────────────────────────────┴────────────────────────────┘
```

---

## 1. Part by part

```
 PART                          BEFORE                                 NOW
 ────────────────────────────  ─────────────────────────────────────  ─────────────────────────────────────
 sidebar · codebase row        name + count 2/6                       same; count = tasks done / tasks
 sidebar · under the codebase  a flat list of units                   one short row per task: its title
                                                                      and its ticked boxes, such as 1/4
 second sidebar                nothing                                NEW, opens when a task is clicked;
                                                                      the main sidebar folds into its rail
 sidebar · icons               plus · caret · arrow · gear            removed; the collapse button stays
 sidebar · Settings            Park lesson · Resume lesson            removed: the design has no park
 Map tab                       the story of the selected unit         the story of the selected task or
                                                                      issue; a click on a line opens
                                                                      that turn
 Conversation · messages       tutor and learner, code snippets,      same, with a thin line between
                               streaming text                         tasks
 Conversation · grade cards    a JUDGE verdict under an answer        a tick note: ☑ <the box's text>
 Conversation · tool rows      TEACHER · step · read_workspace        what the tutor reads, in plain words
 Conversation · side threads   aside boxes with their own follow-ups  removed: a side question is one
                                                                      normal turn, then saved for later
 Conversation · composer       Answer │ Side question switch          one text box
 Editor                        tabs · line numbers · Submit           same; Submit became Attach file
 Codebase                      explorer · file view · unit            explorer and file view only:
                               highlights · Focus current unit        highlights would show where the bug is
 Attach                        from code, editor, conversation        same
 import page                   everything                             rebuilt from the crafting line (§5)
```

---

## 2. The new main screen

The left side follows the reference design the user shared: layout only, our colors. It has three states.

```
 1  THE MAIN SIDEBAR              2  FOLDED                  3  A TASK IS OPEN
 ┌──────────────────────────┐     ┌────┐                     ┌────┬──────────────────────────────┐
 │                        « │     │ »  │                     │ »  │ guests always get the        │
 │ + New codebase           │     │    │                     │    │ generic error                │
 │ Codebases                │     │    │                     │    │ [debug] [app.py]             │
 │ ▢ chatbot_final_version  │     │    │                     │    │                              │
 │   trace one question …   │     │    │                     │    │ The job                    ∧ │
 │   unknown labels need …  │     │    │                     │    │ ╰ the fix works: a guest …   │
 │   guests always get the… │     │    │                     │    │ Concepts                   ∧ │
 │   recruiters can filter… │     │    │                     │    │ ╰ a broad except hides …     │
 │   log every question …   │     │    │                     │    │   │ ╰ finds the real error … │
 │   conversations survive… │     │    │                     │    │ ╰ loop variables outlive …   │
 │                          │     │    │                     │    │     ╰ ▬▬▬▬▬                  │
 │                          │     │    │                     │    │ Issues                     ∧ │
 │                          │     │    │                     │    │ ╰ a loop variable only exi…  │
 │                          │     │    │                     │    │   ╭──────────────────────╮   │
 │                          │     │    │                     │    │   ╰ why the loop on line…│   │
 │                          │     │    │                     │    │   ╰──────────────────────╯   │
 └──────────────────────────┘     └────┘                     └────┴──────────────────────────────┘
 « folds it into the rail          » unfolds it               » unfolds the main sidebar and
 a click on a task opens 3                                    closes the panel
```

In state 3, the panel's title comes first, then its tags: the tier, and the files, which open in the Codebase panel. Below them are the groups, each folding with its chevron. The selected issue sits in a rounded box with a border. A box not proven yet shows a blank bar, never its text or its number. The main sidebar is laid out like claude.ai's: the main action, + New codebase, and every codebase row carry a small grey icon with their text 38px in; the category title, Codebases, is small grey text with 24px of air above it; a codebase's tasks sit under it on a grey guide line, their text aligned with the codebase's name. Done tasks are grey, the current one is dark and bold, and later ones are pale. On the import page, + New codebase shows as selected.

```
 CLICK                          WHAT HAPPENS
 ─────────────────────────────  ───────────────────────────────────────────────────
 a codebase                     opens it, or folds it
 a task                         the main sidebar folds into its rail; the task's
                                panel opens beside it; the map shows its story
 » on the rail                  the main sidebar comes back; the panel closes
 the panel's title              the map shows the whole task's story
 a group's name                 folds or unfolds the group
 an issue                       the map shows that issue's own story
 a ticked box                   the conversation opens at the turn that ticked it
 a story line                   the conversation opens at that turn
 a task, on the import page     goes to the main screen with that task's panel open
```

## 3. The task sheet on screen

It sits in the second sidebar, which opens when a task is clicked (§2, state 3).

```
 SHOWN                                         FROM (LEGO.md §10)
 ────────────────────────────────────────────  ──────────────────────────────────────
 the task's title, goal, tier and files        task · the task crafter
 the job box, with its text                    the_job_is_done
 each concept: its name, checked or not        concepts · concept · checked
 each box: ticked or not                       boxes · ticked_at_turn
 each concept box's text                       boxes · box, only once ticked;
                                               before that, a blank bar
 the issues: the waiting room, nested, in      issues · LEGO.md §17
   priority order; dark is now, pale is on
   hold, grey is cleared or already knew it

 NOT SHOWN: difficulties · had_it_then_missed · times_it_came_up
            they are for the tutor; the story already shows those moments
```

A concept that was checked and then missed goes back to ☐. Nothing else marks it.

**The Issues group is the waiting room** (decided 2026-10-12). It shows every issue of the task, nested under the issue it was named in, in the priority order the server sends. No numbers and no labels: the tone says the state.

```
 Issues                                 ∧
 ╰ a loop variable only exists if …         ◄ pale: on hold, with its note
   ╭────────────────────────────────╮
   ╰ why the loop on line 684 runs … │      ◄ dark: now
   ╰────────────────────────────────╯
 ╰ how the test fakes OpenAI                ◄ pale: on hold, waits its turn
 ╰ run the test                             ◄ grey: cleared
```

The task can't close while anything in it is still dark or pale.

---

## 4. Story lines: what Map.tsx draws

```
 LINE                                     BEFORE IN Map.tsx               CHANGE
 ───────────────────────────────────────  ──────────────────────────────  ─────────
 • Started <task title>                   • Learned                       new word
 ✓ Did <what they showed>                 ✓ Proved                        new word
 ☑ <the box's text>                       nothing                         new line
 ~ Almost <what went wrong>               ~ Almost                        same
 ⚠ Found a gap <why, for the learner>     ⚠ Found a gap                   same
 ↳ Went to learn first — <issue>          ↳ Went to learn first —         same
 ↳ Needed first — <issue>                 ↳ Needed first —                same
 ○ Saved for later <issue>                ○ Noted for later               new word
 ‖ Put on hold — <issue>                  nothing                         new line
 ↳ Picked up — <issue>                    nothing                         new line
 ★ Cleared — <issue>                      ★ Sealed — you own              new word
 ✕ Already knew it — <issue>              nothing                         new line
 ↩ Came back to <step above>              ↩ Came back to                  same
       picking up: <return note>                picking up:               same
 ★ Done — <goal>                          ★ Sealed — you own              new word
 ◉ You are here — <the current focus>     ◉ You are here —                same

 REMOVED: ⚙ Reasoning off · ✓ Cleared up, struck through · @ aside ·
          the axis tags such as ‹How it works›
```

Each line is written by code in the same step as the change it shows (`LEGO.md` §12, effects). Indentation is the depth of the stack at that moment.

---

## 5. The import page, rebuilt

Every field of the old page is gone. The new page has only what the crafting line needs (`LEGO.md` §13).

```
 BEFORE                                         NOW
 ─────────────────────────────────────────────  ─────────────────────────────────────────
 Repo URL or local path · folder button         Repository URL
 "Start with 1–3 stations …"                    removed
 Preview example stations                       removed
 Learning in batches: initial stations ·        removed: all tasks are prepared once,
   next batch size · unfinished stations          together
   left · prepare the next batch
 Learning profile · Next batch                  removed
 Agent log                                      Preparing: the four steps; grey once
                                                  done, dark while running, pale waiting
 Learning stations                              Tasks: the ladder as a plain list, filled
                                                  as tasks are written
 Generate · N initial stations                  Start the first task, once the ladder is
                                                  ready
 station card: learning target · needed         task card: title · tier and files tags ·
   first · scope · code highlights ·              the job box · concepts with their boxes
   understanding across axes · assessment
   review · misconceptions · state ·
   position · depth
 Open lesson · Locked                           Open task; a task not open yet has no
                                                  button and is pale
```

Step 1, import:

```
┌──────────────────────────────────────────────┐
│ ┌──────────────────────────────────────────┐ │
│ │ https://github.com/you/your-repository   │ │
│ └──────────────────────────────────────────┘ │
│                   Import                     │
└──────────────────────────────────────────────┘
```

Step 2, preparing. The four steps are the crafting line: code copies the repository, the concept crafter writes the concepts, the task crafter writes the tasks, code orders them.

```
┌────────────────────────┬──────────────────────────────────────────────────────────┐
│ sidebar                │ your-repository                                          │
│                        │ ┌ Preparing ────────────────────┐ ┌ Tasks ─────────────┐ │
│                        │ │ copying the repository        │ │ trace one questi…  │ │
│                        │ │ finding the concepts          │ │ unknown labels n…  │ │
│                        │ │ writing the tasks             │ │ guests always ge…  │ │
│                        │ │ ordering the tasks            │ │ ▬▬▬▬▬▬             │ │
│                        │ │   a broad except hides the …  │ │                    │ │
│                        │ └───────────────────────────────┘ └────────────────────┘ │
│                        │                   Start the first task                   │
└────────────────────────┴──────────────────────────────────────────────────────────┘
```

Step 3, a click on a task opens its card. Never the answer key.

```
┌─ task card ────────────────────────────────────────────────────────────────┐
│ Back                                                                       │
│ guests always get the generic error                                        │
│ [debug] [app.py]                                                           │
│ The job                                                                    │
│ the fix works: a guest gets a real answer                                  │
│ Concepts                                                                   │
│ a broad except hides the real error                                        │
│    ▬▬▬▬▬▬                                                                  │
│ loop variables outlive the loop                                            │
│    ▬▬▬▬▬▬▬▬                                                                │
│ OpenAI tool calling                                                        │
│    ▬▬▬▬▬                                                                   │
└────────────────────────────────────────────────────────────────────────────┘
```

If preparing fails, the page says at which step, with a Try again button.

---

## 6. Never on the learner's screen

```
 the answer key · the orchestrator's leaf, kind and why · the evaluator's verdicts,
 except a tick · the stuck level · the tutor's instructions · the task sheet's
 private fields (§3) · any agent's name
```

---

## 7. The contract: `lib/api/types.ts`

This is page 1 of the backend spec. It replaces the whole tutor_v2 contract (units, axes, driver state, park, asides, stations). The file itself is the source of truth; this is its shape.

```ts
Workspace      { id, name, preparing: running | ready | failed, tasks_done, tasks_total }

Snapshot       { revision, workspace, ladder: LadderTask[], where: Where | null,
                 story: StoryLine[], conversation: Message[] }

LadderTask     { id, number, title, goal, tier, files,
                 status: done | current | later,
                 sheet: TaskSheet, issues: LadderIssue[] }
LadderIssue    { id, number, title, parent_issue_id,
                 status: now | on_hold | cleared | already_knew }
               ladder[].issues = the waiting room, in priority order
Where          { task_id, issue_id, depth, you_are_here,
                 tutor: waiting_for_you | answering }

TaskSheet      { the_job_is_done: Box, concepts: SheetConcept[] }
SheetConcept   { number, name, checked, boxes: Box[] }
Box            { number, text (a concept's box: null until ticked), ticked_at_turn }

StoryLine      { id, task_id, issue_id, turn, depth, kind, text, picking_up }
               kind: started · did · ticked · almost · found_a_gap · went_to_learn_first ·
                     needed_first · saved_for_later · put_on_hold · picked_up · cleared ·
                     already_knew · came_back · done
IDs            written in full, never shortened: "task-3", "issue-1"
Message        { id, task_id, turn, role: learner | tutor, text, attachments }
Attachment     { kind: repository_code | editor_code | conversation, label, text, source }

stream         revision { revision } · tutor { task_id, turn, text } · tool { task_id, turn, doing }
stop           the tutor stops its reply where it is; what it said so far is kept
preparing      step { name: copying | concepts | tasks | ordering, state: running | done, count } ·
               concept { number, name } · task { id, number, title } · ready { tasks_total } ·
               failed { step, error }
```

---

## 8. Routes

```
 ROUTE                                          WHAT IT DOES
 ─────────────────────────────────────────────  ──────────────────────────────────────────
 GET   /workspaces                              the sidebar's codebases
 POST  /workspaces/import                       { name, git_url } → preparing starts
 GET   /workspaces/{id}/preparing               stream: step · concept · task · ready · failed
 GET   /workspaces/{id}/tasks/{task}            one task, as in the ladder
 POST  /workspaces/{id}/start                   opens task 1; the tutor speaks first
 GET   /workspaces/{id}?since={revision}        the snapshot, or "unchanged"
 POST  /workspaces/{id}/messages                { client_message_id, text, attachments }
 POST  /workspaces/{id}/stop                    the tutor stops its reply where it is
 GET   /workspaces/{id}/stream                  stream: revision · tutor · tool
 GET   /workspaces/{id}/files                   the explorer
 GET   /workspaces/{id}/file?path=              one file

 GONE: register · open · session · map · resume · park · answer · aside · workspace submit
```

---

## 9. Every file

```
 FILE                                  WHAT HAPPENED
 ────────────────────────────────────  ──────────────────────────────────────────────────
 lib/api/types.ts                      rewritten: §7
 lib/api/live.ts                       the routes in §8
 lib/api/demo.ts                       new: the task 3 scenario, turn by turn; replaces
                                       demo.json; 0.6: the waiting room, full IDs, and a
                                       last issue picked up after every box is ticked
 lib/api/stub.ts                       rewritten: plays demo.ts in memory
 lib/session.tsx                       rewritten: one workspace, one snapshot; send() · stop()
 lib/scanner.ts · scanner-demo.json    removed
 lib/auth.tsx · lib/editor.ts          unchanged
 components/Sidebar.tsx                one short row per task, titles only; icons and Settings
                                       removed; « and » fold and unfold it
 components/TaskPanel.tsx              new: the second sidebar (§2, state 3); its Issues
                                       group is the waiting room (§3)
 components/Icon.tsx                   two new glyphs: « and »
 next.config.mjs                       the development badge is off: it covered »
 components/Map.tsx                    the new story lines; lines open turns; 0.6: put on
                                       hold, picked up
 components/Conversation.tsx           side threads and the switch removed; tick notes;
                                       task lines; opens at the clicked turn; one-row
                                       composer whose send turns into stop while answering
 components/Tutor.tsx                  same layout; the Settings dialog removed; file tags
                                       open the Codebase panel
 components/Editor.tsx                 Submit became Attach file
 components/Codebase.tsx               highlights, counts and the focus switch removed;
                                       opens the file a tag asks for
 components/Scan.tsx                   rebuilt as the import page (§5), Quiet: no shimmer,
                                       spinners, dots or flying pills
 components/TaskCard.tsx               new: the task card; replaces StationDetails.tsx
 components/BatchPlanner.tsx           removed
 components/Refs.tsx                   Ref renamed Attachment
 app/sidebar.css                       new: the Quiet style both screens share, sized from
                                       claude.ai
 app/tutor.css · scan_stage.css        styles of removed parts gone
 scripts/extract-demo.cjs              removed: it rebuilt the old demo data
 tests/contracts.test.ts               rewritten for the new contract; scanner.test.ts removed
 README.md                             the contract section replaces the old backend notes
```

---

## 10. Order of work

```
 1  the contract       lib/api/types.ts, §7                done
 2  the demo data      demo.ts + stub.ts, the task 3 scenario  done
 3  the screen         sidebar · Map · Conversation · Editor · Codebase · import page   done
 4  clean out          park · resume · side threads · batches · axes · stations         done
 5  check              typecheck · tests · production build · demo mode in a browser    done
 6  commit and push    your call: a push deploys to Vercel; with no backend, production
                       stays empty, as it is today
 7  the backend spec   built to serve exactly this contract
 8  switch on          live mode on Vercel once the backend is up
```

---

## 11. Decisions

```
 1  box text before it is ticked      hidden until ticked                 you, 2026-10-11
 2  where the task sheet sits         a second sidebar that opens when    you, 2026-10-11
                                      a task is clicked; the main one
                                      folds into its rail, as in the
                                      reference design; our colors
 ·  numbering on screen               none: the brand rule                you, 2026-10-11
 ·  text on screen                    no helper sentences or descriptive  you, 2026-10-11
                                      labels: the design says it
 ·  style                             Quiet: minimalist, flat and still   you, 2026-10-12
 ·  sizes and spacing                 measured on claude.ai; our fonts    you, 2026-10-12
 ·  the tier and the files            small grey tags; a file tag opens   you, 2026-10-12
                                      the file
 ·  the sidebar's labeling            like claude.ai: icons on the main   you, 2026-10-12
                                      action and the codebases; a
                                      category title with air above it
 3  the Answer │ Side question        removed: the orchestrator tells     you, 2026-10-11
    switch                            them apart
 4  the collapse button of the        kept                                you, 2026-10-11
    sidebar
 ·  Codebase highlights               removed: they would show where      my proposal
                                      the bug is
 ·  import                            a repository URL only: the server   my proposal
                                      needs the code to prepare tasks
 ·  between tasks                     the conversation runs on, with a    my proposal
                                      thin line holding the next task's
                                      title
 ·  the waiting room on screen        the task panel's Issues group,      you, 2026-10-12
                                      in priority order; dark now, pale
                                      on hold, grey cleared
```
