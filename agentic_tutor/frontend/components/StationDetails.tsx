"use client";
import { useState } from 'react';
import type { StationContract } from '@/lib/scanner';
export default function StationDetails({ contract, files }: { contract: StationContract; files: Record<string, string> }) {
  const [selected, setSelected] = useState(0);
  const h = contract.highlights[selected];
  const source = h && (files[h.file]?.split('\n').slice(h.lo - 1, h.hi).join('\n') ?? h.excerpt);
  return <div className="station-contract">
    <p className="station-question">{contract.question}</p>
    <div className="sec-l">Learning target</div><p>{contract.target}</p>
    <div className="sec-l">Needed first</div><p>{contract.prerequisites.join(' · ') || 'No prerequisites specified.'}</p>
    <div className="sec-l">Scope</div><p>{contract.scope}</p>
    <div className="sec-l">Code highlights · {contract.highlights.length}</div>
    <div className="highlight-tabs" aria-label="Source highlights">{contract.highlights.map((item, i) => <button type="button" key={`${item.file}:${item.lo}:${i}`} aria-pressed={i === selected} onClick={() => setSelected(i)}>{i + 1}. {item.label}</button>)}</div>
    {h && <section aria-live="polite"><p className="detail-sub">{h.file} · L{h.lo}–{h.hi}</p><p>{h.annotation}</p>{source !== undefined ? <div className="code">{source.split('\n').map((line, i) => <div className="cl" key={i}><span className="ln">{h.lo + i}</span><span className="src">{line || ' '}</span></div>)}</div> : <p>Source is not available in this browser.</p>}</section>}
    <div className="sec-l">Understanding across axes</div>
    {contract.axes.map(a => <details className="axis-contract" key={a.axis}><summary>{a.axis}</summary><p>{a.objective}</p><p><strong>Try it</strong><br />{a.probe}</p></details>)}
    <details className="axis-contract"><summary>Assessment review · teacher criteria</summary><p className="detail-sub">Contains expected evidence. Open after attempting the challenges.</p>{contract.axes.map(a => <p key={a.axis}><strong>{a.axis}</strong><br />{a.evidence}</p>)}<div className="sec-l">Misconceptions to watch for</div><ul>{contract.misconceptions.map(m => <li key={m}>{m}</li>)}</ul></details>
  </div>;
}
