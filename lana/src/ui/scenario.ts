import type { Piece, Reply, Run, Source, Step } from './conversation';

// A scripted agent, standing in for the real one: a beginner who wants the basics of Amazon S3.
// Lana talks first: what the learner will do with S3, which pieces the session must give, and
// how they connect. It searches once mid-talk, because the talk needs a fact (what AWS itself
// uses for a first upload). Then it finds each piece on its own and answers it twice: in the
// chat, and annotated on the page. The pages and passages are the real ones (checked 2026-10-29).

/** One change to the agent's status line, at a time from the start of the run (ms). */
export type RunEvent =
  | { at: number; label: string }
  | { at: number; step: Step }
  | { at: number; finish: Pick<Step, 'id' | 'state' | 'items'> }
  | { at: number; done: string };

export function applyRunEvent(run: Run, e: RunEvent): Run {
  const settle = (steps: Step[]) => steps.map((s) => (s.kind === 'thinking' && s.state === 'busy' ? { ...s, state: 'done' as const } : s));
  if ('label' in e) return { ...run, label: e.label };
  if ('step' in e) return { ...run, steps: [...settle(run.steps), e.step] };
  if ('finish' in e) return { ...run, steps: run.steps.map((s) => (s.id === e.finish.id ? { ...s, ...e.finish } : s)) };
  return { ...run, running: false, label: e.done, steps: settle(run.steps) };
}

const GUIDE: Source = { url: 'https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html', title: 'What is Amazon S3?', site: 'docs.aws.amazon.com' };
const CLI: Source = { url: 'https://docs.aws.amazon.com/cli/latest/reference/s3/cp.html', title: 'cp · AWS CLI Command Reference', site: 'docs.aws.amazon.com' };

/** The session's pieces, as the talk defines them; `answer` is filled when Lana finds them. */
export const PIECES: Piece[] = [
  {
    id: 'definition',
    number: 1,
    kind: 'definition',
    name: 'Definition',
    what: 'What a bucket and an object are',
  },
  {
    id: 'diagram',
    number: 2,
    kind: 'diagram',
    name: 'Diagram',
    what: 'Bucket → key → object',
    relates: 'draws the definition',
  },
  {
    id: 'code',
    number: 3,
    kind: 'code',
    name: 'Code',
    what: 'Upload one file from the command line',
    relates: 'puts one object in the diagram’s bucket',
  },
];

export const ANSWERS: Record<string, Piece['answer']> = {
  definition: {
    source: GUIDE,
    quote: 'An object is a file and any metadata that describes the file. A bucket is a container for objects.',
    mark: { id: 'definition', label: '1 · Definition', text: 'An object is a file and any metadata that describes the file. A bucket is a container for objects.' },
  },
  diagram: {
    source: GUIDE,
    quote: 'Every object in a bucket has exactly one key.',
    diagram: { from: 'Bucket', via: 'key', to: 'Object' },
    mark: {
      id: 'diagram',
      label: '2 · Diagram',
      text: 'Every object in a bucket has exactly one key. The combination of a bucket, object key, and optionally, version ID (if S3 Versioning is enabled for the bucket) uniquely identify each object.',
    },
  },
  code: {
    source: CLI,
    quote: 'The following cp command copies a single file to a specified bucket and key:',
    code: 'aws s3 cp test.txt s3://amzn-s3-demo-bucket/test2.txt',
    mark: { id: 'code', label: '3 · Code', text: 'Example 1: Copying a local file to S3', block: true },
  },
};

/** What Lana says at each beat of the talk, and the replies it offers. */
export const BEATS: { text: string; replies?: Reply[]; map?: boolean }[] = [
  {
    text: 'Before we look anything up: what will you do with S3 first?',
    replies: [['Store files for an app', 'use'], ['Host a website', 'use'], ['Just understand it', 'use']],
  },
  {
    text: 'Then this session needs three pieces, each building on the one before. One question for the code: will you try it yourself in a terminal?',
    map: true,
    replies: [['Yes, in a terminal', 'code'], ['Not sure yet', 'code']],
  },
  {
    text: 'AWS’s own reference does a first upload with one terminal command, aws s3 cp: a local file into a bucket, under a key. It’s the shortest way to see the diagram happen, so that’s our code piece. Shall I find all three?',
    replies: [['Find them', 'find'], ['Change something', 'change']],
  },
];

/** Mid-talk: the talk needs one fact, so Lana looks it up and comes back. */
export const CHECKING_CODE: RunEvent[] = [
  { at: 0, label: 'Checking what AWS uses for a first upload' },
  { at: 200, step: { id: 'search-cli', kind: 'search', state: 'busy', subject: 'aws cli s3 upload a file' } },
  { at: 1400, label: 'Searching the web' },
  {
    at: 2600,
    finish: {
      id: 'search-cli',
      state: 'done',
      items: [
        { title: 'cp · AWS CLI Command Reference', url: CLI.url, domain: 'docs.aws.amazon.com' },
        { title: 'Use high-level (s3) commands with the AWS CLI', url: 'https://docs.aws.amazon.com/cli/latest/userguide/cli-services-s3-commands.html', domain: 'docs.aws.amazon.com' },
        { title: 'Uploading objects', url: 'https://docs.aws.amazon.com/AmazonS3/latest/userguide/upload-objects.html', domain: 'docs.aws.amazon.com' },
      ],
    },
  },
  { at: 2800, label: 'Searched the web' },
  { at: 3400, done: 'Searched the web' },
];

/** Finding: Lana searches and reads on its own, piece by piece. */
export const FINDING: RunEvent[] = [
  { at: 0, label: 'Sifting' },
  { at: 200, step: { id: 'search-basics', kind: 'search', state: 'busy', subject: 'amazon s3 buckets objects keys' } },
  { at: 1500, label: 'Searching the web' },
  {
    at: 3000,
    finish: {
      id: 'search-basics',
      state: 'done',
      items: [
        { title: 'What is Amazon S3?', url: GUIDE.url, domain: 'docs.aws.amazon.com' },
        { title: 'Amazon S3 objects overview', url: 'https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingObjects.html', domain: 'docs.aws.amazon.com' },
        { title: 'Amazon S3', url: 'https://en.wikipedia.org/wiki/Amazon_S3', domain: 'en.wikipedia.org' },
      ],
    },
  },
  { at: 3200, step: { id: 'read-guide', kind: 'fetch', state: 'busy', subject: GUIDE.url } },
  { at: 3500, label: 'Reading a page' },
  { at: 5200, finish: { id: 'read-guide', state: 'done' } },
  { at: 5300, step: { id: 'think-pieces', kind: 'thinking', state: 'busy', text: 'Matching the definition and the key passage to the pieces.' } },
  { at: 5600, label: 'Matching the passages to the pieces' },
  { at: 7000, step: { id: 'read-cli', kind: 'fetch', state: 'busy', subject: CLI.url } },
  { at: 7600, label: 'Reading a page' },
  { at: 9000, finish: { id: 'read-cli', state: 'done' } },
  { at: 9600, label: 'Marking each piece on its page' },
  { at: 11000, done: 'Found 3 pieces on 2 pages' },
];
