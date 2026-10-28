import { matches, plainUrl, type PageInfo, type PartRef, type ResultLabel, type Verdict } from '@/contract/messages';

// A scripted agent, standing in for the real one: a beginner who wants the basics of Amazon S3.
// Too many places could answer, so Lana searches with the learner, labels the results on the
// search page itself, and asks the learner to open each page worth reading and point to where the
// answer is. Then it says where it would have looked, and frames that part on the page.
// The pages and their parts are the real ones (checked on 2026-10-27).

export const SEARCH = 'what is amazon s3';
export const SEARCH_URL = `https://www.google.com/search?q=${encodeURIComponent(SEARCH)}`;

export interface Source {
  label: ResultLabel;
  alt?: string; // another address for the same page
  title: string;
  site: string;
  open: string;
  why: string;
  answer: PartRef & { say: string };
}

export const SOURCES: Source[] = [
  {
    label: { url: 'docs.aws.amazon.com/amazons3/latest/userguide/welcome.html', verdict: 'read' },
    title: 'What is Amazon S3?',
    site: 'docs.aws.amazon.com',
    open: 'https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html',
    why: 'The official user guide',
    answer: { heading: 'How Amazon S3 works', id: 'CoreConcepts', say: 'buckets, objects and keys, in one short section' },
  },
  {
    label: { url: 'en.wikipedia.org/wiki/amazon_s3', verdict: 'read' },
    alt: 'en.m.wikipedia.org/wiki/amazon_s3',
    title: 'Amazon S3 · Wikipedia',
    site: 'en.wikipedia.org',
    open: 'https://en.wikipedia.org/wiki/Amazon_S3',
    why: 'An independent overview',
    answer: { heading: 'Design', id: 'Design', say: 'the same three ideas, said by someone outside AWS' },
  },
  {
    label: { url: 'aws.amazon.com/s3/faqs', verdict: 'later' },
    title: 'Amazon S3 FAQs',
    site: 'aws.amazon.com',
    open: 'https://aws.amazon.com/s3/faqs/',
    why: 'Good once you have questions of your own',
    answer: { heading: 'General S3 FAQs', id: null, say: 'the first questions everyone asks' },
  },
];

/** Results not worth the learner's time, labeled on the search page too. */
export const SKIP: ResultLabel[] = [
  { url: 'aws.amazon.com/s3', verdict: 'skip' },
  { url: 'aws.amazon.com/pm/serv-s3', prefix: true, verdict: 'skip' },
  { url: 'youtube.com/watch', prefix: true, verdict: 'skip' },
];

export const LABELS: ResultLabel[] = [
  ...SOURCES.flatMap((s) => [s.label, ...(s.alt ? [{ url: s.alt, verdict: s.label.verdict }] : [])]),
  ...SKIP,
];

export const sourceFor = (url: string) =>
  SOURCES.find((s) => matches(url, s.label) || (s.alt ? matches(url, { url: s.alt }) : false)) ?? null;

export const isSearchPage = (url: string) => /^google\.[a-z.]+\/search$/.test(plainUrl(url));

export const samePart = (a: PartRef, b: PartRef) =>
  (!!a.id && a.id === b.id) || (!!a.heading && !!b.heading && a.heading.toLowerCase() === b.heading.toLowerCase());

/** Where the learner stands with each source. */
export type Status = 'unread' | 'reading' | 'done';

export const verdictOf = (s: Source): Verdict => s.label.verdict;

export type { PageInfo };
