#!/usr/bin/env python3
"""The hole STACK. Replaces context_store.py's flat per-concept folders.

A hole found while teaching a hole is not a sibling — it is a child. v3 stored
a flat "chain", so when the tutor descended from `uuid` into `ledger` and from
`ledger` into `pathlib`, nothing remembered the question it had been in the
middle of asking. Both holes were found and both were lost in one session.

Here FOCUS is a stack:

    push    freezes the current top and records the question it interrupted
    top     the ONLY teachable frame; a frozen frame cannot be graded or popped
    pop     refuses unless all four rungs are HIT and nothing is pending, then
            thaws the parent and hands back the question to replay

Every rule below lives in code, not prose, because prose is the layer that was
already there and did not hold.
"""
import json
from datetime import datetime
from pathlib import Path

# The four rungs, in order. A frame is owned when all four are HIT — one rung
# is a demonstration, four is understanding.
RUNGS = ('predict', 'perturb', 'produce', 'transfer')
RESULTS = ('HIT', 'WEAK', 'MISS', 'BLOCKED')


class StackRefusal(Exception):
    """A refusal, with the exact missing items named. Never a bare False."""


def now():
    return datetime.now().isoformat(timespec='seconds')


# ---- reads ---------------------------------------------------------------

def frame(con, frame_id):
    row = con.execute("SELECT * FROM stack_frames WHERE id=?", (frame_id,)).fetchone()
    if row is None:
        raise StackRefusal(f"no stack frame #{frame_id}")
    return row


def top(con, project_id):
    """The deepest live frame. Nothing else may be taught, graded, or popped."""
    return con.execute(
        "SELECT * FROM stack_frames WHERE project_id=? AND state='ACTIVE'"
        " ORDER BY depth DESC, id DESC LIMIT 1", (project_id,)).fetchone()


def live(con, project_id):
    """Every unfinished frame, root first."""
    return con.execute(
        "SELECT * FROM stack_frames WHERE project_id=? AND state!='PASSED'"
        " ORDER BY depth, id", (project_id,)).fetchall()


def path(con, project_id):
    return [r['slug'] for r in live(con, project_id)]


def rungs(con, frame_id):
    return json.loads(frame(con, frame_id)['rungs'] or '{}')


def pending(con, frame_id):
    return json.loads(frame(con, frame_id)['pending'] or '[]')


def missing(con, frame_id):
    """What stands between this frame and a clean pop."""
    got = rungs(con, frame_id)
    return ([r for r in RUNGS if got.get(r) != 'HIT'], pending(con, frame_id))


# ---- writes --------------------------------------------------------------

def push(con, project_id, slug, why=None, anchor=None, resume_q=None):
    """Open a frame under the current top and freeze the parent.

    `anchor` is (file, lo, hi). A child with no anchor of its own inherits the
    parent's FILE — the hole was found in that code and is taught from it.
    `resume_q` is the question the parent was mid-way through asking; it is the
    only thing that makes the descent reversible.
    """
    parent = top(con, project_id)
    afile, alo, ahi = anchor if anchor else (None, None, None)
    if parent is not None:
        if afile is None:
            afile = parent['anchor_file']
        con.execute("UPDATE stack_frames SET state='FROZEN' WHERE id=?",
                    (parent['id'],))
    cur = con.execute(
        "INSERT INTO stack_frames(project_id, slug, depth, parent_id, why,"
        " anchor_file, anchor_lo, anchor_hi, resume_q, opened_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (project_id, slug, 0 if parent is None else parent['depth'] + 1,
         None if parent is None else parent['id'], why, afile, alo, ahi,
         resume_q, now()))
    con.commit()
    return cur.lastrowid


def set_rung(con, frame_id, rung, result):
    """Grade one rung of the top frame.

    WEAK is not a soft HIT. It cuts the hop budget to 1 — a shaky answer earns
    SHORTER questions, not more rope — and a second WEAK on the same rung is a
    MISS, because twice-shaky is not almost-there.
    """
    if rung not in RUNGS:
        raise StackRefusal(f"unknown rung '{rung}'. Valid: {', '.join(RUNGS)}")
    if result not in RESULTS:
        raise StackRefusal(f"unknown result '{result}'. Valid: {', '.join(RESULTS)}")
    got = rungs(con, frame_id)
    prior = got.get(rung)
    if result == 'WEAK':
        got[rung] = 'MISS' if prior == 'WEAK' else 'WEAK'
        con.execute("UPDATE stack_frames SET rungs=?, hop_budget=1 WHERE id=?",
                    (json.dumps(got), frame_id))
    else:
        got[rung] = result
        con.execute("UPDATE stack_frames SET rungs=? WHERE id=?",
                    (json.dumps(got), frame_id))
    con.commit()
    return got[rung]


def queue_pending(con, frame_id, terms):
    """Park sibling holes found in one answer. Order preserved, no duplicates."""
    q = pending(con, frame_id)
    for t in terms:
        if t and t not in q:
            q.append(t)
    con.execute("UPDATE stack_frames SET pending=? WHERE id=?",
                (json.dumps(q), frame_id))
    con.commit()
    return q


def take_pending(con, frame_id, term):
    q = [t for t in pending(con, frame_id) if t != term]
    con.execute("UPDATE stack_frames SET pending=? WHERE id=?",
                (json.dumps(q), frame_id))
    con.commit()
    return q


def pop(con, frame_id, base='.'):
    """Close the top frame. Returns the parent's question, to be replayed.

    Refuses on anything unfinished and names it. A pop that could be argued for
    is a pop that will be argued for.
    """
    f = frame(con, frame_id)
    if f['state'] == 'PASSED':
        raise StackRefusal(f"frame #{frame_id} ({f['slug']}) is already PASSED.")
    if f['state'] != 'ACTIVE':
        raise StackRefusal(
            f"frame #{frame_id} ({f['slug']}) is {f['state']}, not the top of the "
            f"stack. Pop the frames above it first: "
            f"{', '.join(path(con, f['project_id']))}")
    unhit, waiting = missing(con, frame_id)
    if unhit or waiting:
        parts = []
        if unhit:
            got = rungs(con, frame_id)
            parts.append("rungs not HIT: " +
                         ', '.join(f"{r}={got.get(r) or 'ungraded'}" for r in unhit))
        if waiting:
            parts.append("pending holes: " + ', '.join(waiting))
        raise StackRefusal(
            f"cannot pop '{f['slug']}' — " + '; '.join(parts) + ".")

    con.execute("UPDATE stack_frames SET state='PASSED', closed_at=? WHERE id=?",
                (now(), frame_id))
    if f['parent_id'] is not None:
        con.execute("UPDATE stack_frames SET state='ACTIVE' WHERE id=?",
                    (f['parent_id'],))
    con.commit()
    _archive(base, con, frame_id)
    return f['resume_q']


def _archive(base, con, frame_id):
    """The frame outlives the stack: one JSON file, never read back by the tutor."""
    f = frame(con, frame_id)
    dest = Path(base) / 'passed_context'
    dest.mkdir(parents=True, exist_ok=True)
    blob = {k: f[k] for k in f.keys()}
    blob['rungs'] = json.loads(blob['rungs'] or '{}')
    blob['pending'] = json.loads(blob['pending'] or '[]')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    (dest / f"{f['slug']}_{stamp}.json").write_text(
        json.dumps(blob, ensure_ascii=False, indent=2), encoding='utf-8')
