import { plainUrl, type Annotation, type Capture } from '@/contract/messages';

// One conversation, shown by two views: the full page (to talk) and the side panel (beside the
// site, to read). It lives in Chrome's session storage, so either view can close and the other
// picks up exactly where it was.
//
// A session goes:  talk ──► find ──► read
//   talk   Lana and the learner define what the session must give: its pieces (a definition,
//          a diagram, code…) and how each relates to the others. Lana searches only when the
//          talk itself needs a fact, then the talk goes on.
//   find   Lana searches and reads on its own, and answers each piece twice, linked: in the
//          chat, and annotated on the page where it found it.
//   read   the learner opens the annotated pages, with Lana in the side panel.

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

export interface Source {
  url: string;
  title: string;
  site: string;
}

/** What a piece is answered with: the passage, where it is, and what the chat shows of it. */
export interface Answer {
  source: Source;
  mark: Annotation;
  quote: string;
  code?: string;
  diagram?: { from: string; via: string; to: string };
}

/** One piece the session must give the learner, and how it relates to the others. */
export interface Piece {
  id: string;
  number: number;
  kind: 'definition' | 'diagram' | 'code';
  name: string;
  what: string;
  relates?: string;
  answer?: Answer;
}

export type Turn =
  | {
      who: 'lana';
      at: number;
      home: Home;
      text: string;
      run?: Run;
      /** Show the session's pieces as a map. */
      map?: boolean;
      /** Show these pieces' answers. */
      answers?: string[];
      replies?: Reply[];
      used?: boolean;
    }
  | { who: 'you'; at: number; text?: string; chip?: string; capture?: Capture };

/** Where the session stands. The full page owns talk and find; reading happens in the panel. */
export type Stage = 'talk' | 'find' | 'read';

export interface Conversation {
  question: string;
  stage: Stage;
  /** How far the scripted talk has gone; the real agent won't need it. */
  beat: number;
  pieces: Piece[];
  /** The piece the learner asked to see on its page. */
  focus: string | null;
  turns: Turn[];
}

export const newConversation = (question: string): Conversation => ({
  question,
  stage: 'talk',
  beat: 0,
  pieces: [],
  focus: null,
  turns: [{ who: 'you', at: Date.now(), text: question }],
});

/** Two addresses are the same page when they match without protocol, query or fragment. */
export const samePage = (a: string, b: string) => plainUrl(a) === plainUrl(b);
