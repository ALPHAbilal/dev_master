import type { Capture } from '@/contract/messages';

// One conversation, shown by two views: the full page (to talk and decide) and the side
// panel (beside the site, to read and show). It lives in Chrome's session storage, so either
// view can close and the other picks up exactly where it was.

/** Where the conversation is kept, in Chrome's session storage. */
export const CONVERSATION_KEY = 'conversation';

/** A reply button: what it says, and the key the view that owns it acts on. */
export type Reply = [label: string, key: string];

/** Which view a turn's buttons belong to. The other view sends the learner there. */
export type Home = 'full' | 'panel';

/** One thing the agent did while working: a thought, a search, a page read. */
export interface Step {
  id: string;
  kind: 'thinking' | 'search' | 'fetch';
  state: 'busy' | 'done' | 'error';
  text?: string;
  subject?: string;
  items?: { title: string; url: string; domain: string }[];
}

/** The agent at work: one status line that changes in place, and the steps behind it. */
export interface Run {
  running: boolean;
  label: string;
  startedAt: number;
  steps: Step[];
}

/** What the session must find, and what the course gets from it. */
export interface Plan {
  find: string[];
  course: string[];
}

/** A search the agent suggests, and what it will give the learner. */
export interface Query {
  text: string;
  width: 'Wide' | 'Narrow';
  gives: string;
}

/** The plan held against what was found. */
export interface CheckItem {
  text: string;
  found: boolean;
}

export type Turn =
  | {
      who: 'lana';
      at: number;
      home: Home;
      text: string;
      run?: Run;
      plan?: Plan;
      queries?: Query[];
      check?: CheckItem[];
      sources?: boolean;
      replies?: Reply[];
      used?: boolean;
    }
  | { who: 'you'; at: number; text?: string; chip?: string; capture?: Capture };

/** Where the session stands. Each view acts only on the stages it owns. */
export type Stage =
  | 'framing' // full page: the agent drafts the plan
  | 'plan' // full page: the learner approves or changes it
  | 'queries' // full page: the learner picks a search
  | 'searching' // side panel: the results page is open
  | 'triage' // side panel: results are labeled, the learner opens pages
  | 'check'; // full page: the plan against the finds

/** Where the learner stands with each source. */
export type SourceStatus = 'unread' | 'reading' | 'done';

export interface Conversation {
  question: string;
  stage: Stage;
  query: string | null;
  plan: Plan | null;
  turns: Turn[];
  sources: SourceStatus[];
  current: number | null;
}

export const newConversation = (question: string, sources: number): Conversation => ({
  question,
  stage: 'framing',
  query: null,
  plan: null,
  turns: [{ who: 'you', at: Date.now(), text: question }],
  sources: Array.from({ length: sources }, () => 'unread'),
  current: null,
});
