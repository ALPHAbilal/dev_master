# Lana

You and your AI on the same page, learning faster together.

Lana has two views of one conversation. In its **full page** you and Lana talk
things through: what to find, which searches to run, what each will give you.
In Chrome's **side panel**, beside the real site, you read and show; Lana sees the
page you are on, points to the part that matters, and keeps what you find.

## Status

Early. The infrastructure is in place: research mode, and every surface wired
to the others. The workflow on top of it, and the agent behind it, come later.

## Run it

```sh
npm install
npm run build
```

In Chrome, open `chrome://extensions`, turn on Developer mode, choose
**Load unpacked**, and pick `.output/chrome-mv3`. Click the toolbar icon to open
Lana.

`npm run dev` rebuilds on every change; load `.output/chrome-mv3-dev` instead.
`npm run compile` checks the types.

## Try it

- Click the toolbar icon. Lana's full page asks one thing: what you want to learn.
  Answering it starts **research mode**: the icon gets a dot, and Lana starts
  working on every page. Off, Lana stays out of the way.
- Lana frames the question into a plan, then suggests searches and what each
  will give you. **Search** opens the results page with Lana in the side panel.
- When there is something to talk through, the panel hands back to the full
  page (the expand button does it anytime); **Back to the page** returns.
- Open any article (reload tabs that were open before Lana was installed).
  The panel shows the page and follows you across tabs.
- Select text: Lana's small menu appears over it, **Keep** or **Ask**.
- Right-click text, code, an image or a table: **Keep with Lana** or
  **Ask Lana about this**. It arrives in the shape of what it is.
- Select text and press `Ctrl+Shift+K` (`Cmd+Shift+K` on a Mac).
- The target button marks the page by hand: a heading gets a frame, exact words
  a highlight; an arrow shows while the mark is off screen.
- The square button ends research mode.

The Goal Book web app can start and stop research mode too, through
`externally_connectable` (`research:start`, `research:stop` in the contract).

## Structure

```
src/
  contract/
    messages.ts       every message between the three parts, typed
  entrypoints/
    background.ts     the hub: carries messages, the right-click menu,
                      the shortcut, the toolbar icon, the side panel
    content/          the page script, inside every website
      index.ts          answers the background, reports the page
      layer.ts          Lana's own layer: frame, highlight, arrow, menu
      capture.ts        turns what was taken into text, code, image or table
      find.ts           finds a part by heading or id, a passage by its words
    sidepanel/        the side panel: Lana beside the site (React)
    app/              the full page: where Lana and the learner talk (React)
  ui/                 shared by both views: the conversation and its store,
                      the status line, how each turn is drawn, the scenario
  design/
    tokens.css        colors and type shared by every surface
```

The page script and the panel never talk directly: every message goes through
the background, which keeps what the panel missed while it was closed.
