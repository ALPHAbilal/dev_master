import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  RESEARCH_OFF,
  toBackground,
  type Envelope,
  type FromPanel,
  type MarkResult,
  type PageInfo,
  type PanelStart,
  type PartRef,
  type Research,
  type ToPanel,
} from '@/contract/messages';
import { newConversation, type Conversation, type SourceStatus, type Turn } from '@/ui/conversation';
import { Icon } from '@/ui/icons';
import { LABELS, SOURCES, isSearchPage, samePart, sourceFor } from '@/ui/scenario';
import { useConversation } from '@/ui/store';
import { TurnView } from '@/ui/turns';

// The side panel: Lana beside the real site, where the learner reads and shows.
//   off  a single box: what do you want to find out? Answering opens the full page.
//   on   the question, the page Lana sees, and the same conversation as the full page.
// Talking things through happens in the full page; the panel hands over when it's time.
// For now a scripted agent (ui/scenario.ts) talks; the real one will use the same messages.

const send = (message: FromPanel) => browser.runtime.sendMessage(toBackground(message));
const toPage = (message: Extract<FromPanel, { type: 'panel:to-page' }>['message']) => send({ type: 'panel:to-page', message });

/** Moves the session to the full page and closes the panel. */
function goFull() {
  void send({ type: 'view:full' });
  window.close();
}

const FULL_STAGES: Conversation['stage'][] = ['framing', 'plan', 'queries', 'check'];

export default function App() {
  const [research, setResearch] = useState<Research>(RESEARCH_OFF);
  const [page, setPage] = useState<PageInfo | null | 'unavailable'>(null);
  const [ready, setReady] = useState(false);
  const [events, setEvents] = useState<ToPanel[]>([]);
  const store = useConversation();

  useEffect(() => {
    const receive = (message: ToPanel) => {
      if (message.type === 'panel:research') setResearch(message.research);
      if (message.type === 'panel:page') setPage(message.page);
      if (message.type === 'panel:page-unavailable') setPage('unavailable');
      setEvents((e) => [...e, message]);
    };
    const listener = (raw: unknown, _sender: unknown, sendResponse: (r: unknown) => void) => {
      const message = raw as Envelope;
      if (message.to !== 'panel') return;
      receive(message);
      sendResponse({ ok: true });
    };
    browser.runtime.onMessage.addListener(listener);
    void send({ type: 'panel:ready' }).then((start) => {
      const s = start as PanelStart | undefined;
      if (s) {
        setResearch(s.research);
        s.waiting.forEach(receive);
      }
      setReady(true);
    });
    return () => browser.runtime.onMessage.removeListener(listener);
  }, []);

  if (!ready || !store.loaded) return <div className="panel" />;
  if (!research.active)
    return (
      <Idle
        onStart={async (question) => {
          await store.start(newConversation(question, SOURCES.length));
          await send({ type: 'panel:start-research', question });
          goFull();
        }}
      />
    );
  return <Active research={research} page={page} events={events} store={store} />;
}

/* ─── off: one box ─── */
function Idle({ onStart }: { onStart: (question: string) => void }) {
  const [question, setQuestion] = useState('');
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (question.trim()) onStart(question.trim());
  };
  return (
    <div className="panel idle">
      <div className="idle-mark" aria-hidden="true">L</div>
      <form className="composer" onSubmit={submit}>
        <input autoFocus value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="What do you want to find out?" aria-label="Research question" />
        <button className="send" type="submit" disabled={!question.trim()} aria-label="Start research">
          <Icon name="arrow" />
        </button>
      </form>
    </div>
  );
}

/* ─── on: the conversation, driven by the scripted agent ─── */
function Active({
  research,
  page,
  events,
  store,
}: {
  research: Research;
  page: PageInfo | null | 'unavailable';
  events: ToPanel[];
  store: ReturnType<typeof useConversation>;
}) {
  const [tools, setTools] = useState(false);
  const seen = useRef(events.length);
  const body = useRef<HTMLDivElement>(null);
  const { conversation, update } = store;

  // Research started elsewhere (the Goal Book web app): the conversation starts here.
  useEffect(() => {
    if (!conversation && research.question) void store.start(newConversation(research.question, SOURCES.length));
  }, [conversation, research.question]);

  const say = (t: Omit<Extract<Turn, { who: 'lana' }>, 'who' | 'at' | 'home'> | Omit<Extract<Turn, { who: 'you' }>, 'who' | 'at'>, who: 'lana' | 'you' = 'lana') =>
    update((c) => ({ ...c, turns: [...c.turns, (who === 'lana' ? { ...t, who, at: Date.now(), home: 'panel' } : { ...t, who, at: Date.now() }) as Turn] }));
  const closeReplies = () => update((c) => ({ ...c, turns: c.turns.map((t) => (t.who === 'lana' && t.replies ? { ...t, used: true } : t)) }));

  function nextOrDone(done: SourceStatus[]) {
    const next = SOURCES.findIndex((s, i) => s.label.verdict === 'read' && done[i] !== 'done');
    if (next >= 0) say({ text: `Next: ${SOURCES[next]!.title}.`, replies: [['Open it', `open:${next}`]] });
    else say({ text: 'That covers what S3 is and how it’s built. Let’s hold it against the plan.', replies: [['Talk it through', 'check']] });
  }

  function answerFor(i: number, picked: PartRef | null) {
    if (!conversation) return;
    const src = SOURCES[i]!;
    const same = picked ? samePart(picked, src.answer) : false;
    say({ text: same ? `Same place I’d look: ${src.answer.say}.` : `I’d look at ${src.answer.heading}: ${src.answer.say}.` });
    void toPage({ type: 'mark:point', part: src.answer });
    const done = conversation.sources.map((s, j) => (j === i ? 'done' : s)) as SourceStatus[];
    void update((c) => ({ ...c, sources: done, current: null }));
    nextOrDone(done);
  }

  // What happens on the pages reaches the conversation.
  useEffect(() => {
    const fresh = events.slice(seen.current);
    seen.current = events.length;
    for (const e of fresh) {
      if (e.type === 'panel:page') onPage(e.page);
      if (e.type === 'panel:picked') {
        const i = SOURCES.findIndex((s) => s === sourceFor(e.page.url));
        say({ text: e.part.heading ?? '', chip: 'here' }, 'you');
        if (i >= 0) answerFor(i, e.part);
      }
      if (e.type === 'panel:captured') say({ capture: e.capture, chip: e.action }, 'you');
    }
  });

  function onPage(p: PageInfo) {
    if (!conversation) return;
    const stage = conversation.stage;
    if (isSearchPage(p.url) && (stage === 'searching' || stage === 'triage')) {
      void toPage({ type: 'mark:results', results: LABELS });
      if (stage === 'searching') {
        void update((c) => ({ ...c, stage: 'triage' }));
        say({ text: 'I marked the results. Three are worth it. Open each one, read, and show me where the answer is.', sources: true });
      }
      return;
    }
    const src = sourceFor(p.url);
    if (!src) return;
    const i = SOURCES.indexOf(src);
    if (conversation.sources[i] === 'done' || conversation.current === i) return;
    void update((c) => ({ ...c, current: i, sources: c.sources.map((x, j) => (j === i ? 'reading' : x)) }));
    say({ text: `${src.title}. Read it, then show me where the answer is.`, replies: [['Show me on the page', `pick:${i}`], ['Not on this page', `none:${i}`]] });
  }

  function reply(key: string, label: string) {
    if (key === 'go:full') return goFull();
    void closeReplies();
    const [what, arg] = key.split(':');
    const i = Number(arg);
    if (what === 'open') void send({ type: 'panel:open', url: SOURCES[i]!.open });
    if (what === 'pick') {
      say({ text: label }, 'you');
      void toPage({ type: 'pick:start' });
    }
    if (what === 'none') {
      say({ text: label }, 'you');
      answerFor(i, null);
    }
    if (what === 'check') void update((c) => ({ ...c, stage: 'check' })).then(goFull);
  }

  useEffect(() => {
    body.current?.scrollTo({ top: body.current.scrollHeight, behavior: 'smooth' });
  }, [conversation?.turns.length]);

  if (!conversation) return <div className="panel" />;
  const waitingInFull = FULL_STAGES.includes(conversation.stage) && !conversation.turns.some((t) => t.who === 'lana' && t.home === 'full' && t.replies && !t.used);

  return (
    <div className="panel">
      <header className="question">
        <span className="live" aria-hidden="true" />
        <h1>{research.question}</h1>
        <button className="icon-btn" onClick={goFull} aria-label="Open the full page">
          <Icon name="expand" />
        </button>
        <button className="icon-btn" onClick={() => setTools((t) => !t)} aria-pressed={tools} aria-label="Mark the page">
          <Icon name="target" />
        </button>
        <button className="icon-btn" onClick={() => void send({ type: 'panel:stop-research' })} aria-label="End research">
          <Icon name="stop" />
        </button>
      </header>
      {tools && <MarkTools />}
      <PageRow page={page} />

      <main className="body" ref={body}>
        <div className="turns">
          {conversation.turns.map((t, k) => (
            <TurnView
              key={k}
              turn={t}
              actions={{
                view: 'panel',
                sources: conversation.sources,
                current: conversation.current,
                onReply: reply,
                onSearch: (q) => void send({ type: 'panel:open', url: `https://www.google.com/search?q=${encodeURIComponent(q)}` }),
                onOpenSource: (i) => void send({ type: 'panel:open', url: SOURCES[i]!.open }),
              }}
            />
          ))}
          {waitingInFull && (
            <div className="handoff">
              <button className="go" onClick={goFull}>
                <Icon name="expand" size={14} />
                Lana is in the full page
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function PageRow({ page }: { page: PageInfo | null | 'unavailable' }) {
  if (page === null) return <div className="page-row"><span className="favicon" /><span className="bar" /></div>;
  if (page === 'unavailable')
    return (
      <div className="page-row off">
        <span className="favicon"><Icon name="eye-off" /></span>
        <span className="bar" />
      </div>
    );
  return (
    <div className="page-row" title={page.url}>
      <span className="favicon">{page.site.replace(/^www\./, '').charAt(0).toUpperCase()}</span>
      <span className="page-title">{page.title || page.site}</span>
    </div>
  );
}

/* the marks, by hand, until the agent sends them */
function MarkTools() {
  const [words, setWords] = useState('');
  const [result, setResult] = useState<'found' | 'missing' | null>(null);
  async function mark(kind: 'point' | 'highlight' | 'clear') {
    const message =
      kind === 'point'
        ? ({ type: 'mark:point', part: { heading: words, id: null } } as const)
        : kind === 'highlight'
          ? ({ type: 'mark:highlight', text: words } as const)
          : ({ type: 'mark:clear' } as const);
    const reply = (await toPage(message)) as MarkResult | { ok: true };
    setResult('found' in reply ? (reply.found ? 'found' : 'missing') : null);
  }
  return (
    <div className="tools">
      <input value={words} onChange={(e) => { setWords(e.target.value); setResult(null); }} placeholder="Heading or words" aria-label="Heading or words to mark" />
      <button className="icon-btn" disabled={!words.trim()} onClick={() => void mark('point')} aria-label="Point to this heading"><Icon name="frame" /></button>
      <button className="icon-btn" disabled={!words.trim()} onClick={() => void mark('highlight')} aria-label="Highlight these words"><Icon name="highlight" /></button>
      <button className="icon-btn" onClick={() => void mark('clear')} aria-label="Clear the marks"><Icon name="clear" /></button>
      {result && <span className={`result ${result}`} aria-label={result === 'found' ? 'Found' : 'Not on this page'}><Icon name={result === 'found' ? 'check' : 'cross'} /></span>}
    </div>
  );
}
