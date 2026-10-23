// Goal Book demo: draws on top of the real AWS page from one layer of its own.
// AWS's elements are never edited, except by the "Restyle AWS instead" button,
// which shows the other way and can be undone.
(() => {
  if (document.querySelector("goalbook-layer")) return;

  const TARGET_ID = "CoreConcepts";
  const TARGET_NAME = "How Amazon S3 works";
  const PASSAGE =
    "An object is a file and any metadata that describes the file. A bucket is a container for objects.";

  const state = { point: true, mark: true, hint: true, select: true, restyled: false, small: false };
  let savedRange = null;
  let passageRange = null;
  let toastTimer = 0;
  const restyleUndo = [];

  const icon = (d) =>
    `<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
  const ICON = {
    book: icon('<path d="M3 3.5h4A1.5 1.5 0 0 1 8.5 5v8A1.5 1.5 0 0 0 7 11.5H3zM13 3.5H9.5A1.5 1.5 0 0 0 8 5v8a1.5 1.5 0 0 1 1.5-1.5H13z"/>'),
    ask: icon('<path d="M2.75 3.25h10.5v7.5H8l-3 2.5v-2.5H2.75z"/>'),
    down: icon('<path d="M8 3v10M4 9l4 4 4-4"/>'),
    up: icon('<path d="M8 13V3M4 7l4-4 4 4"/>'),
  };

  // The layer sits beside <body>, not inside it, and is the only element we add.
  const host = document.createElement("goalbook-layer");
  host.style.cssText = "all:initial;position:fixed;inset:0;pointer-events:none;z-index:2147483647";
  document.documentElement.appendChild(host);
  const root = host.attachShadow({ mode: "open" });

  root.innerHTML = `<style>
    :host{all:initial}
    *{box-sizing:border-box;margin:0;font-family:"Inter","Segoe UI",system-ui,-apple-system,sans-serif}
    [hidden]{display:none!important}
    .g{flex:none;width:16px;height:16px;border-radius:4px;background:#4f7290;color:#fff;display:grid;place-items:center;font-size:9.5px;font-weight:700;line-height:1}

    .frame{position:fixed;border-radius:10px;box-shadow:0 0 0 2px #4f7290,0 0 0 8px rgba(79,114,144,.13);animation:in .3s ease-out}
    .label{position:absolute;right:10px;top:-13px;display:inline-flex;align-items:center;gap:6px;height:24px;padding:0 9px 0 4px;border-radius:7px;background:#fff;box-shadow:0 2px 10px rgba(30,32,36,.16);font-size:12px;font-weight:500;color:#385876;white-space:nowrap}

    .hint{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);pointer-events:auto;display:inline-flex;align-items:center;gap:8px;height:36px;padding:0 14px 0 9px;border:0;border-radius:18px;background:#fff;box-shadow:0 6px 22px rgba(30,32,36,.2);font-size:13px;color:#1e2024;cursor:pointer;white-space:nowrap;animation:nudge 1.6s ease-in-out infinite}
    .hint.up{top:24px;bottom:auto}
    .hint svg{color:#4f7290}
    .hint:hover{background:#f4f4f2}

    .menu{position:fixed;pointer-events:auto;display:flex;gap:2px;padding:3px;border-radius:10px;background:#fff;box-shadow:0 6px 22px rgba(30,32,36,.22);animation:in .15s ease-out}
    .menu button{display:inline-flex;align-items:center;gap:6px;height:30px;padding:0 10px;border:0;border-radius:7px;background:none;font-size:13px;color:#4a4d53;cursor:pointer;white-space:nowrap}
    .menu button:hover{background:#ebeae6}
    .menu .main{background:#4f7290;color:#fff;font-weight:500}
    .menu .main:hover{background:#385876}

    .toast{position:fixed;left:50%;top:20px;transform:translateX(-50%);max-width:min(520px,calc(100vw - 32px));display:flex;align-items:center;gap:8px;padding:9px 14px 9px 10px;border-radius:10px;background:#1e2024;color:#fff;font-size:13px;box-shadow:0 8px 26px rgba(30,32,36,.3);animation:in .2s ease-out}
    .toast span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}

    .card{position:fixed;right:16px;bottom:16px;width:308px;max-width:calc(100vw - 32px);pointer-events:auto;background:#fff;color:#1e2024;border-radius:14px;box-shadow:0 14px 44px rgba(30,32,36,.22),0 0 0 1px rgba(30,32,36,.06);font-size:13px;overflow:hidden}
    .card header{display:flex;align-items:center;gap:10px;padding:12px 12px 10px 14px}
    .card header div{flex:1;min-width:0}
    .card header b{display:block;font-size:13px;font-weight:600}
    .card header small{display:block;font-size:12px;color:#7a7d84;margin-top:1px}
    .min{width:26px;height:26px;border:0;border-radius:7px;background:none;color:#7a7d84;font-size:16px;cursor:pointer}
    .min:hover{background:#ebeae6}
    .card.small{width:auto}
    .card.small .body,.card.small header div{display:none}
    .body{padding:0 8px 12px}
    .sec{padding:10px 6px 6px;font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:#a8a6a0}
    .row{width:100%;display:flex;align-items:center;justify-content:space-between;gap:10px;height:34px;padding:0 6px;border:0;border-radius:8px;background:none;font-size:13px;color:#1e2024;text-align:left;cursor:pointer}
    .row:hover{background:#f4f4f2}
    .sw{flex:none;width:28px;height:16px;border-radius:8px;background:#d8d6cf;position:relative;transition:background .15s}
    .sw::after{content:"";position:absolute;left:2px;top:2px;width:12px;height:12px;border-radius:50%;background:#fff;transition:transform .15s}
    .row[aria-pressed="true"] .sw{background:#4f7290}
    .row[aria-pressed="true"] .sw::after{transform:translateX(12px)}
    .proof{display:grid;grid-template-columns:1fr 1fr;gap:6px;padding:0 6px}
    .proof div{padding:8px 10px;border-radius:8px;background:#f4f4f2;font-size:12px;color:#4a4d53;line-height:1.3}
    .proof b{display:block;font-size:18px;font-weight:600;color:#2f6b4f}
    .proof.bad div{background:#fbeeee}
    .proof.bad b{color:#a33a3a}
    .note{padding:8px 6px 0;font-size:12px;line-height:1.45;color:#7a7d84}
    .note.warn{color:#a33a3a}
    .other{margin:10px 6px 0;width:calc(100% - 12px);height:32px;border:1px solid #e3e1db;border-radius:8px;background:#fff;font-size:13px;color:#4a4d53;cursor:pointer}
    .other:hover{background:#f4f4f2}

    @keyframes in{from{opacity:0}to{opacity:1}}
    @keyframes nudge{0%,100%{translate:0 0}50%{translate:0 3px}}
    @media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
  </style>
  <div class="frame" hidden><span class="label"><span class="g">G</span>Look here</span></div>
  <button class="hint" hidden></button>
  <div class="menu" hidden>
    <button class="main" data-act="add">${ICON.book}Add to the book</button>
    <button data-act="ask">${ICON.ask}Ask about this</button>
  </div>
  <div class="toast" hidden><span class="g">G</span><span></span></div>
  <section class="card">
    <header>
      <span class="g">G</span>
      <div><b>Goal Book demo</b><small>Drawing on this page from our own layer</small></div>
      <button class="min" aria-label="Minimize">–</button>
    </header>
    <div class="body">
      <p class="sec">What the agent can show</p>
      <button class="row" data-key="point"><span>Point to “${TARGET_NAME}”</span><i class="sw"></i></button>
      <button class="row" data-key="mark"><span>Highlight the passage</span><i class="sw"></i></button>
      <button class="row" data-key="hint"><span>Scroll hint</span><i class="sw"></i></button>
      <button class="row" data-key="select"><span>Menu on selected text</span><i class="sw"></i></button>
      <p class="sec">Inside AWS's page</p>
      <div class="proof">
        <div><b data-count="added">0</b>elements we added</div>
        <div><b data-count="styled">0</b>AWS elements we restyled</div>
      </div>
      <p class="note" data-note="clean">All of the above lives in one element beside AWS's page, inside its own Shadow DOM.</p>
      <p class="note warn" data-note="dirty" hidden>Possible, but this edits AWS's own page: it breaks when AWS changes the page, and the learner no longer sees the real one.</p>
      <button class="other">Restyle AWS instead</button>
    </div>
  </section>`;

  const $ = (selector) => root.querySelector(selector);
  const frame = $(".frame"), hint = $(".hint"), menu = $(".menu"), toast = $(".toast"), card = $(".card");

  const target = () => document.getElementById(TARGET_ID);
  const targetPart = () => {
    const heading = target();
    return heading ? [heading, heading.nextElementSibling].filter(Boolean) : [];
  };

  // Text is split by <em> tags and line breaks, so match on collapsed whitespace
  // and map back to the real text nodes.
  function findRange(element, text) {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    const positions = [];
    let flat = "", lastSpace = false;
    for (let node; (node = walker.nextNode()); ) {
      for (let i = 0; i < node.data.length; i++) {
        const space = /\s/.test(node.data[i]);
        if (space && lastSpace) continue;
        flat += space ? " " : node.data[i];
        positions.push([node, i]);
        lastSpace = space;
      }
    }
    const at = flat.indexOf(text);
    if (at < 0) return null;
    const range = document.createRange();
    range.setStart(...positions[at]);
    const [endNode, endOffset] = positions[at + text.length - 1];
    range.setEnd(endNode, endOffset + 1);
    return range;
  }

  function renderMark() {
    if (!("highlights" in CSS)) return;
    const paragraph = targetPart()[1];
    const range = (passageRange = state.mark && paragraph ? findRange(paragraph, PASSAGE) : null);
    if (range) CSS.highlights.set("goalbook-passage", new Highlight(range));
    else CSS.highlights.delete("goalbook-passage");
  }

  function showToast(text) {
    toast.lastElementChild.textContent = text;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toast.hidden = true), 2600);
  }

  function renderCard() {
    root.querySelectorAll(".row").forEach((row) =>
      row.setAttribute("aria-pressed", String(state[row.dataset.key])));
    const added = document.body.querySelectorAll("[data-goalbook-added]").length;
    const styled = document.querySelectorAll("[data-goalbook-restyled]").length;
    root.querySelector('[data-count="added"]').textContent = added;
    root.querySelector('[data-count="styled"]').textContent = styled;
    $(".proof").classList.toggle("bad", added + styled > 0);
    $('[data-note="clean"]').hidden = state.restyled;
    $('[data-note="dirty"]').hidden = !state.restyled;
    $(".other").textContent = state.restyled ? "Undo, back to drawing on top" : "Restyle AWS instead";
    card.classList.toggle("small", state.small);
  }

  // The other way: edit AWS's elements directly.
  function restyle(on) {
    const [heading, paragraph] = targetPart();
    if (!heading) return;
    if (on) {
      for (const [element, css] of [
        [heading, "background:#4f7290;color:#fff;padding:6px 12px;border-radius:8px"],
        [paragraph, "font-size:19px;line-height:1.6;background:#fff6d6;padding:8px 12px"],
      ]) {
        restyleUndo.push([element, element.getAttribute("style")]);
        element.style.cssText += ";" + css;
        element.setAttribute("data-goalbook-restyled", "");
      }
      const badge = document.createElement("div");
      badge.setAttribute("data-goalbook-added", "");
      badge.textContent = "Goal Book: start here";
      badge.style.cssText = "display:inline-block;margin:0 0 8px;padding:4px 10px;border-radius:6px;background:#1e2024;color:#fff;font:600 13px system-ui";
      heading.before(badge);
      restyleUndo.push([badge, null, true]);
    } else {
      for (const [element, style, remove] of restyleUndo.splice(0).reverse()) {
        if (remove) { element.remove(); continue; }
        if (style === null) element.removeAttribute("style");
        else element.setAttribute("style", style);
        element.removeAttribute("data-goalbook-restyled");
      }
    }
    state.restyled = on;
  }

  // Follow the page every frame: it can scroll in the window or in an inner box,
  // and it can redraw its text, which empties our range, so find it again.
  function follow() {
    if (state.mark && (!passageRange || passageRange.collapsed)) renderMark();
    const part = targetPart();
    if (state.point && part.length) {
      const rects = part.map((element) => element.getBoundingClientRect());
      const top = rects[0].top - 10, bottom = rects[rects.length - 1].bottom + 10;
      const left = Math.min(...rects.map((rect) => rect.left)) - 12;
      const right = Math.max(...rects.map((rect) => rect.right)) + 12;
      Object.assign(frame.style, { top: top + "px", left: left + "px", width: right - left + "px", height: bottom - top + "px" });
      frame.hidden = bottom < 0 || top > innerHeight;
    } else frame.hidden = true;

    if (state.hint && part.length) {
      const rect = part[0].getBoundingClientRect();
      const below = rect.top > innerHeight - 90, above = rect.bottom < 70;
      hint.hidden = !(below || above);
      if (below || above) {
        const html = `${below ? ICON.down : ICON.up}${below ? "Scroll down" : "Scroll up"} · ${TARGET_NAME}`;
        if (hint.innerHTML !== html) hint.innerHTML = html;
        hint.classList.toggle("up", above);
      }
    } else hint.hidden = true;

    if (!menu.hidden && savedRange) {
      const rect = savedRange.getBoundingClientRect();
      const width = menu.offsetWidth;
      const left = Math.max(8, Math.min(innerWidth - width - 8, rect.left + rect.width / 2 - width / 2));
      const top = rect.top - 44 < 8 ? rect.bottom + 8 : rect.top - 44;
      Object.assign(menu.style, { left: left + "px", top: top + "px" });
    }
    requestAnimationFrame(follow);
  }

  function onSelection() {
    const selection = getSelection();
    const text = selection.toString().trim();
    if (!state.select || !selection.rangeCount || selection.isCollapsed || text.length < 3) {
      menu.hidden = true;
      savedRange = null;
      return;
    }
    savedRange = selection.getRangeAt(0).cloneRange();
    menu.hidden = false;
  }

  const fromLayer = (event) => event.composedPath().includes(host);
  document.addEventListener("mouseup", (event) => { if (!fromLayer(event)) setTimeout(onSelection); }, true);
  document.addEventListener("keyup", (event) => { if (event.shiftKey) setTimeout(onSelection); }, true);
  document.addEventListener("mousedown", (event) => { if (!fromLayer(event)) menu.hidden = true; }, true);

  // Keep the learner's selection alive while they click our menu.
  menu.addEventListener("mousedown", (event) => event.preventDefault());
  menu.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button || !savedRange) return;
    const text = savedRange.toString().trim().replace(/\s+/g, " ");
    const short = text.length > 70 ? text.slice(0, 70) + "…" : text;
    if (button.dataset.act === "add") {
      if ("highlights" in CSS) {
        const saved = CSS.highlights.get("goalbook-saved") || new Highlight();
        saved.add(savedRange);
        CSS.highlights.set("goalbook-saved", saved);
      }
      showToast(`Added to the book · “${short}”`);
    } else {
      showToast(`Sent to the side panel · “${short}”`);
    }
    getSelection().removeAllRanges();
    menu.hidden = true;
  });

  hint.addEventListener("click", () => target()?.scrollIntoView({ behavior: "smooth", block: "center" }));

  card.addEventListener("click", (event) => {
    const row = event.target.closest(".row");
    if (row) {
      state[row.dataset.key] = !state[row.dataset.key];
      if (row.dataset.key === "mark") renderMark();
      if (row.dataset.key === "select" && !state.select) menu.hidden = true;
    } else if (event.target.closest(".other")) {
      restyle(!state.restyled);
    } else if (event.target.closest(".min")) {
      state.small = !state.small;
    } else return;
    renderCard();
  });

  // AWS may still be rendering when we start; wait for the section.
  const started = Date.now();
  (function waitForTarget() {
    if (target()) {
      renderMark();
      renderCard();
      requestAnimationFrame(follow);
    } else if (Date.now() - started < 10000) setTimeout(waitForTarget, 200);
    else showToast(`Could not find “${TARGET_NAME}” on this page`);
  })();
})();
