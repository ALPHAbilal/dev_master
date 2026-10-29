import { matches, plainUrl, type PageInfo, type PartRef, type ResultLabel, type Verdict } from '@/contract/messages';
import type { CheckItem, Plan, Query, Run, Step } from './conversation';

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

export const verdictOf = (s: Source): Verdict => s.label.verdict;

export type { PageInfo };

// ─── the full page: frame the question, then choose the searches ─────────────

/** One change to the agent's status line, at a time from the start of the run. */
export type RunEvent =
  | { at: number; label: string }
  | { at: number; step: Step }
  | { at: number; finish: Pick<Step, 'id' | 'state' | 'items'> }
  | { at: number; done: string };

/** Lana reads the question and looks around before proposing a plan. Times in ms. */
export const FRAMING: RunEvent[] = [
  { at: 0, label: 'Sifting' },
  { at: 300, step: { id: 'think-1', kind: 'thinking', state: 'busy', text: 'Reading the question: the basics of Amazon S3.' } },
  { at: 1400, step: { id: 'search-1', kind: 'search', state: 'busy', subject: 'amazon s3 for beginners' } },
  { at: 1800, label: 'Searching the web' },
  {
    at: 3600,
    finish: {
      id: 'search-1',
      state: 'done',
      items: [
        { title: 'What is Amazon S3?', url: 'https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html', domain: 'docs.aws.amazon.com' },
        { title: 'Getting started with Amazon S3', url: 'https://docs.aws.amazon.com/AmazonS3/latest/userguide/GetStartedWithS3.html', domain: 'docs.aws.amazon.com' },
        { title: 'Amazon S3', url: 'https://en.wikipedia.org/wiki/Amazon_S3', domain: 'en.wikipedia.org' },
        { title: 'Amazon S3 FAQs', url: 'https://aws.amazon.com/s3/faqs/', domain: 'aws.amazon.com' },
        { title: 'Amazon S3 pricing', url: 'https://aws.amazon.com/s3/pricing/', domain: 'aws.amazon.com' },
      ],
    },
  },
  { at: 3800, label: 'Searched the web' },
  { at: 4400, step: { id: 'think-2', kind: 'thinking', state: 'busy', text: 'Splitting it into what you need to find.' } },
  { at: 5800, label: 'Splitting it into what you need to find' },
  { at: 7600, done: 'Searched the web, read 5 results' },
];

export function applyRunEvent(run: Run, e: RunEvent): Run {
  const settle = (steps: Step[]) => steps.map((s) => (s.kind === 'thinking' && s.state === 'busy' ? { ...s, state: 'done' as const } : s));
  if ('label' in e) return { ...run, label: e.label };
  if ('step' in e) return { ...run, steps: [...settle(run.steps), e.step] };
  if ('finish' in e) return { ...run, steps: run.steps.map((s) => (s.id === e.finish.id ? { ...s, ...e.finish } : s)) };
  return { ...run, running: false, label: e.done, steps: settle(run.steps) };
}

export const PLAN: Plan = {
  find: ['What S3 is for', 'Buckets, objects and keys', 'How you pay'],
  course: ['A definition', 'A diagram', 'One practice task'],
};

export const QUERIES: Query[] = [
  { text: SEARCH, width: 'Wide', gives: 'The official guide and an independent overview. Start here.' },
  { text: 'amazon s3 buckets objects keys explained', width: 'Narrow', gives: 'The three core ideas, each in plain words.' },
  { text: 'amazon s3 pricing free tier', width: 'Narrow', gives: 'How you pay, and what stays free while you learn.' },
];

/** The plan held against what the scripted reading found: pricing is the gap. */
export const CHECK: CheckItem[] = [
  { text: PLAN.find[0]!, found: true },
  { text: PLAN.find[1]!, found: true },
  { text: PLAN.find[2]!, found: false },
];

export const searchUrl = (query: string) => `https://www.google.com/search?q=${encodeURIComponent(query)}`;
