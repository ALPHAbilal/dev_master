import { useEffect, useState } from 'react';
import type { Capture } from '@/contract/messages';
import type { Home, Piece, Turn } from './conversation';
import { StatusLine } from './StatusLine';
import { Icon } from './icons';

// How each kind of turn is drawn. Both views use these; the full page draws them wide,
// the side panel compact. A turn's buttons work in the view it belongs to; the other view
// shows one button that takes the learner there.

export interface TurnActions {
  view: Home;
  pieces: Piece[];
  /** Pieces marked on the page the learner is on (side panel only). */
  here?: string[];
  onReply: (key: string, label: string) => void;
  onShow: (pieceId: string) => void;
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

/** The session's pieces, and how each relates to the ones before it. */
function PieceMap({ pieces }: { pieces: Piece[] }) {
  return (
    <ol className="piece-map">
      {pieces.map((p) => (
        <li key={p.id}>
          <span className="num">{p.number}</span>
          <span className="piece-body">
            <span className="piece-name">{p.name}</span>
            <span className="piece-what">{p.what}</span>
            {p.relates && <span className="relates">↳ {p.relates}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}

function Diagram({ from, via, to }: { from: string; via: string; to: string }) {
  return (
    <div className="diagram" role="img" aria-label={`${from}, through a ${via}, to an ${to}`}>
      <span className="node">{from}<small>amzn-s3-demo-bucket</small></span>
      <span className="edge">{via}<small>test2.txt</small></span>
      <span className="node">{to}<small>file + metadata</small></span>
    </div>
  );
}

/** A piece answered: what the chat shows of it, where it came from, and the way to its place on the page. */
function AnswerCard({ piece, onShow, marked }: { piece: Piece; onShow: () => void; marked?: boolean }) {
  const a = piece.answer!;
  return (
    <article className="answer">
      <header>
        <span className="num">{piece.number}</span>
        <span className="piece-name">{piece.name}</span>
        <span className="piece-what">{piece.what}</span>
      </header>
      <blockquote>{a.quote}</blockquote>
      {a.diagram && <Diagram {...a.diagram} />}
      {a.code && <pre className="code">{a.code}</pre>}
      <footer>
        <img src={`https://www.google.com/s2/favicons?sz=32&domain=${a.source.site}`} alt="" />
        <span className="source">{a.source.site} · {a.source.title}</span>
        <button className={`show${marked ? ' here' : ''}`} onClick={onShow}>
          <Icon name={marked ? 'frame' : 'open'} size={14} />
          {marked ? 'Show me' : 'Show on the page'}
        </button>
      </footer>
    </article>
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

const CHIP_ICON = { here: 'frame', ask: 'ask', keep: 'keep' } as const;

export function TurnView({ turn, actions }: { turn: Turn; actions: TurnActions }) {
  if (turn.who === 'you')
    return (
      <div className="turn you">
        {turn.capture ? <Preview capture={turn.capture} /> : <p>{turn.text}</p>}
        {turn.chip && <span className="turn-icon"><Icon name={CHIP_ICON[turn.chip as keyof typeof CHIP_ICON] ?? 'keep'} size={14} /></span>}
      </div>
    );
  const own = turn.home === actions.view;
  const answered = (turn.answers ?? []).map((id) => actions.pieces.find((p) => p.id === id)).filter((p): p is Piece => !!p?.answer);
  return (
    <div className="turn lana">
      {turn.run && <StatusLine run={turn.run} />}
      {turn.text && <Words text={turn.text} at={turn.at} />}
      {turn.map && <PieceMap pieces={actions.pieces} />}
      {answered.length > 0 && (
        <div className="answers">
          {answered.map((p) => (
            <AnswerCard key={p.id} piece={p} marked={actions.here?.includes(p.id)} onShow={() => actions.onShow(p.id)} />
          ))}
        </div>
      )}
      {turn.replies && !turn.used && (
        <div className="replies">
          {own ? (
            turn.replies.map(([label, key], j) => (
              <button key={label} className={j === 0 ? 'go' : ''} onClick={() => actions.onReply(key, label)}>{label}</button>
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
