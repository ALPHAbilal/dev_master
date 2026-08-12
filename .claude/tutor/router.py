#!/usr/bin/env python3
"""The brief, rendered. Pure: same state in, same text out.

v3's router owned a registry — gap types, angles, form questions, bucket keys —
seeded from Python constants into the DB and then read back out. Two copies of
the same list, and the constants won every time they disagreed. The DB is the
source now; this module only renders.

It renders a DELTA. A brief that reprints the same eleven lines every turn is a
brief nobody reads, and the one turn it changes is the turn nobody notices.
"""
import hashlib
import json

DOCTRINE = {
    'ADVERSARY':
        "ADVERSARY — question first. Pose the question whose answer IS the next "
        "step; explain only the residue he cannot reach. Never hand him the flaw "
        "or the fix. Working code is not evidence.",
    'ALLY':
        "ALLY — he is building. Answer directly, pair with him, unblock fast. "
        "Finishing is the product; a half-built thing teaches nothing. Save the "
        "interrogation for the phase that is for it.",
}

# What the brief is a delta ON. Anything outside this list can change without
# reprinting, because it does not change what you should do next.
SIG_FIELDS = ('phase', 'slug', 'path', 'rungs', 'pending', 'hop_budget',
              'anchor_file', 'anchor_lo', 'anchor_hi', 'anchor_text', 'resume_q')


def signature(state) -> str:
    blob = json.dumps({k: state.get(k) for k in SIG_FIELDS},
                      sort_keys=True, default=str)
    return hashlib.sha1(blob.encode('utf-8')).hexdigest()[:16]


def render(state) -> str:
    """The delta brief. `state['last_sig']` is what was printed last time;
    `state['full']` forces the whole thing regardless."""
    sig = signature(state)
    if not state.get('full') and state.get('last_sig') == sig:
        return "Δ none"
    return '\n'.join(_lines(state))


def _rung_line(rungs):
    from stack import RUNGS
    return '  '.join(f"{r}={rungs.get(r) or '-'}" for r in RUNGS)


def _lines(state):
    L = []
    phase = state.get('phase', 'SCAN')
    mode = state.get('mode', 'ADVERSARY')
    L.append(f"PHASE  {phase}")
    L.append(f"MODE   {DOCTRINE.get(mode, mode)}")

    path = state.get('path') or []
    if not path:
        L.append("STACK  empty — nothing is being taught. Open the anchor frame "
                 "before anything else.")
        return L
    L.append(f"STACK  {' > '.join(path)}   (only the last one is teachable)")

    L.append(f"FRAME  {state.get('slug')}  depth {state.get('depth')}  "
             f"hop budget {state.get('hop_budget')}")
    if state.get('why'):
        L.append(f"WHY    {state['why']}")

    af = state.get('anchor_file')
    if af:
        L.append(f"ANCHOR {af}:{state.get('anchor_lo')}-{state.get('anchor_hi')}"
                 f"   (re-read off disk just now, not remembered)")
        lo = state.get('anchor_lo') or 1
        for i, line in enumerate((state.get('anchor_text') or '').splitlines()):
            L.append(f"  {lo + i:>4} | {line}")
    else:
        L.append("ANCHOR none — a frame with no real code under it is a lecture.")

    L.append(f"RUNGS  {_rung_line(state.get('rungs') or {})}")
    pend = state.get('pending') or []
    if pend:
        L.append(f"PENDING {', '.join(pend)}  — these must clear before it pops")
    if state.get('resume_q'):
        L.append(f"RESUME {state['resume_q']}")
    return L
