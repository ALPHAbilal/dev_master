# Design brief — three teaching artifacts (3 geometric variations)

You are the design lead for an AI code tutor. The **conversation stays plain** — normal text, the
lightest possible chrome. All the creative, geometric energy goes into **three artifact
components only**: generated **code**, a **first-principles** breakdown, and a **concept-evolution**
timeline. Those three are where the geometry of the UI itself is the subject. Deliver **three
distinct variations** of those three components.

## What must stay PLAIN (do not design these — keep them quiet)
The conversation around the artifacts is text-first. Render it, but keep it boring on purpose so
the artifacts stand out:
- **Message turns** `{role:"tutor"|"learner"|"system", text}` — just text. Tutor left, learner
  right, system a muted aside. A learner answer may sit in a plain soft card; the tutor is plain
  text. No bubbles-with-tails, no avatars, no timestamps, no geometry.
- **Tool-call line** `{agent, step, tools:[[name,note]]}` — **just a short line of text**, e.g.
  `TEACHER · read_code_slice L42–46`, muted and monospace-ish. Only `read_code_slice` /
  `read_workspace` ever appear. No icons, no boxes, no chrome beyond a faint line.
- **JUDGE verdict** `{verdict, category, agent:"JUDGE", text}` — a plain, neutral line/blocklet:
  the verdict word, the category, one sentence. No colored side-stripe, no toast, no badge art.
These exist only to give the three artifacts a realistic context. Spend zero creativity here.

## Where ALL the creativity goes — the three artifact components
Reimagine the **geometry of each component itself** — the structure, the way parts sit and relate
— not decoration laid on top. Each of the three variations gives these components a *different*
geometric language, and the geometry must encode each component's own logic.

**1. Generated code** — `{lang:"py", fname, code, collapsed}`. **Collapsible from its header**
(click toggles), monospace, line numbers, light syntax tint. This is the one heavy-monospace
element; make its frame/gutter/header geometry distinctive.
Sample `code`:
```py
def _pinned_qa_group(questions):
    pinned = [q for q in questions if q["pin"]]
    rest   = [q for q in questions if not q["pin"]]
    seen, out = set(), []
    for q in pinned + rest:          # pinned first, order preserved
        if q["id"] not in seen:      # dedupe by value, not object identity
            seen.add(q["id"])
            out.append(q)
    return out
```

**2. First-principles decomposition** — `{claim, atoms:[...ordered...], rebuild}`. An ordered
break-to-atoms, then a synthesis. The numbering is meaningful — the geometry should *show*
decompose → recompose (a splitting-apart then joining, not a plain list).
Sample: claim "Why does the duplicate survive `pinned + rest`?"; atoms ["A list `+` copies
references — it compares nothing.","Two dicts with the same `id` field are still separate
objects.","So `q in seen` on objects checks identity, which is always unique."]; rebuild "Dedupe on
the value you mean (`q[\"id\"]`), never the object."

**3. Concept evolution** — `{stages:[{at, belief}]}`. How one idea changed across turns; the last
stage is "now", earlier ones superseded. The geometry should carry *time and supersession* —
earlier beliefs read as past, the current one as arrived-at.
Sample stages: {"Probe 1","Equality is about identity (`is`)."} → {"Dive · identity","`==`
compares value, `is` compares the object."} → {"Now","Dedupe by the id field's value — not the
dict object."}.

## Non-negotiable constraints
- **Single self-contained `.html` per variation.** Inline all CSS/JS; no images/CDNs. (Google
  Fonts links allowed, with real fallbacks.)
- **LIGHT theme (light gray + muted blue), these exact tokens** — match or evolve, keep character:
  ```
  --bg-deepest#ffffff  --bg-app#f4f4f2 (conversation ground)  --bg-surface#ebeae6
  --bg-card#e3e1db  --bg-elevated#d8d6cf  --bg-hover#cfccc3
  --text-primary#1e2024  --text-secondary#4a4d53  --text-muted#7a7d84  --text-disabled#a8a6a0
  --accent#4f7290 (muted steel blue)  --accent-dim#385876 (deeper blue, for blue text on light)
  --accent-soft rgba(79,114,144,0.15)  --on-accent#ffffff (white text ON blue fills)
  radii 8/12/16px   ui-font:"Segoe UI",system   code-font:"Cascadia Code",ui-monospace
  ```
  Dark text on light gray. Muted blue is a *restrained* signal — deliberate, not everywhere. Text
  on a blue fill uses `--on-accent` (white); blue as text/thin lines uses `--accent-dim`.
- Artifacts sit left-aligned, `max-width ~92%`, in a centered ~780px reading column on `--bg-app`.
- Prose/labels stay **normal weight**; monospace is reserved for the code. Responsive to ~360px;
  visible keyboard focus; respect `prefers-reduced-motion`; AA contrast.

## The creative brief (artifacts only)
Give each variation a **different geometric organizing idea** applied consistently across the three
components — e.g. an isometric/blueprint grid, a node-and-edge circuit, layered strata/stacked
planes, modular tiling, a coordinate/axis system, a split-and-merge diagram. Pick three that truly
differ. The geometry must encode each component's logic (code = frame+gutter; first-principles =
split→merge; evolution = time+supersession). Take one real, justified risk per variation, and in a
one-line note say what the geometric idea is and why it fits a *reasoning* artifact.

## Avoid
- Any geometric treatment leaking onto the plain conversation elements — keep those flat.
- The three AI-default aesthetics (cream+serif+terracotta; black+one-acid-accent; broadsheet hairlines).
- Ornament that doesn't encode meaning; blue used as filler; making the code hard to read.

## Deliverable
Three standalone HTML files (`variation_1.html`, `_2`, `_3`). Each renders a **short plain
transcript for context** (system line → tool-call line → tutor question → learner answer → JUDGE
verdict) followed by the **three richly-designed artifacts** (code first, then first-principles,
then evolution). The code artifact must actually collapse/expand. Put a 1–2 line note at the top of
each file (HTML comment) naming the geometric idea and the one risk taken. The three must be
distinguishable at a glance — and in all three, the plain transcript should look identical/quiet;
only the artifacts differ.
