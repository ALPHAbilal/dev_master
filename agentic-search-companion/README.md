# Agentic Search Companion

A Chrome side panel that searches beside you. You do the searching, on the real
sites; the companion sees which page you are on, suggests where to look, points
to the part that matters, and keeps what you find.

## Status

Early. The interface comes first, driven by scripted scenarios; the agent behind
it comes later.

## Run it

```sh
npm install
npm run build
```

In Chrome, open `chrome://extensions`, turn on Developer mode, choose
**Load unpacked**, and pick `.output/chrome-mv3`. Click the toolbar icon to open
the side panel.

## Structure

```
src/
  entrypoints/
    background.ts     opens the side panel from the toolbar icon
    sidepanel/        the side panel app (React)
  design/
    tokens.css        colors and type shared by every surface
```
