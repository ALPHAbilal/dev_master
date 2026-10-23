# Agentic Search Companion: decisions

In-house notes for `agentic-search-companion/`. They stay in dev_master and
never go into the companion's own repository.

## Decided on 2026-10-23

- The search phase lives in a **Chrome side panel** beside the real site
  (chosen over: back to our app, floating chat, two windows).
- **Scope now: the frontend only.** The side panel, the marks drawn on the page,
  and the flows. The agent's intelligence comes later; until then a scripted
  scenario stands in for it. Expect the frontend to change once the agent is
  designed.
- **Name:** agentic-search-companion.
- **Tooling:** WXT + React + TypeScript. `web-ext` removed: it only launches a
  browser during development, which cannot work from WSL, and it brought 9
  vulnerable dependencies.
- **Two repositories, one folder (git subtree).** The folder is ordinary in
  dev_master. To publish it alone, from dev_master:

  ```
  git subtree push --prefix=agentic-search-companion <portfolio-remote> main
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

## Open

- Panel code: bundled in the extension, or a thin shell framing a Vercel page.
  Not needed until there is a backend.
