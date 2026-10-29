import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { toBackground, type FromPanel } from '@/contract/messages';
import { newConversation, type Conversation, type Run, type Turn } from '@/ui/conversation';
import { Icon } from '@/ui/icons';
import { CHECK, FRAMING, PLAN, QUERIES, SOURCES, applyRunEvent, searchUrl, type RunEvent } from '@/ui/scenario';
import { useConversation } from '@/ui/store';
import { TurnView } from '@/ui/turns';

// Lana's full page: where the learner and Lana talk things through.
// It owns three moments of a research session: framing the question into a plan, choosing the
// searches (and what each will give), and checking the finds against the plan. Reading happens
// on the real site, with Lana in the side panel; searching hands over to it.
// For now a scripted agent (ui/scenario.ts) talks; the real one will use the same conversation.

const send = (message: FromPanel) => browser.runtime.sendMessage(toBackground(message));
type LanaTurn = Extract<Turn, { who: 'lana' }>;

/** Scripted runs already playing in this page, so a re-render or StrictMode never starts one twice. */
const playing = new Set<string>();

export default function FullPage() {
  const { conversation, loaded, update, start } = useConversation();
  const windowId = useRef<number | undefined>(undefined);
  const thread = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void browser.windows.getCurrent().then((w) => (windowId.current = w.id));
  }, []);

  const lana = (t: Omit<LanaTurn, 'who' | 'at' | 'home'>): LanaTurn => ({ ...t, who: 'lana', at: Date.now(), home: 'full' });
  const you = (text: string, chip?: string): Turn => ({ who: 'you', at: Date.now(), text, chip });
  const push = (...turns: Turn[]) => update((c) => ({ ...c, turns: [...c.turns, ...turns] }));
  const closeReplies = () => update((c) => ({ ...c, turns: c.turns.map((t) => (t.who === 'lana' && t.home === 'full' && (t.replies || t.queries) ? { ...t, used: true } : t)) }));

  /** Plays a scripted run on a new turn, then hands its final state to `after`. */
  function play(key: string, events: RunEvent[], after: (c: Conversation) => Conversation) {
    if (playing.has(key)) return;
    playing.add(key);
    const startedAt = Date.now();
    let index = -1;
    void update((c) => {
      index = c.turns.length;
      return { ...c, turns: [...c.turns, lana({ text: '', run: { running: true, label: '', startedAt, steps: [] } })] };
    });
    const setRun = (change: (r: Run) => Run) =>
      update((c) => ({ ...c, turns: c.turns.map((t, i) => (i === index && t.who === 'lana' && t.run ? { ...t, run: change(t.run) } : t)) }));
    for (const e of events) setTimeout(() => void setRun((r) => applyRunEvent(r, e)), e.at);
    setTimeout(() => void update(after), events[events.length - 1]!.at + 500);
  }

  // The moments this page owns start on their own when the session reaches them.
  useEffect(() => {
    if (!conversation) return;
    const id = String(conversation.turns[0]?.at ?? 0);
    if (conversation.stage === 'framing')
      play(`frame-${id}`, FRAMING, (c) => ({
        ...c,
        stage: 'plan',
        plan: PLAN,
        turns: [
          ...c.turns,
          lana({ text: 'Here’s how I’d frame it. Change anything before we search.', plan: PLAN, replies: [['Looks good', 'plan:ok'], ['Change something', 'plan:change']] }),
        ],
      }));
    if (conversation.stage === 'check')
      play(`check-${id}-${conversation.turns.length}`, CHECKING, (c) => ({
        ...c,
        stage: 'queries',
        turns: [
          ...c.turns,
          lana({ text: 'What S3 is for and how it’s built: found, in two places. How you pay: still missing. One narrow search should close it.', check: CHECK, queries: [QUERIES[2]!] }),
        ],
      }));
  }, [conversation?.stage]);

  useEffect(() => {
    thread.current?.lastElementChild?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [conversation?.turns.length]);

  function reply(key: string, label: string) {
    if (key === 'go:panel') return backToPage();
    void closeReplies();
    void push(you(label));
    if (key === 'plan:ok')
      void update((c) => ({
        ...c,
        stage: 'queries',
        turns: [...c.turns, lana({ text: 'Start wide, then narrow. Here’s what each search will give you. Edit any of them, then search.', queries: QUERIES })],
      }));
    if (key === 'plan:change') void push(lana({ text: 'Tell me what to add, remove or reword.' }));
  }

  /** The learner wrote something. In the plan, it becomes part of it; elsewhere Lana notes it. */
  function say(text: string) {
    if (!conversation) return;
    if (conversation.stage === 'plan') {
      void closeReplies();
      const plan = { ...(conversation.plan ?? PLAN), find: [...(conversation.plan ?? PLAN).find, text] };
      void update((c) => ({
        ...c,
        plan,
        turns: [...c.turns, you(text), lana({ text: 'Added. Here’s the plan now.', plan, replies: [['Looks good', 'plan:ok'], ['Change something', 'plan:change']] })],
      }));
    } else void push(you(text), lana({ text: 'Noted. I’ll keep that in mind.' }));
  }

  /** Searching happens on the real results page, with Lana in the side panel beside it. */
  function search(query: string) {
    // Opening the panel needs the click itself, so it comes before anything awaited.
    if (windowId.current !== undefined) void browser.sidePanel.open({ windowId: windowId.current });
    void closeReplies()
      .then(() => update((c) => ({ ...c, query, stage: 'searching', turns: [...c.turns, you(query, 'search')] })))
      .then(() => send({ type: 'panel:open', url: searchUrl(query) }));
  }

  /** Back to the site: the side panel opens and this page closes. */
  function backToPage() {
    if (windowId.current !== undefined) void browser.sidePanel.open({ windowId: windowId.current });
    void browser.tabs.getCurrent().then((tab) => {
      if (tab?.id) void browser.tabs.remove(tab.id);
    });
  }

  if (!loaded) return <div className="full" />;
  if (!conversation)
    return (
      <div className="full empty">
        <div className="hero">
          <h1>
            <span className="hero-mark" aria-hidden="true">L</span>
            What do you want to learn?
          </h1>
          <Composer
            autoFocus
            placeholder="A topic, a question, a goal…"
            onSend={(question) => {
              void start(newConversation(question, SOURCES.length)).then(() => send({ type: 'panel:start-research', question }));
            }}
          />
        </div>
      </div>
    );

  const reading = conversation.stage === 'searching' || conversation.stage === 'triage';
  return (
    <div className="full">
      <header className="top">
        <span className="brand"><span className="hero-mark small" aria-hidden="true">L</span>Lana</span>
        <h1 title={conversation.question}>{conversation.question}</h1>
        {reading && (
          <button className="top-btn" onClick={backToPage}>
            <Icon name="panel" size={14} />
            Back to the page
          </button>
        )}
        <button className="top-btn quiet" onClick={() => void send({ type: 'panel:stop-research' })} aria-label="End research">
          <Icon name="stop" size={14} />
        </button>
      </header>
      <main className="thread" ref={thread}>
        {conversation.turns.map((t, k) => (
          <TurnView
            key={k}
            turn={t}
            actions={{
              view: 'full',
              sources: conversation.sources,
              current: conversation.current,
              onReply: reply,
              onSearch: search,
              onOpenSource: backToPage,
            }}
          />
        ))}
      </main>
      <div className="dock">
        <Composer placeholder={conversation.stage === 'plan' ? 'Add to the plan…' : 'Reply to Lana…'} onSend={say} />
      </div>
    </div>
  );
}

/** Checking the finds against the plan, before saying what's missing. */
const CHECKING: RunEvent[] = [
  { at: 0, label: 'Comparing your finds with the plan' },
  { at: 300, step: { id: 'think-check', kind: 'thinking', state: 'busy', text: 'Holding each find against the plan.' } },
  { at: 2600, done: 'Compared 2 finds with the plan' },
];

function Composer({ placeholder, onSend, autoFocus }: { placeholder: string; onSend: (text: string) => void; autoFocus?: boolean }) {
  const [text, setText] = useState('');
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!text.trim()) return;
    onSend(text.trim());
    setText('');
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };
  return (
    <form className="composer-box" onSubmit={submit}>
      <textarea
        rows={1}
        autoFocus={autoFocus}
        value={text}
        placeholder={placeholder}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKey}
        aria-label={placeholder}
      />
      <button className="send" type="submit" disabled={!text.trim()} aria-label="Send">
        <Icon name="arrow" />
      </button>
    </form>
  );
}
