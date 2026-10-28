import type { PartRef } from '@/contract/messages';

// Finding things on the live page: a part by its id or heading, a passage by its exact words.

const clean = (s: string) => s.replace(/\s+/g, ' ').trim().toLowerCase();

/** A part: by its id when there is one, else by its heading's text. */
export function findHeading(part: PartRef): Element | null {
  if (part.id) {
    const byId = document.getElementById(part.id);
    if (byId) return byId.matches('h1, h2, h3, h4, h5, h6') ? byId : (byId.querySelector('h1, h2, h3, h4, h5, h6') ?? byId);
  }
  if (!part.heading) return null;
  const wanted = clean(part.heading);
  for (const h of document.querySelectorAll('h1, h2, h3, h4, h5, h6')) if (clean(h.textContent ?? '') === wanted) return h;
  return null;
}

/** A passage: its exact words, wherever the site split them across elements. */
export function findText(text: string, skip: Element): Range | null {
  const wanted = text.replace(/\s+/g, ' ').trim();
  if (!wanted) return null;

  // Walk the visible text, joined with single spaces, and remember where each piece came from.
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => {
      const p = n.parentElement;
      if (!p || skip.contains(p) || p.closest('script, style, noscript, template')) return NodeFilter.FILTER_REJECT;
      return n.nodeValue && n.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
    },
  });
  let joined = '';
  const map: { node: Text; at: number }[] = [];
  for (let n = walker.nextNode() as Text | null; n; n = walker.nextNode() as Text | null) {
    const piece = n.nodeValue!.replace(/\s+/g, ' ');
    if (joined && !joined.endsWith(' ') && !piece.startsWith(' ')) joined += ' ';
    map.push({ node: n, at: joined.length });
    joined += piece;
  }

  const start = joined.indexOf(wanted);
  if (start < 0) return null;
  const end = start + wanted.length;
  const locate = (pos: number) => {
    let i = map.length - 1;
    while (i > 0 && map[i]!.at > pos) i--;
    const { node, at } = map[i]!;
    // Offsets inside the original node, whose spaces were not collapsed.
    const raw = node.nodeValue!;
    let seen = 0;
    let k = 0;
    const target = pos - at;
    while (k < raw.length && seen < target) {
      if (/\s/.test(raw.charAt(k))) {
        while (k + 1 < raw.length && /\s/.test(raw.charAt(k + 1))) k++;
      }
      k++;
      seen++;
    }
    return { node, offset: Math.min(k, raw.length) };
  };
  const a = locate(start);
  const b = locate(end);
  const range = document.createRange();
  range.setStart(a.node, a.offset);
  range.setEnd(b.node, b.offset);
  return range;
}
