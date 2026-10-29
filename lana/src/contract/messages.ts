// The contract: every message that travels between Lana's three parts.
//
//   PAGE SCRIPT  (content script, inside the website)
//   BACKGROUND   (service worker, the hub: every message goes through it)
//   PANEL        (Chrome's side panel, and Lana's full page: the same app, two sizes)
//
// The page script and the panel never talk directly. The background carries
// messages both ways, and keeps the ones the panel missed while it was closed.

/** The page the learner is on. */
export interface PageInfo {
  url: string;
  title: string;
  site: string;
}

/** The part of a page something belongs to: the nearest heading above it. */
export interface PartRef {
  heading: string | null;
  id: string | null;
}

/** What the learner took from a page, in the shape of what it is. */
export type Capture =
  | { kind: 'text'; text: string; part: PartRef; page: PageInfo }
  | { kind: 'code'; code: string; part: PartRef; page: PageInfo }
  | { kind: 'image'; src: string; alt: string; part: PartRef; page: PageInfo }
  | { kind: 'table'; rows: string[][]; part: PartRef; page: PageInfo };

/** Keep it, or ask Lana about it. */
export type CaptureAction = 'keep' | 'ask';

/** Where the learner asked from. */
export type CaptureSource = 'selection-menu' | 'context-menu' | 'shortcut';

/** Research mode. Off, Lana stays out of the way; on, every surface works with the learner. */
export interface Research {
  active: boolean;
  question: string | null;
  goal: string | null;
  startedAt: number | null;
}

export const RESEARCH_OFF: Research = { active: false, question: null, goal: null, startedAt: null };

/** How a search result is worth the learner's time, shown on the results page itself. */
export type Verdict = 'read' | 'later' | 'skip';

/** A result to label: its address without the protocol, and its verdict. */
export interface ResultLabel {
  url: string;
  prefix?: boolean;
  verdict: Verdict;
}

/** The answer to "point to" or "highlight": found, or why not. */
export type MarkResult = { found: true } | { found: false; reason: 'not-on-page' | 'no-page-script' };

// ─── page script ──► background ──────────────────────────────────────────────

export type FromPage =
  | { type: 'page:opened'; page: PageInfo }
  | { type: 'page:research?' }
  | { type: 'page:picked'; part: PartRef; page: PageInfo }
  | { type: 'page:captured'; action: CaptureAction; source: CaptureSource; capture: Capture };

// ─── background ──► page script ──────────────────────────────────────────────

export type ToPage =
  | { type: 'page:who-are-you' }
  | { type: 'research:changed'; research: Research }
  | { type: 'page:capture'; action: CaptureAction; source: CaptureSource; imageUrl?: string }
  | { type: 'mark:point'; part: PartRef }
  | { type: 'mark:highlight'; text: string }
  | { type: 'mark:clear' }
  | { type: 'mark:results'; results: ResultLabel[] }
  | { type: 'pick:start' }
  | { type: 'pick:stop' };

// ─── panel ──► background ───────────────────────────────────────────────────

export type FromPanel =
  | { type: 'panel:ready' }
  | { type: 'panel:start-research'; question: string }
  | { type: 'panel:stop-research' }
  | { type: 'panel:to-page'; message: Extract<ToPage, { type: `mark:${string}` | `pick:${string}` }> }
  | { type: 'panel:open'; url: string }
  | { type: 'view:full' };

// ─── background ──► panel ───────────────────────────────────────────────────

export type ToPanel =
  | { type: 'panel:research'; research: Research }
  | { type: 'panel:page'; page: PageInfo }
  | { type: 'panel:page-unavailable' }
  | { type: 'panel:picked'; part: PartRef; page: PageInfo }
  | { type: 'panel:captured'; action: CaptureAction; source: CaptureSource; capture: Capture };

/** What the panel gets when it opens: research mode, and what it missed while closed. */
export interface PanelStart {
  research: Research;
  waiting: ToPanel[];
}

// ─── the Goal Book web app ──► background (through externally_connectable) ──

export type FromApp = { type: 'research:start'; goal: string; question: string } | { type: 'research:stop' };

/** Every message carries who it is for, so each part ignores the others' mail. */
export type Envelope =
  | ({ to: 'background' } & (FromPage | FromPanel))
  | ({ to: 'panel' } & ToPanel)
  | ({ to: 'page' } & ToPage);

export const toBackground = (m: FromPage | FromPanel): Envelope => ({ to: 'background', ...m });
export const toPanel = (m: ToPanel): Envelope => ({ to: 'panel', ...m });
export const toPage = (m: ToPage): Envelope => ({ to: 'page', ...m });

/** An address as Lana compares them: no protocol, no www, no query, no fragment, no trailing slash. */
export function plainUrl(url: string): string {
  try {
    const u = new URL(url);
    return (u.hostname.replace(/^www\./, '') + u.pathname).replace(/\/+$/, '').toLowerCase();
  } catch {
    return url.toLowerCase();
  }
}

export function matches(url: string, label: { url: string; prefix?: boolean }): boolean {
  const plain = plainUrl(url);
  return label.prefix ? plain.startsWith(label.url) : plain === label.url;
}
