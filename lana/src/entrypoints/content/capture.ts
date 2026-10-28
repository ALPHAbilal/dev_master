import type { Capture, PageInfo, PartRef } from '@/contract/messages';

// Turning what the learner pointed at into a capture, in the shape of what it is:
// text, code, an image or a table.

export function pageInfo(): PageInfo {
  return { url: location.href, title: document.title, site: location.hostname };
}

const HEADINGS = 'h1, h2, h3, h4, h5, h6';

/** The nearest heading above a node. */
export function headingOf(node: Node | null): Element | null {
  if (!node) return null;
  let found: Element | null = null;
  for (const h of document.querySelectorAll(HEADINGS)) {
    if (h.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING || h.contains(node)) found = h;
    else break;
  }
  return found;
}

/** The part of the page a node belongs to: its heading's text and id. */
export function partOf(node: Node | null): PartRef {
  return partOfHeading(headingOf(node));
}

export function partOfHeading(found: Element | null): PartRef {
  if (!found) return { heading: null, id: null };
  const id = found.id || found.closest('section[id]')?.id || null;
  return { heading: clean(found.textContent ?? ''), id };
}

const clean = (s: string) => s.replace(/\s+/g, ' ').trim();

export function capture({ target, imageUrl }: { target: Element | null; imageUrl?: string }): Capture | null {
  const page = pageInfo();
  const selection = window.getSelection();
  const selected = selection && !selection.isCollapsed ? selection.toString() : '';
  const anchor = selected ? selection!.anchorNode : target;
  const element = anchor instanceof Element ? anchor : (anchor?.parentElement ?? null);
  const part = partOf(anchor ?? null);

  // An image, right-clicked.
  if (imageUrl || (!selected && target instanceof HTMLImageElement)) {
    const img = target instanceof HTMLImageElement ? target : null;
    return { kind: 'image', src: imageUrl ?? img?.src ?? '', alt: img?.alt ?? '', part, page };
  }

  // Code: inside a pre or code block. Spacing is kept exactly.
  const code = element?.closest('pre, code');
  if (code) return { kind: 'code', code: selected || code.textContent || '', part, page };

  // A table, right-clicked with nothing selected: its rows.
  const table = !selected ? element?.closest('table') : null;
  if (table) {
    const rows = [...table.rows].slice(0, 100).map((r) => [...r.cells].map((c) => clean(c.textContent ?? '')));
    return { kind: 'table', rows, part, page };
  }

  // Text: what was selected, or the paragraph right-clicked.
  const text = clean(selected || element?.closest('p, li, td, blockquote, dd')?.textContent || '');
  return text ? { kind: 'text', text, part, page } : null;
}
