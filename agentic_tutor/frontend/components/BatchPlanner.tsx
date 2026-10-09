"use client";
import { useEffect, useState } from 'react';
import { batchStorageKey, defaultBatchSettings, parseBatchSettings, type BatchSettings } from '@/lib/scanner';
export default function BatchPlanner({ user, codebase, name, onSettings, demo }: { user: string | null; codebase: string; name: string; onSettings(s: BatchSettings): void; demo: boolean }) {
  const [settings, setSettings] = useState(defaultBatchSettings);
  const [notice, setNotice] = useState('');
  const [status, setStatus] = useState('waiting');
  useEffect(() => {
    let saved = defaultBatchSettings;
    try { if (user) saved = parseBatchSettings(JSON.parse(localStorage.getItem(batchStorageKey(user, codebase)) || 'null')); }
    catch { setNotice('Saved settings could not be loaded.'); }
    setSettings(saved); onSettings(saved);
  }, [user, codebase, onSettings]);
  function update(patch: Partial<BatchSettings>) {
    const next = parseBatchSettings({ ...settings, ...patch });
    setSettings(next); onSettings(next);
    try { if (user) { localStorage.setItem(batchStorageKey(user, codebase), JSON.stringify(next)); setNotice('Saved in this browser for this codebase.'); } else setNotice('Sign in to retain settings for your profile.'); }
    catch { setNotice('Browser storage is unavailable; settings apply to this visit.'); }
  }
  return <div className="scanner-planner">
    <details open><summary>Learning in batches</summary><p>Start with 1–3 stations. Prepare more as you approach the end.</p>
      <div className="batch-fields"><label>Initial stations<select value={settings.initial} onChange={e => update({ initial: Number(e.target.value) })}>{[1,2,3].map(n => <option key={n}>{n}</option>)}</select></label>
      <label>Next batch size<input type="number" min={1} max={50} value={settings.next} onChange={e => update({ next: Number(e.target.value) })} /></label>
      <label>Unfinished stations left<input type="number" min={0} max={50} value={settings.remaining} onChange={e => update({ remaining: Number(e.target.value) })} /></label></div>
      <label className="batch-toggle"><input type="checkbox" checked={settings.automatic} onChange={e => update({ automatic: e.target.checked })} />Prepare the next batch automatically</label>
      <p>{settings.automatic ? `Prepare ${settings.next} more when ${settings.remaining} or fewer unfinished stations remain.` : 'Automatic preparation is off.'}</p>
      <small>Preferences only · background preparation is not connected yet.</small><p role="status">{notice}</p>
    </details>
    <details><summary>Learning profile · {name}</summary><p>This profile belongs to your learning in this codebase only.</p><div className="profile-empty"><strong>No assessment evidence yet</strong><p>Strengths, gaps, and learning patterns will appear as teaching and grading accumulate evidence. No behavior has been inferred.</p></div></details>
    <details><summary>Next batch · {demo ? 'preview' : 'not connected'}</summary>{demo ? <><label>Preview preparation state<select value={status} onChange={e => setStatus(e.target.value)}>{['waiting','generating','ready','failed'].map(s => <option key={s}>{s}</option>)}</select></label><p role="status">{({ waiting: 'Waiting for the remaining-station trigger.', generating: `Preparing ${settings.next} stations…`, ready: `${settings.next} next stations ready to join your path.`, failed: 'Preparation failed. Your existing stations and progress are preserved.' } as Record<string,string>)[status]}</p><small>Sample status only. No background job is running.</small></> : <p>Preparation status will appear here when background generation is connected.</p>}</details>
  </div>;
}
