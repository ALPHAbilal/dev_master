import type { ContentScriptContext } from 'wxt/utils/content-script-context';
import type { Annotation } from '@/contract/messages';
import { findText } from './find';
import { headingOf } from './capture';
import type { LabeledResult } from './results';

// Lana's own layer on the page. It sits in page coordinates (top-left of the
// document), so the browser scrolls Lana's marks with the text, with no lag. It
// lives in a shadow root, so the site's styles can't reach it and Lana's can't
// leak out. The site's own elements are never touched.

interface Hooks {
  onKeep: () => void;
  onAsk: () => void;
}

const CSS = `
:host { all: initial; }
* { box-sizing: border-box; font-family: Inter, "Segoe UI", system-ui, sans-serif; }
.frame { position: absolute; border-radius: 10px; box-shadow: 0 0 0 2px #4f7290; background: rgba(79,114,144,.07); pointer-events: none; }
.tag { position: absolute; left: 10px; top: -13px; display: inline-flex; align-items: center; gap: 6px; height: 24px; padding: 0 4px;
  border-radius: 12px; background: #4f7290; color: #fff; font-size: 12px; font-weight: 600; white-space: nowrap; }
.icon { width: 16px; height: 16px; border-radius: 4px; display: grid; place-items: center; background: #fff; color: #4f7290; font-size: 9.5px; font-weight: 700; }
.hl { position: absolute; border-radius: 3px; background: rgba(79,114,144,.28); pointer-events: none; }
.menu { position: absolute; display: flex; align-items: center; gap: 2px; padding: 3px 3px 3px 6px; border-radius: 12px; background: #1e2024;
  box-shadow: 0 4px 18px rgba(0,0,0,.22); pointer-events: auto; }
.menu .icon { background: #4f7290; color: #fff; width: 18px; height: 18px; border-radius: 5px; font-size: 10.5px; }
.menu button { height: 28px; padding: 0 10px; border: 0; border-radius: 9px; background: none; color: #fff; font-size: 12.5px; font-weight: 600; cursor: pointer; }
.menu button:hover { background: rgba(255,255,255,.14); }
.arrow { position: fixed; left: 50%; transform: translateX(-50%); display: inline-flex; align-items: center; gap: 6px; height: 34px; padding: 0 12px 0 8px;
  border: 0; border-radius: 17px; background: #4f7290; color: #fff; font-size: 13px; font-weight: 600; box-shadow: 0 4px 16px rgba(0,0,0,.2);
  pointer-events: auto; cursor: pointer; }
.arrow.down { bottom: 18px; } .arrow.up { top: 18px; } .dir { font-size: 16px; line-height: 1; }
.toast { position: fixed; right: 18px; bottom: 18px; display: inline-flex; align-items: center; gap: 6px; height: 30px; padding: 0 12px 0 6px;
  border-radius: 15px; background: #4f7290; color: #fff; font-size: 12.5px; font-weight: 600; pointer-events: none; }
.result { position: absolute; border-radius: 10px; pointer-events: none; }
.result.read { box-shadow: 0 0 0 2px #4f7290; }
.result.later { box-shadow: 0 0 0 1.5px #c3c1ba; }
.result.skip { background: rgba(255,255,255,.62); }
.badge { position: absolute; left: -11px; top: 8px; width: 22px; height: 22px; border-radius: 6px; display: grid; place-items: center;
  font-size: 11px; font-weight: 700; }
.read .badge { background: #4f7290; color: #fff; }
.later .badge { background: #fff; color: #7a7d84; box-shadow: inset 0 0 0 1.5px #c3c1ba; }
.skip .badge { background: #ebeae6; color: #a8a6a0; }
.anno { position: absolute; border-radius: 3px; background: rgba(79,114,144,.2); pointer-events: none; }
.anno-frame { position: absolute; border-radius: 10px; box-shadow: 0 0 0 2px #4f7290; background: rgba(79,114,144,.05); pointer-events: none; }
.anno-tag { position: absolute; display: inline-flex; align-items: center; gap: 6px; height: 22px; padding: 0 9px 0 3px; border-radius: 11px;
  background: #4f7290; color: #fff; font-size: 12px; font-weight: 600; white-space: nowrap; pointer-events: none; box-shadow: 0 2px 8px rgba(0,0,0,.18); }
.anno-tag b { display: grid; place-items: center; width: 16px; height: 16px; border-radius: 8px; background: #fff; color: #4f7290; font-size: 10px; }
.focus.anno { background: rgba(79,114,144,.34); }
.focus.anno-frame { box-shadow: 0 0 0 3px #4f7290; background: rgba(79,114,144,.08); }
.focus.anno-tag, .focus.anno-frame { animation: lana-pulse 1.2s ease-out 1; }
@keyframes lana-pulse { 0% { box-shadow: 0 0 0 0 rgba(79,114,144,.55); } 100% { box-shadow: 0 0 0 14px rgba(79,114,144,0); } }
.hover { position: absolute; border-radius: 10px; background: rgba(79,114,144,.10); box-shadow: 0 0 0 1.5px rgba(79,114,144,.55); pointer-events: none; }
[hidden] { display: none !important; }
`;

const ICON = '<span class="icon">L</span>';

export function createLayer(ctx: ContentScriptContext, hooks: Hooks) {
  const host = document.createElement('lana-layer');
  host.style.cssText = 'position:absolute;top:0;left:0;width:0;height:0;z-index:2147483646;pointer-events:none;';
  const root = host.attachShadow({ mode: 'open' });
  root.innerHTML = `<style>${CSS}</style><div id="marks"></div>
    <div class="menu" id="menu" hidden>${ICON}<button id="keep">Keep</button><button id="ask">Ask</button></div>
    <button class="arrow" id="arrow" hidden></button><div class="toast" id="toast" hidden></div>`;
  document.documentElement.append(host);
  ctx.onInvalidated(() => host.remove());

  const $ = <T extends HTMLElement>(id: string) => root.getElementById(id) as T;
  const marks = $('marks');
  const menu = $('menu');
  const arrow = $<HTMLButtonElement>('arrow');
  const toastEl = $('toast');

  // ─── what is marked now, kept as a description so it can be redrawn ───
  let pointed: Element | null = null;
  let results: LabeledResult[] = [];
  let picking: ((heading: Element) => void) | null = null;
  let hovered: Element | null = null;
  let highlighted: { range: Range; text: string } | null = null;
  let annotations: { note: Annotation; range: Range; blocks: Element[] }[] = [];
  let focused: string | null = null;

  const page = (r: DOMRect) => ({ x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height });

  function sectionBox(heading: Element) {
    const level = /^H(\d)$/.exec(heading.tagName)?.[1];
    const top = page(heading.getBoundingClientRect());
    const column = page((heading.parentElement ?? heading).getBoundingClientRect());
    let bottom = column.y + column.h;
    if (level) {
      // The section ends where the next heading of the same level or higher begins.
      const all = [...document.querySelectorAll('h1, h2, h3, h4, h5, h6')];
      const next = all.slice(all.indexOf(heading) + 1).find((h) => Number(h.tagName[1]) <= Number(level));
      if (next) bottom = page(next.getBoundingClientRect()).y - 8;
    }
    return { x: column.x - 12, y: top.y - 10, w: column.w + 24, h: Math.max(top.h + 20, bottom - top.y + 10) };
  }

  function draw() {
    let html = '';
    if (pointed?.isConnected) {
      const b = sectionBox(pointed);
      html += `<div class="frame" style="left:${b.x}px;top:${b.y}px;width:${b.w}px;height:${b.h}px"><span class="tag">${ICON}</span></div>`;
    }
    if (highlighted) {
      // Sites redraw their text after loading: when the range empties, find the words again.
      if (!highlighted.range.toString().trim()) {
        const again = findText(highlighted.text, host);
        if (again) highlighted.range = again;
      }
      for (const r of highlighted.range.getClientRects()) {
        const b = page(r);
        html += `<div class="hl" style="left:${b.x - 1}px;top:${b.y - 1}px;width:${b.w + 2}px;height:${b.h + 2}px"></div>`;
      }
    }
    for (const r of results) {
      if (!r.block.isConnected) continue;
      const b = page(r.block.getBoundingClientRect());
      html += `<div class="result ${r.verdict}" style="left:${b.x - 10}px;top:${b.y - 8}px;width:${b.w + 20}px;height:${b.h + 16}px"><span class="badge">L</span></div>`;
    }
    annotations.forEach((a) => {
      // Sites redraw their text after loading: when the range empties, find the words again.
      if (!a.range.toString().trim()) {
        const again = findText(a.note.text, host);
        if (again) {
          a.range = again;
          if (a.note.block) a.blocks = blockWith(again);
        }
      }
      const cls = a.note.id === focused ? ' focus' : '';
      const tag = (x: number, y: number) =>
        `<span class="anno-tag${cls}" style="left:${x}px;top:${y}px"><b>L</b>${escape(a.note.label)}</span>`;
      if (a.note.block && a.blocks.length) {
        const rects = a.blocks.filter((b) => b.isConnected).map((b) => page(b.getBoundingClientRect()));
        if (!rects.length) return;
        const x = Math.min(...rects.map((r) => r.x)) - 10;
        const y = Math.min(...rects.map((r) => r.y)) - 8;
        const w = Math.max(...rects.map((r) => r.x + r.w)) - x + 10;
        const h = Math.max(...rects.map((r) => r.y + r.h)) - y + 8;
        html += `<div class="anno-frame${cls}" style="left:${x}px;top:${y}px;width:${w}px;height:${h}px"></div>` + tag(x + 10, y - 12);
        return;
      }
      const rects = [...a.range.getClientRects()].map(page);
      rects.forEach((b) => (html += `<div class="anno${cls}" style="left:${b.x - 1}px;top:${b.y - 1}px;width:${b.w + 2}px;height:${b.h + 2}px"></div>`));
      if (rects[0]) html += tag(rects[0].x - 2, rects[0].y - 27);
    });
    if (picking && hovered?.isConnected) {
      const b = sectionBox(hovered);
      html += `<div class="hover" style="left:${b.x}px;top:${b.y}px;width:${b.w}px;height:${b.h}px"></div>`;
    }
    marks.innerHTML = html;
    updateArrow();
  }

  // ─── the scroll arrow: shown only while the marked part is off screen ───
  function target(): Element | null {
    const focus = annotations.find((a) => a.note.id === focused);
    if (focus) return focus.blocks[0] ?? elementOf(focus.range.startContainer);
    if (pointed?.isConnected) return pointed;
    const node = highlighted?.range.startContainer;
    return node ? (node instanceof Element ? node : node.parentElement) : null;
  }
  function updateArrow() {
    const t = target();
    if (!t) return void (arrow.hidden = true);
    const r = t.getBoundingClientRect();
    const below = r.top > innerHeight - 40;
    const above = r.bottom < 40;
    arrow.hidden = !below && !above;
    arrow.className = `arrow ${below ? 'down' : 'up'}`;
    arrow.innerHTML = `${ICON}<span class="dir">${below ? '↓' : '↑'}</span>`;
    arrow.setAttribute('aria-label', below ? 'Scroll down to it' : 'Scroll up to it');
  }
  arrow.addEventListener('click', () => target()?.scrollIntoView({ behavior: 'smooth', block: 'center' }));

  // ─── the selection menu ───
  menu.addEventListener('mousedown', (e) => e.preventDefault()); // keep the selection while clicking
  $('keep').addEventListener('click', () => hooks.onKeep());
  $('ask').addEventListener('click', () => hooks.onAsk());
  let enabled = false;
  ctx.addEventListener(document, 'mouseup', (e) => {
    if (!enabled || e.composedPath().includes(host)) return;
    setTimeout(() => {
      const sel = getSelection();
      if (!sel || sel.isCollapsed || sel.toString().trim().length < 2) return void (menu.hidden = true);
      const r = page(sel.getRangeAt(0).getBoundingClientRect());
      menu.hidden = false;
      menu.style.left = `${Math.max(scrollX + 8, r.x + r.w / 2 - 90)}px`;
      menu.style.top = `${Math.max(scrollY + 8, r.y - 42)}px`;
    });
  });
  ctx.addEventListener(document, 'selectionchange', () => {
    if (getSelection()?.isCollapsed) menu.hidden = true;
  });

  // Picking a part: the learner hovers the page, the part under the pointer lights up, a click picks it.
  ctx.addEventListener(document, 'mousemove', (e) => {
    if (!picking) return;
    const h = headingOf(e.target as Node);
    if (h !== hovered) {
      hovered = h;
      draw();
    }
  });
  ctx.addEventListener(
    document,
    'click',
    (e) => {
      if (!picking || e.composedPath().includes(host)) return;
      e.preventDefault();
      e.stopPropagation();
      const h = headingOf(e.target as Node);
      if (!h) return;
      const done = picking;
      picking = null;
      hovered = null;
      draw();
      done(h);
    },
    { capture: true },
  );
  ctx.addEventListener(document, 'keydown', (e) => {
    if (picking && e.key === 'Escape') {
      picking = null;
      hovered = null;
      draw();
    }
  });

  // Redraw when the page changes size or shifts its layout; recheck the arrow on scroll.
  const redraw = () => (pointed || highlighted || results.length || annotations.length) && draw();
  ctx.addEventListener(window, 'resize', redraw);
  ctx.addEventListener(window, 'scroll', updateArrow, { passive: true });
  const observer = new ResizeObserver(redraw);
  observer.observe(document.body);
  ctx.onInvalidated(() => observer.disconnect());

  let toastTimer = 0;
  return {
    host,
    enable(on: boolean) {
      enabled = on;
      if (!on) {
        pointed = null;
        highlighted = null;
        results = [];
        annotations = [];
        focused = null;
        picking = null;
        menu.hidden = true;
        draw();
      }
    },
    point(heading: Element) {
      pointed = heading;
      draw();
    },
    highlight(range: Range, text: string) {
      highlighted = { range, text };
      draw();
    },
    clear() {
      pointed = null;
      highlighted = null;
      results = [];
      annotations = [];
      focused = null;
      picking = null;
      draw();
    },
    /** Marks each piece where it is, named; answers with the ones found. */
    annotate(list: Annotation[]): string[] {
      annotations = [];
      for (const note of list) {
        const range = findText(note.text, host);
        if (range) annotations.push({ note, range, blocks: note.block ? blockWith(range) : [] });
      }
      draw();
      return annotations.map((a) => a.note.id);
    },
    /** Brings one piece into view and makes it stand out. */
    focus(id: string): boolean {
      const a = annotations.find((n) => n.note.id === id);
      if (!a) return false;
      focused = id;
      draw();
      (a.blocks[0] ?? elementOf(a.range.startContainer))?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return true;
    },
    results(list: LabeledResult[]) {
      results = list;
      draw();
    },
    pick(onPick: ((heading: Element) => void) | null) {
      picking = onPick;
      hovered = null;
      draw();
    },
    hideSelectionMenu() {
      menu.hidden = true;
    },
    toast(text: string) {
      toastEl.innerHTML = `${ICON}${text}`;
      toastEl.hidden = false;
      clearTimeout(toastTimer);
      toastTimer = window.setTimeout(() => (toastEl.hidden = true), 1600);
    },
  };
}

const escape = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!);
const elementOf = (n: Node) => (n instanceof Element ? n : n.parentElement);

/** The passage's own block, and what follows it up to the first code, figure or table. */
function blockWith(range: Range): Element[] {
  const start = elementOf(range.startContainer)?.closest('p, li, dd, div, td');
  if (!start) return [];
  const blocks = [start];
  const isMedia = (e: Element) => e.matches('pre, table, figure, img') || !!e.querySelector('pre, table, figure, img');
  for (let next = start.nextElementSibling, i = 0; next && i < 3; next = next.nextElementSibling, i++) {
    if (next.matches('h1, h2, h3, h4, h5, h6')) break;
    blocks.push(next);
    if (isMedia(next)) return blocks;
  }
  return [start];
}
