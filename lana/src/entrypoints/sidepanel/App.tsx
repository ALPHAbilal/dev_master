import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  RESEARCH_OFF,
  toBackground,
  type AnnotateResult,
  type Envelope,
  type FromPanel,
  type MarkResult,
  type PageInfo,
  type PanelStart,
  type Research,
  type ToPanel,
} from '@/contract/messages';
import { newConversation, samePage, type Conversation, type Piece, type Turn } from '@/ui/conversation';
import { Icon } from '@/ui/icons';
import { useConversation } from '@/ui/store';
import { TurnView } from '@/ui/turns';

// The side panel: Lana beside the real site, where the learner reads.
//   off  a single box: what do you want to learn? Answering opens the full page, where Lana talks.
//   on   the same conversation as the full page, compact, with the pieces marked on this page.
// When the learner opens a page that holds pieces, the panel asks the page to annotate every one
// of them, and brings the one the learner chose into view.

const send = (message: FromPanel) => browser.runtime.sendMessage(toBackground(message));
const toPage = (message: Extract<FromPanel, { type: 'panel:to-page' }>['message']) => send({ type: 'panel:to-page', message });

/** Moves the session to the full page and closes the panel. */
function goFull() {
  void send({ type: 'view:full' });
  window.close();
}

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
          await store.start(newConversation(question));
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
        <input autoFocus value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="What do you want to learn?" aria-label="What do you want to learn?" />
        <button className="send" type="submit" disabled={!question.trim()} aria-label="Start">
          <Icon name="arrow" />
        </button>
      </form>
    </div>
  );
}

/* ─── on: the conversation, and the pieces on this page ─── */
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
  const [here, setHere] = useState<string[]>([]);
  const seen = useRef(events.length);
  const body = useRef<HTMLDivElement>(null);
  const { conversation, update } = store;

  // Research started elsewhere (the Goal Book web app): the conversation starts here.
  useEffect(() => {
    if (!conversation && research.question) void store.start(newConversation(research.question));
  }, [conversation, research.question]);

  const you = (t: Omit<Extract<Turn, { who: 'you' }>, 'who' | 'at'>) => update((c) => ({ ...c, turns: [...c.turns, { ...t, who: 'you', at: Date.now() }] }));

  /** Marks every piece that lives on this page, then brings the chosen one into view. */
  async function annotate(p: PageInfo, c: Conversation) {
    const onPage = c.pieces.filter((x) => x.answer && samePage(x.answer.source.url, p.url));
    if (!onPage.length) return setHere([]);
    const r = (await toPage({ type: 'mark:annotate', annotations: onPage.map((x) => x.answer!.mark) })) as AnnotateResult | MarkResult;
    const found = 'found' in r && Array.isArray(r.found) ? r.found : [];
    setHere(found);
    if (c.focus && found.includes(c.focus)) void toPage({ type: 'mark:focus', id: c.focus });
  }

  // What happens on the pages reaches the conversation.
  useEffect(() => {
    const fresh = events.slice(seen.current);
    seen.current = events.length;
    for (const e of fresh) {
      if (e.type === 'panel:page' && conversation) void annotate(e.page, conversation);
      if (e.type === 'panel:picked') void you({ text: e.part.heading ?? '', chip: 'here' });
      if (e.type === 'panel:captured') void you({ capture: e.capture, chip: e.action });
    }
  });

  /** A piece: on this page, scroll to it; on another, go there. */
  function show(id: string) {
    if (here.includes(id)) return void toPage({ type: 'mark:focus', id });
    const url = conversation?.pieces.find((p) => p.id === id)?.answer?.source.url;
    if (url) void update((c) => ({ ...c, focus: id })).then(() => send({ type: 'panel:open', url }));
  }

  useEffect(() => {
    body.current?.scrollTo({ top: body.current.scrollHeight, behavior: 'smooth' });
  }, [conversation?.turns.length]);

  if (!conversation) return <div className="panel" />;
  const marked = conversation.pieces.filter((p) => here.includes(p.id));
  const talking = conversation.stage !== 'read';

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
      {marked.length > 0 && <OnThisPage pieces={marked} onShow={(id) => void toPage({ type: 'mark:focus', id })} />}

      <main className="body" ref={body}>
        <div className="turns">
          {conversation.turns.map((t, k) => (
            <TurnView key={k} turn={t} actions={{ view: 'panel', pieces: conversation.pieces, here, onReply: (key) => key === 'go:full' && goFull(), onShow: show }} />
          ))}
          {talking && (
            <div className="handoff">
              <button className="go" onClick={goFull}>
                <Icon name="expand" size={14} />
                Lana is talking in the full page
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

/** The pieces marked on this page; a click brings one into view. */
function OnThisPage({ pieces, onShow }: { pieces: Piece[]; onShow: (id: string) => void }) {
  return (
    <div className="on-page">
      {pieces.map((p) => (
        <button key={p.id} onClick={() => onShow(p.id)}>
          <span className="num">{p.number}</span>
          {p.name}
        </button>
      ))}
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
