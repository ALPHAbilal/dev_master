# Lana: decisions

In-house notes for `lana/`. They stay in dev_master and never go into Lana's
own repository (https://github.com/ALPHAbilal/Lana).

## Decided on 2026-10-23

- The search phase lives in a **Chrome side panel** beside the real site
  (chosen over: back to our app, floating chat, two windows).
- **Scope now: the frontend only.** The side panel, the marks drawn on the page,
  and the flows. The agent's intelligence comes later; until then a scripted
  scenario stands in for it. Expect the frontend to change once the agent is
  designed.
- **Name:** Lana (first called agentic-search-companion).
- **Description:** You and your AI on the same page, learning faster together.
- **Tooling:** WXT + React + TypeScript. `web-ext` removed: it only launches a
  browser during development, which cannot work from WSL, and it brought 9
  vulnerable dependencies.
- **Two repositories, one folder (git subtree).** The folder is ordinary in
  dev_master. To publish it alone, from dev_master:

  ```
  git remote add lana https://github.com/ALPHAbilal/Lana.git   (once)
  git subtree push --prefix=lana lana main
  ```

  Rules that keep the portfolio repository clean:
  1. A commit that touches the companion touches only its folder.
  2. Planning, thoughts and decisions stay outside the folder (here).
  3. Inside the folder: code, tests, README.

## Learned from the demo (goal_book/extension-demo)

- Marks are drawn from our own layers, never by editing the site's elements.
- Marks that belong to the page (frame, selection menu) sit in a layer placed in
  page coordinates, so the browser scrolls them with the text, with no lag.
- That layer sits one step under the page's own top bar, so the bar covers our
  marks as it covers the text.
- Sites redraw their text after loading; a highlight must be found again when
  its range empties.

## The build, in order

```
 ✔ 1 foundation      the panel opens and shows "Lana" (commit 73ba598)
 ▶ 2 contract        the messages between the page script and the panel
   3 page awareness  the panel knows which page and which part the learner is on
   4 page marks      bring over the demo: frame, highlight, scroll arrow, menu
   5 panel UI        the real side panel screens
   6 scenario player a script that stands in for the agent
   7 flows           where to look · result labels · scroll arrow, frame and
                     highlight · selection menu · tab or site switch · pages
                     we cannot draw on
```

Lana's three parts, the words used everywhere:

```
 PANEL        Lana's window, the strip Chrome opens on the right. The learner
              reads and types there.
 PAGE SCRIPT  hidden inside the website. Draws the frame, highlight, scroll
              arrow and menu; sees the scrolling and the selections.
 BACKGROUND   invisible, always running. Opens the panel when the icon is
              clicked and carries messages between the two.
```

The contract is the list of messages between the panel and the page script.

## The contract (step 2): decided

- **Pages Lana cannot draw on** (Chrome Web Store, chrome:// pages, PDFs, some
  canvas sites): the learner shows the page to Lana. Lana tells them how:
  copy the text (Ctrl+A, Ctrl+C) or take a screenshot (Win+Shift+S), then paste
  into the **page box**. The page box is separate from the chat box: page box
  for page content (text or image), chat box for questions. Lana never takes a
  screenshot itself, so it needs no screenshot permission.

  ```
  ┌ Lana ─────────────────────────────────┐
  │  conversation ...                     │
  │ ┌ Show Lana this page ──────────────┐ │  ← page box
  │ │ Lana can't see this page.         │ │
  │ │ 1. Ctrl+A, Ctrl+C  → paste here   │ │
  │ │ 2. or Win+Shift+S  → paste here   │ │
  │ └───────────────────────────────────┘ │
  │ ┌ Ask Lana...                  [ ➤ ]┐ │  ← chat box
  │ └───────────────────────────────────┘ │
  └───────────────────────────────────────┘
  ```

- **A · the scroll arrow:** the page script shows and hides it on its own. The
  panel only sends "point to this part"; when that part is off screen the page
  script shows "↓ scroll down", and hides it when the learner reaches it.

## The contract (step 2): open, in this order

Claude's proposal for the messages, not yet confirmed by the user:

```
 THINGS     Page          tab number, address, title, site name
            Part of page  the heading the learner sees ("How Amazon S3 works")
                          and its id when there is one ("CoreConcepts")
            Passage       exact text + the part it belongs to
            Mark          one thing drawn on the page, with its own id
            Result label  a search result's address + label + reason
            Page copy     what the learner pasted: text or image

 PAGE SCRIPT ──► PANEL    page opened · page cannot be marked · learner reached
                          part · learner selected text · learner chose action
                          (add to the book | ask) · tab switched · mark answer
 PANEL ──► PAGE SCRIPT    point to part · highlight passage · label results ·
                          clear marks
 INSIDE THE PANEL         learner pasted page (Page copy)
```

- **B · the page script cannot find the text** (asked, not answered).
  The panel says "highlight: An object is a file and any metadata...", but AWS
  changed its wording or the learner is on another page.
  1. the page script always answers "found" or "not found"; on "not found" the
     panel shows the phrase with [ Copy phrase ] then Ctrl+F  ◄ Claude's pick
  2. the page script stays silent; the learner waits for a highlight that never
     comes
- **C · "Add to the book" with no backend yet.** Kept in the panel's memory
  (lost when the panel closes), or in Chrome's storage (kept after a restart).
  Claude's pick: Chrome's storage.
- **D · how a part is named.** By its heading text, by its id, or both. Claude's
  pick: send both; find by id when there is one, else by text; always show the
  text to the learner.
- **F · when the page box appears.** Always open, or only when Lana cannot see
  the page (plus a small "Show page" button anytime). Claude's pick: only when
  needed, plus the button.
- Then: the user confirms the message list above, and Claude writes it as typed
  code in `lana/src/contract/`.

## Open, later

- Panel code: bundled in the extension, or a thin shell framing a Vercel page.
  Not needed until there is a backend.
