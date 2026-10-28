import { matches, type ResultLabel, type Verdict } from '@/contract/messages';

// The results on a search page: each result's link, matched against the labels the panel sent.
// A result is a link that holds a title (h3), the way Google and most engines draw them.

export interface LabeledResult {
  block: Element;
  verdict: Verdict;
  url: string;
}

export function labelResults(labels: ResultLabel[]): LabeledResult[] {
  const out: LabeledResult[] = [];
  const seen = new Set<string>();
  for (const title of document.querySelectorAll('a h3')) {
    const link = title.closest('a');
    if (!link?.href) continue;
    const label = labels.find((l) => matches(link.href, l));
    if (!label || seen.has(label.url)) continue;
    seen.add(label.url);
    // The result's whole block: the link, its address line and its snippet.
    const block = link.closest('[data-hveid], [data-sokoban-container], .g, li') ?? link;
    out.push({ block, verdict: label.verdict, url: label.url });
  }
  return out;
}
