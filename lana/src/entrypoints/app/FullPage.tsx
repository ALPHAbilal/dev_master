import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { toBackground, type FromPanel } from '@/contract/messages';
import { newConversation, type Conversation, type Run, type Turn } from '@/ui/conversation';
import { Icon } from '@/ui/icons';
import { ANSWERS, BEATS, CHECKING_CODE, FINDING, PIECES, applyRunEvent, type RunEvent } from '@/ui/scenario';
import { useConversation } from '@/ui/store';
import { TurnView } from '@/ui/turns';

// Lana's full page: where the learner and Lana talk.
// First they define the session: what it must give (a definition, a diagram, code…) and how
// each piece relates to the others. Lana searches only when the talk needs a fact, then the
// talk goes on. Then Lana finds every piece on its own and answers each one twice, linked:
// here in the chat, and annotated on the page it came from ("Show on the page").
// For now a scripted agent (ui/scenario.ts) talks; the real one will use the same conversation.

const send = (message: FromPanel) => browser.runtime.sendMessage(toBackground(message));
type LanaTurn = Extract<Turn, { who: 'lana' }>;

/** Scripted moments already started in this page, so a re-render or StrictMode never starts one twice. */
const started = new Set<string>();

export default function FullPage() {
  const { conversation, loaded, update, start } = useConversation();
  const windowId = useRef<number | undefined>(undefined);
  const thread = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void browser.windows.getCurrent().then((w) => (windowId.current = w.id));
  }, []);

  const lana = (t: Omit<LanaTurn, 'who' | 'at' | 'home'>): LanaTurn => ({ ...t, who: 'lana', at: Date.now(), home: 'full' });
  const you = (text: string): Turn => ({ who: 'you', at: Date.now(), text });
  const closeReplies = () => update((c) => ({ ...c, turns: c.turns.map((t) => (t.who === 'lana' && t.replies && !t.used ? { ...t, used: true } : t)) }));
  const beat = (c: Conversation): Conversation => {
    const b = BEATS[c.beat];
    return b ? { ...c, beat: c.beat + 1, turns: [...c.turns, lana(b)] } : c;
  };

  /** Plays a scripted run on a new turn of its own, then applies `after`. */
  function play(key: string, events: RunEvent[], after: (c: Conversation) => Conversation) {
    if (started.has(key)) return;
    started.add(key);
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

  // A new session opens with Lana's first question; no search yet.
  useEffect(() => {
    if (!conversation || conversation.beat > 0) return;
    const key = `open-${conversation.turns[0]?.at}`;
    if (started.has(key)) return;
    started.add(key);
    setTimeout(() => void update(beat), 600);
  }, [conversation?.beat]);

  useEffect(() => {
    thread.current?.lastElementChild?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [conversation?.turns.length]);

  function reply(key: string, label: string) {
    if (key === 'go:panel') return backToPage();
    void closeReplies();
    void update((c) => ({ ...c, turns: [...c.turns, you(label)] }));
    const id = conversation?.turns[0]?.at;
    if (key === 'use') void update((c) => beat({ ...c, pieces: PIECES }));
    if (key === 'code') {
      // The talk needs a fact before it can go on: Lana looks it up, then answers.
      play(`check-${id}`, CHECKING_CODE, beat);
    }
    if (key === 'find') {
      void update((c) => ({ ...c, stage: 'find' }));
      play(`find-${id}`, FINDING, (c) => ({
        ...c,
        stage: 'read',
        pieces: c.pieces.map((p) => ({ ...p, answer: ANSWERS[p.id] })),
        turns: [
          ...c.turns,
          lana({
            text: 'Here they are, each one marked on the page it came from. The diagram draws the definition; the code puts one object into that bucket.',
            answers: c.pieces.map((p) => p.id),
          }),
        ],
      }));
    }
    if (key === 'change') void update((c) => ({ ...c, turns: [...c.turns, lana({ text: 'Tell me what to add, remove or change.' })] }));
  }

  /** The learner wrote something. The scripted agent notes it and offers to go on. */
  function say(text: string) {
    void closeReplies();
    const ready = conversation?.beat === BEATS.length && conversation.stage === 'talk';
    void update((c) => ({
      ...c,
      turns: [...c.turns, you(text), lana({ text: ready ? 'Noted. Shall I find the pieces now?' : 'Noted. I’ll keep that in mind.', replies: ready ? [['Find them', 'find']] : undefined })],
    }));
  }

  /** A piece on its page: the side panel opens, and this tab goes to the page with every piece marked. */
  function show(pieceId: string) {
    // Opening the panel needs the click itself, so it comes before anything awaited.
    if (windowId.current !== undefined) void browser.sidePanel.open({ windowId: windowId.current });
    const url = conversation?.pieces.find((p) => p.id === pieceId)?.answer?.source.url;
    if (!url) return;
    void update((c) => ({ ...c, focus: pieceId })).then(() => send({ type: 'panel:open', url }));
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
            onSend={(question) => void start(newConversation(question)).then(() => send({ type: 'panel:start-research', question }))}
          />
        </div>
      </div>
    );

  return (
    <div className="full">
      <header className="top">
        <span className="brand"><span className="hero-mark small" aria-hidden="true">L</span>Lana</span>
        <h1 title={conversation.question}>{conversation.question}</h1>
        {conversation.focus && (
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
          <TurnView key={k} turn={t} actions={{ view: 'full', pieces: conversation.pieces, onReply: reply, onShow: show }} />
        ))}
      </main>
      <div className="dock">
        <Composer placeholder="Reply to Lana…" onSend={say} />
      </div>
    </div>
  );
}

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
