# Lana

You and your AI on the same page, learning faster together.

Lana lives in Chrome's side panel. You read and search the real sites; Lana sees
the page you are on, points to the part that matters, and keeps what you find.

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
the side panel.

`npm run dev` rebuilds on every change; load `.output/chrome-mv3-dev` instead.
`npm run compile` checks the types.

## Try it

- Click the toolbar icon. The panel asks one thing: what you want to find out.
  Answering it starts **research mode**: the icon gets a dot, and Lana starts
  working on every page. Off, Lana stays out of the way.
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
    sidepanel/        the side panel app (React)
  design/
    tokens.css        colors and type shared by every surface
```

The page script and the panel never talk directly: every message goes through
the background, which keeps what the panel missed while it was closed.
