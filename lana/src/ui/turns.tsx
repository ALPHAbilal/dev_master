import { useEffect, useState } from 'react';
import type { Capture } from '@/contract/messages';
import type { CheckItem, Home, Plan, Query, SourceStatus, Turn } from './conversation';
import { SOURCES } from './scenario';
import { StatusLine } from './StatusLine';
import { Icon } from './icons';

// How each kind of turn is drawn. Both views use these; the full page draws them wide,
// the side panel compact. A turn's buttons work in the view it belongs to; the other view
// shows one button that takes the learner there.

export interface TurnActions {
  view: Home;
  sources: SourceStatus[];
  current: number | null;
  onReply: (key: string, label: string) => void;
  onSearch: (query: string) => void;
  onOpenSource: (index: number) => void;
}

/** Lana's words: shown whole when they're old, revealed piece by piece when they just arrived. */
function Words({ text, at }: { text: string; at: number }) {
  const pieces = text.split(/(?<=\s)/);
  const fresh = Date.now() - at < 1500;
  const [shown, setShown] = useState(fresh ? 0 : pieces.length);
  useEffect(() => {
    if (shown >= pieces.length) return;
    const timer = setTimeout(() => setShown((n) => Math.min(pieces.length, n + 3)), 33);
    return () => clearTimeout(timer);
  }, [shown, pieces.length]);
  return (
    <p className="words">
      {pieces.slice(0, shown).map((p, i) => (
        <span key={i} className={fresh ? 'fresh' : undefined}>{p}</span>
      ))}
    </p>
  );
}

function PlanCard({ plan, compact }: { plan: Plan; compact: boolean }) {
  return (
    <div className={`plan${compact ? ' compact' : ''}`}>
      <section>
        <h3>To find</h3>
        <ul>{plan.find.map((f) => <li key={f}>{f}</li>)}</ul>
      </section>
      <section>
        <h3>Your course gets</h3>
        <ul>{plan.course.map((c) => <li key={c}>{c}</li>)}</ul>
      </section>
    </div>
  );
}

function Queries({ queries, onSearch, active }: { queries: Query[]; onSearch: (q: string) => void; active: boolean }) {
  const [texts, setTexts] = useState(queries.map((q) => q.text));
  return (
    <div className="queries">
      {queries.map((q, i) => (
        <div className="query" key={q.text}>
          <div className="query-body">
            <span className="width">{q.width}</span>
            <input
              value={texts[i]}
              disabled={!active}
              onChange={(e) => setTexts(texts.map((t, j) => (j === i ? e.target.value : t)))}
              aria-label={`Search ${i + 1}`}
              spellCheck={false}
            />
            <span className="gives">{q.gives}</span>
          </div>
          {active && (
            <button className="search-btn" disabled={!texts[i]!.trim()} onClick={() => onSearch(texts[i]!.trim())}>
              <Icon name="search" size={14} />
              Search
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

function Check({ items }: { items: CheckItem[] }) {
  return (
    <ul className="check">
      {items.map((c) => (
        <li key={c.text} className={c.found ? 'found' : 'gap'}>
          <Icon name={c.found ? 'check' : 'cross'} size={14} />
          {c.text}
        </li>
      ))}
    </ul>
  );
}

/** The pages worth opening, with where the learner stands on each. */
export function Sources({ status, current, onOpen }: { status: SourceStatus[]; current: number | null; onOpen: (i: number) => void }) {
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

export function Preview({ capture }: { capture: Capture }) {
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

const CHIP_ICON = { search: 'search', here: 'frame', ask: 'ask', keep: 'keep' } as const;

export function TurnView({ turn, actions }: { turn: Turn; actions: TurnActions }) {
  const compact = actions.view === 'panel';
  if (turn.who === 'you')
    return (
      <div className="turn you">
        {turn.capture ? <Preview capture={turn.capture} /> : <p>{turn.text}</p>}
        {turn.chip && <span className="turn-icon"><Icon name={CHIP_ICON[turn.chip as keyof typeof CHIP_ICON] ?? 'keep'} size={14} /></span>}
      </div>
    );
  const here = turn.home === actions.view;
  return (
    <div className="turn lana">
      {turn.run && <StatusLine run={turn.run} />}
      {turn.text && <Words text={turn.text} at={turn.at} />}
      {turn.plan && <PlanCard plan={turn.plan} compact={compact} />}
      {turn.check && <Check items={turn.check} />}
      {turn.queries && <Queries queries={turn.queries} onSearch={actions.onSearch} active={here && !turn.used} />}
      {turn.sources && <Sources status={actions.sources} current={actions.current} onOpen={actions.onOpenSource} />}
      {turn.replies && !turn.used && (
        <div className="replies">
          {here ? (
            turn.replies.map(([label, key], j) => (
              <button key={key} className={j === 0 ? 'go' : ''} onClick={() => actions.onReply(key, label)}>{label}</button>
            ))
          ) : (
            <button className="go" onClick={() => actions.onReply(`go:${turn.home}`, '')}>
              <Icon name={turn.home === 'full' ? 'expand' : 'panel'} size={14} />
              {turn.home === 'full' ? 'Answer in the full page' : 'Answer in the side panel'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
