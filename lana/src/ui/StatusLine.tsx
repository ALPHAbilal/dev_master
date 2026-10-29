import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { Run, Step } from './conversation';
import { Icon } from './icons';

// The agent at work, on one line: a spark, a label that changes in place, a seconds counter,
// and a fold with the steps behind it. Motion measured on claude.ai's search status (2026-10-29):
// the old label leaves up 3px, the new one arrives from 3px below, the box glides to the new
// width, all in 180ms; a light band sweeps the running label every 3s.

const MORPH = { duration: 180, easing: 'cubic-bezier(0.2,0,0,1)' };

/** A label that changes in place. */
export function Morph({ text, className = '' }: { text: string; className?: string }) {
  const box = useRef<HTMLSpanElement>(null);
  useLayoutEffect(() => {
    const el = box.current!;
    const current = el.lastElementChild as HTMLElement | null;
    if (current && current.textContent === text && current.className === className) return;
    const fromWidth = current ? el.getBoundingClientRect().width : 0;
    const next = document.createElement('span');
    next.className = className;
    next.textContent = text;
    el.append(next);
    if (!current) return;
    void current.animate([{ opacity: 0, transform: 'translateY(-3px)' }], { ...MORPH, fill: 'both' }).finished.then(() => current.remove());
    next.animate([{ opacity: 0, transform: 'translateY(3px)' }, { opacity: 1, transform: 'none' }], MORPH);
    const toWidth = next.getBoundingClientRect().width;
    if (fromWidth && Math.abs(toWidth - fromWidth) > 1) el.animate([{ width: `${fromWidth}px` }, { width: `${toWidth}px` }], MORPH);
  }, [text, className]);
  return <span className="morph" ref={box} />;
}

/** Lana's spark, redrawn 30 times a second while the agent works. */
function Spark({ running }: { running: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!running) return;
    const c = canvas.current!;
    const dpr = devicePixelRatio || 1;
    c.width = c.height = 20 * dpr;
    const ctx = c.getContext('2d')!;
    ctx.scale(dpr, dpr);
    const color = getComputedStyle(c).color;
    let frame = 0;
    const draw = () => {
      ctx.clearRect(0, 0, 20, 20);
      ctx.strokeStyle = color;
      ctx.lineCap = 'round';
      ctx.lineWidth = 1.9;
      for (let i = 0; i < 10; i++) {
        const angle = (i / 10) * Math.PI * 2 + frame * 0.02;
        const length = 5.2 + 2.6 * Math.sin(frame * 0.21 + i * 1.7);
        ctx.beginPath();
        ctx.moveTo(10 + Math.cos(angle) * 1.4, 10 + Math.sin(angle) * 1.4);
        ctx.lineTo(10 + Math.cos(angle) * length, 10 + Math.sin(angle) * length);
        ctx.stroke();
      }
      frame++;
    };
    draw();
    const timer = setInterval(draw, 1000 / 30);
    return () => clearInterval(timer);
  }, [running]);
  return <canvas className={`spark${running ? '' : ' gone'}`} ref={canvas} aria-hidden="true" />;
}

/** Seconds since the run started, shown from 5s on, like the original. */
function Seconds({ since }: { since: number }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const seconds = Math.floor((now - since) / 1000);
  return <span className="seconds">{seconds >= 5 ? `${seconds}s` : ''}</span>;
}

function Toggle({ open, onToggle, label }: { open: boolean; onToggle: () => void; label: string }) {
  return (
    <button className="fold-toggle" aria-expanded={open} aria-label={label} onClick={onToggle}>
      <Icon name="chevron" size={12} />
    </button>
  );
}

function verbOf(step: Step): string {
  if (step.kind === 'search') return step.state === 'busy' ? 'Searching the web' : 'Searched the web';
  if (step.state === 'busy') return 'Reading a page';
  if (step.state === 'error') return 'Couldn’t read the page';
  return `Read ${step.subject ? new URL(step.subject).hostname : 'a page'}`;
}

function StepRow({ step }: { step: Step }) {
  const [open, setOpen] = useState(false);
  const busy = step.state === 'busy';
  const hasResults = !!step.items?.length;
  return (
    <div className="step">
      <div className="step-row">
        <Morph text={step.kind === 'thinking' ? step.text ?? '' : verbOf(step)} className={busy && step.kind !== 'thinking' ? 'verb shimmer' : 'verb'} />
        {step.subject && <span className="subject">{step.subject}</span>}
        {hasResults && <Toggle open={open} onToggle={() => setOpen(!open)} label="Show results" />}
      </div>
      {hasResults && (
        <div className={`fold${open ? ' open' : ''}`}>
          <div>
            <div className="results">
              <header>Results</header>
              <ul>
                {step.items!.map((item) => (
                  <li key={item.url}>
                    <a href={item.url} target="_blank" rel="noopener">
                      <img src={`https://www.google.com/s2/favicons?sz=32&domain=${encodeURIComponent(item.domain)}`} alt="" />
                      <span className="title">{item.title}</span>
                      <span className="domain">{item.domain}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function StatusLine({ run }: { run: Run }) {
  const [open, setOpen] = useState(false);
  const steps = run.steps.filter((s) => s.kind !== 'thinking' || s.text);
  return (
    <div className="status">
      <div className="status-row">
        <Spark running={run.running} />
        <Morph text={run.label} className={run.running ? 'shimmer' : 'label-done'} />
        {run.running && <Seconds since={run.startedAt} />}
        {steps.length > 0 && <Toggle open={open} onToggle={() => setOpen(!open)} label="Show steps" />}
      </div>
      <div className={`fold${open ? ' open' : ''}`}>
        <div>
          <div className="steps">
            {steps.map((s) => (
              <StepRow key={s.id} step={s} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
