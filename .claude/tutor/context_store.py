#!/usr/bin/env python3
"""Per-concept TEMPORARY teaching memory.

While a concept is being taught, everything the tutor learns about teaching it
(gaps detected, angles tried, session log) lives in concept_context/<slug>/.
On pass the folder is relocated to passed_context/ and the working copy is
gone — the bucket stays lean no matter how many thousands of concepts exist.
"""
import json
import shutil
from datetime import datetime
from pathlib import Path

FILES = ('gaps', 'angles', 'log')


def now():
    return datetime.now().isoformat(timespec='seconds')


def ctx_dir(base: Path, slug: str) -> Path:
    return Path(base) / 'concept_context' / slug


def has_context(base, slug) -> bool:
    return ctx_dir(base, slug).is_dir()


def _read(base, slug, name):
    p = ctx_dir(base, slug) / f'{name}.json'
    if p.exists():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return []
    return []


def _write(base, slug, name, data):
    d = ctx_dir(base, slug)
    d.mkdir(parents=True, exist_ok=True)
    (d / f'{name}.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def init_context(base, slug):
    for name in FILES:
        if not (ctx_dir(base, slug) / f'{name}.json').exists():
            _write(base, slug, name, [])


def read_context(base, slug) -> dict:
    return {name: _read(base, slug, name) for name in FILES}


def open_gap(base, slug, gap, evidence):
    gaps = _read(base, slug, 'gaps')
    for row in gaps:
        if row['gap'] == gap and row['status'] == 'open':
            row['evidence'] += f' | {evidence}'
            _write(base, slug, 'gaps', gaps)
            return
    gaps.append({'gap': gap, 'evidence': evidence, 'status': 'open',
                 'opened_at': now(), 'closed_at': None})
    _write(base, slug, 'gaps', gaps)


def close_gap(base, slug, gap, evidence) -> bool:
    gaps = _read(base, slug, 'gaps')
    for row in gaps:
        if row['gap'] == gap and row['status'] == 'open':
            row.update(status='closed', closed_at=now())
            row['evidence'] += f' | CLOSED: {evidence}'
            _write(base, slug, 'gaps', gaps)
            return True
    return False


def log_angle(base, slug, angle, result):
    angles = _read(base, slug, 'angles')
    angles.append({'angle': angle, 'result': result, 'ts': now()})
    _write(base, slug, 'angles', angles)


def append_log(base, slug, event, detail):
    log = _read(base, slug, 'log')
    log.append({'ts': now(), 'event': event, 'detail': detail})
    _write(base, slug, 'log', log)


def open_gaps(ctx: dict) -> list:
    return [r['gap'] for r in ctx.get('gaps', []) if r['status'] == 'open']


def angle_results(ctx: dict) -> dict:
    out = {}
    for row in ctx.get('angles', []):     # later rows overwrite: latest wins
        out[row['angle']] = row['result']
    return out


def pass_concept(base, slug) -> Path:
    ctx = read_context(base, slug)
    still_open = open_gaps(ctx)
    if still_open:
        raise RuntimeError(
            f"REFUSED: gaps still open on '{slug}': {', '.join(still_open)}. "
            f"Close each with `assess {slug} --close-gap <gap>` backed by a probe.")
    src = ctx_dir(base, slug)
    dest_root = Path(base) / 'passed_context'
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / f"{slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.move(str(src), str(dest))
    return dest
