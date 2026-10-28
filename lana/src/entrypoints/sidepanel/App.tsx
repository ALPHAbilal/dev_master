import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  RESEARCH_OFF,
  toBackground,
  type Capture,
  type Envelope,
  type FromPanel,
  type MarkResult,
  type PageInfo,
  type PanelStart,
  type PartRef,
  type Research,
  type ToPanel,
} from '@/contract/messages';
import { Icon } from './icons';
import { LABELS, SEARCH, SEARCH_URL, SOURCES, isSearchPage, samePart, sourceFor, type Status } from './scenario';

// The side panel. Two states, and nothing that explains itself in words:
//   off  a single box: what do you want to find out?
//   on   the question, the page Lana sees, and the conversation with Lana.
// For now a scripted agent (scenario.ts) talks; the real one will use the same messages.

type Reply = [label: string, key: string];
type Turn =
  | { who: 'lana'; text: string; replies?: Reply[]; used?: boolean; sources?: boolean }
  | { who: 'you'; text?: string; chip?: string; capture?: Capture };

const send = (message: FromPanel) => browser.runtime.sendMessage(toBackground(message));
const toPage = (message: Extract<FromPanel, { type: 'panel:to-page' }>['message']) => send({ type: 'panel:to-page', message });

export default function App() {
  const [research, setResearch] = useState<Research>(RESEARCH_OFF);
  const [page, setPage] = useState<PageInfo | null | 'unavailable'>(null);
  const [ready, setReady] = useState(false);
  const [events, setEvents] = useState<ToPanel[]>([]);

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

  if (!ready) return <div className="panel" />;
  return research.active ? (
    <Active key={research.startedAt ?? 0} research={research} page={page} events={events} />
  ) : (
    <Idle onStart={(question) => void send({ type: 'panel:start-research', question }).then((r) => setResearch(r as Research))} />
  );
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
function Active({ research, page, events }: { research: Research; page: PageInfo | null | 'unavailable'; events: ToPanel[] }) {
  const [tools, setTools] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([
    { who: 'lana', text: 'Lots of places answer this. Let’s search first, then pick what’s worth reading.', replies: [['Search Google', 'search']] },
  ]);
  const [status, setStatus] = useState<Status[]>(SOURCES.map(() => 'unread'));
  const [phase, setPhase] = useState<'start' | 'searching' | 'triage'>('start');
  const [current, setCurrent] = useState<number | null>(null);
  const seen = useRef(events.length);
  const body = useRef<HTMLDivElement>(null);

  const say = (t: Turn) => setTurns((all) => [...all, t]);
  const closeReplies = () => setTurns((all) => all.map((t) => (t.who === 'lana' && t.replies ? { ...t, used: true } : t)));

  function nextOrDone(done: Status[]) {
    const next = SOURCES.findIndex((s, i) => s.label.verdict === 'read' && done[i] !== 'done');
    if (next >= 0) say({ who: 'lana', text: `Next: ${SOURCES[next]!.title}.`, replies: [['Open it', `open:${next}`]] });
    else say({ who: 'lana', text: 'Same answer in two places, said two ways. Keep what helps you.' });
  }

  function answerFor(i: number, picked: PartRef | null) {
    const src = SOURCES[i]!;
    const same = picked ? samePart(picked, src.answer) : false;
    say({ who: 'lana', text: same ? `Same place I’d look: ${src.answer.say}.` : `I’d look at ${src.answer.heading}: ${src.answer.say}.` });
    void toPage({ type: 'mark:point', part: src.answer });
    const done = status.map((s, j) => (j === i ? 'done' : s)) as Status[];
    setStatus(done);
    setCurrent(null);
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
        say({ who: 'you', text: e.part.heading ?? '', chip: 'here' });
        if (i >= 0) answerFor(i, e.part);
      }
      if (e.type === 'panel:captured') say({ who: 'you', capture: e.capture, chip: e.action });
    }
  });

  function onPage(p: PageInfo) {
    if (isSearchPage(p.url) && phase !== 'start') {
      void toPage({ type: 'mark:results', results: LABELS });
      if (phase === 'searching') {
        setPhase('triage');
        say({ who: 'lana', text: 'I marked the results. Three are worth it. Open each one, read, and show me where the answer is.', sources: true });
      }
      return;
    }
    const src = sourceFor(p.url);
    if (!src) return;
    const i = SOURCES.indexOf(src);
    if (status[i] === 'done' || current === i) return;
    setCurrent(i);
    setStatus((s) => s.map((x, j) => (j === i ? 'reading' : x)) as Status[]);
    say({ who: 'lana', text: `${src.title}. Read it, then show me where the answer is.`, replies: [['Show me on the page', `pick:${i}`], ['Not on this page', `none:${i}`]] });
  }

  function reply(key: string, label: string) {
    closeReplies();
    const [what, arg] = key.split(':');
    const i = Number(arg);
    if (what === 'search') {
      say({ who: 'you', chip: 'search', text: SEARCH });
      setPhase('searching');
      void send({ type: 'panel:open', url: SEARCH_URL });
    }
    if (what === 'open') void send({ type: 'panel:open', url: SOURCES[i]!.open });
    if (what === 'pick') {
      say({ who: 'you', text: label });
      void toPage({ type: 'pick:start' });
    }
    if (what === 'none') {
      say({ who: 'you', text: label });
      answerFor(i, null);
    }
  }

  useEffect(() => {
    body.current?.scrollTo({ top: body.current.scrollHeight, behavior: 'smooth' });
  }, [turns.length]);

  return (
    <div className="panel">
      <header className="question">
        <span className="live" aria-hidden="true" />
        <h1>{research.question}</h1>
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
          {turns.map((t, k) =>
            t.who === 'lana' ? (
              <div className="turn lana" key={k}>
                <p>{t.text}</p>
                {t.sources && <Sources status={status} current={current} onOpen={(i) => void send({ type: 'panel:open', url: SOURCES[i]!.open })} />}
                {t.replies && !t.used && (
                  <div className="replies">
                    {t.replies.map(([label, key], j) => (
                      <button key={key} className={j === 0 ? 'go' : ''} onClick={() => reply(key, label)}>{label}</button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="turn you" key={k}>
                {t.capture ? <Preview capture={t.capture} /> : <p>{t.text}</p>}
                {t.chip && <span className="turn-icon"><Icon name={t.chip === 'search' ? 'search' : t.chip === 'here' ? 'frame' : t.chip === 'ask' ? 'ask' : 'keep'} size={14} /></span>}
              </div>
            ),
          )}
        </div>
      </main>
    </div>
  );
}

/* the pages worth opening, with where the learner stands on each */
function Sources({ status, current, onOpen }: { status: Status[]; current: number | null; onOpen: (i: number) => void }) {
  return (
    <div className="sources">
      {SOURCES.map((s, i) => (
        <button key={s.open} className={`source ${s.label.verdict} ${status[i]}${current === i ? ' now' : ''}`} onClick={() => onOpen(i)}>
          <span className="verdict" aria-hidden="true">L</span>
          <span className="s-body">
            <span className="s-title">{s.title}</span>
            <span className="s-why">{s.site} · {s.why}</span>
          </span>
          <span className="s-state" aria-hidden="true">{status[i] === 'done' ? <Icon name="check" /> : <Icon name="open" />}</span>
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

function Preview({ capture }: { capture: Capture }) {
  switch (capture.kind) {
    case 'text':
      return <p className="text">{capture.text}</p>;
    case 'code':
      return <pre>{capture.code}</pre>;
    case 'image':
      return <img src={capture.src} alt={capture.alt} />;
    case 'table':
      return (
        <table>
          <tbody>
            {capture.rows.slice(0, 6).map((row, i) => (
              <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>
            ))}
          </tbody>
        </table>
      );
  }
}
