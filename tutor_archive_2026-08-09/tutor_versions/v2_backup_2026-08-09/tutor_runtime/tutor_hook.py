#!/usr/bin/env python3
"""Harness-side enforcement. Rules that must not depend on an agent remembering.

Wired into .claude/settings.json. Reads the hook payload on stdin.

    brief         SessionStart  -> prints the learner's rules and current state
    read-guard    PreToolUse(Read)        -> blocks the spec file of an open gate
    write-guard   PreToolUse(Write|Edit)  -> blocks the agent writing his target
    stop-check    Stop                    -> warns when a session recorded nothing

Exit codes: 0 allow, 2 block (stderr is shown to the agent).

FAIL-OPEN by design: any unexpected error exits 0. A locked database must never
stop the user working. It fails CLOSED only on a positive match against an open
gate, which is the one case where being wrong is expensive.
"""
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / 'tutor.db'
PROJECT = HERE.parent.parent          # .claude/tutor -> .claude -> project root


def payload():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def connect():
    con = sqlite3.connect(f'file:{DB}?mode=ro', uri=True, timeout=2.0)
    con.row_factory = sqlite3.Row
    return con


def open_gates(con):
    return con.execute(
        "SELECT g.*, c.slug FROM gates g JOIN concepts c ON c.id = g.concept_id"
        " WHERE g.closed_at IS NULL").fetchall()


def same_file(a, b):
    """Compare paths that may be relative to the project root or absolute."""
    if not a or not b:
        return False
    pa = Path(a) if Path(a).is_absolute() else PROJECT / a
    pb = Path(b) if Path(b).is_absolute() else PROJECT / b
    try:
        return pa.resolve() == pb.resolve()
    except OSError:
        return str(pa) == str(pb)


def block(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def cmd_brief(_data):
    """SessionStart: stdout is injected as context. No agent has to remember."""
    con = connect()
    learner = con.execute("SELECT * FROM learners WHERE active = 1").fetchone()
    lines = ["## TUTOR STATE (injected, not optional)"]
    if learner:
        lines.append(f"Learner: {learner['name']}")
        lines.append(learner['rules'])
    n = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    if n:
        lines.append(f"\npast_interactions={n}. You are not the first agent here."
                     " Read the state, do not re-derive it.")
    else:
        lines.append("\npast_interactions=0. You ARE the first agent here."
                     " Nothing has been measured yet -- do not pretend otherwise,"
                     " and do not infer what he knows from any code in this repo.")
    states = con.execute(
        "SELECT state, COUNT(*) c FROM concepts WHERE parked = 0"
        " GROUP BY state").fetchall()
    if states:
        lines.append("Position: " + ' '.join(f"{r['state']}={r['c']}" for r in states))
    else:
        lines.append("Position: the bank is EMPTY."
                     " Nothing can be routed until `/tutor concepts <dir>` has run.")
    ph = con.execute("SELECT value FROM meta WHERE key = 'phase'").fetchone()
    lines.append(f"Phase: {ph['value'] if ph else 'FLOOR'}"
                 " (FLOOR -> READ -> BUILD_V1 -> BUILD_V2)."
                 " He chooses the phase; you choose every rung inside it.")
    due = con.execute(
        "SELECT COUNT(*) FROM concepts WHERE next_review <= date('now')").fetchone()[0]
    lines.append(f"Due for review: {due}")
    gates = open_gates(con)
    if gates:
        lines.append("\nOPEN GATES — he writes these, you do not:")
        for g in gates:
            lines.append(f"  #{g['id']} {g['kind']} {g['slug']}"
                         f" spec={g['spec_path']} target={g['target']}")
    lines.append("\nAll tutor writes go through .claude/tutor/tutor_db.py."
                 " It refuses what the rules forbid.")
    print('\n'.join(lines))


def cmd_read_guard(data):
    """The most-violated rule: showing him the file he is supposed to rebuild."""
    path = (data.get('tool_input') or {}).get('file_path')
    if not path:
        return
    con = connect()
    for g in open_gates(con):
        if same_file(path, g['spec_path']):
            block(f"BLOCKED by tutor gate #{g['id']} ({g['slug']}).\n"
                  f"{g['spec_path']} is the spec for an open {g['kind']} gate. "
                  f"The file is the spec, not the lesson — do not read it to him "
                  f"and do not read it yourself to paraphrase.\n"
                  f"Give him the contract instead: inputs, outputs, constraints, "
                  f"failure modes. He writes it from a blank page.\n"
                  f"To end the gate: tutor_db.py gate close {g['id']} --result ...")


def cmd_write_guard(data):
    """While a gate is open, the agent writing the code IS the failure."""
    path = (data.get('tool_input') or {}).get('file_path')
    if not path:
        return
    con = connect()
    for g in open_gates(con):
        if same_file(path, g['target']):
            block(f"BLOCKED by tutor gate #{g['id']} ({g['slug']}).\n"
                  f"{g['target']} is his blank page for an open {g['kind']} gate. "
                  f"If you write it, the gate proves nothing.\n"
                  f"Diff what he wrote and name what it cannot survive.\n"
                  f"To end the gate: tutor_db.py gate close {g['id']} --result ...")


def cmd_stop_check(data):
    """A probing session that recorded nothing evaporated when the context did."""
    con = connect()
    row = con.execute("SELECT id FROM sessions ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        return
    n = con.execute("SELECT COUNT(*) FROM probes WHERE session_id = ?",
                    (row['id'],)).fetchone()[0]
    if n == 0:
        print(f"Session {row['id']} recorded zero probes. If you asked him anything, "
              f"it is not in the database and the next agent will re-derive it. "
              f"Write the probes now: tutor_db.py probe <slug> <phase> <faculty> "
              f"<result>.", file=sys.stderr)


COMMANDS = {
    'brief': cmd_brief,
    'read-guard': cmd_read_guard,
    'write-guard': cmd_write_guard,
    'stop-check': cmd_stop_check,
}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd not in COMMANDS:
        sys.exit(0)
    data = payload()
    try:
        COMMANDS[cmd](data)
    except SystemExit:
        raise                       # a deliberate block; let it through
    except Exception:
        sys.exit(0)                 # fail open: never break the session
    sys.exit(0)


if __name__ == '__main__':
    main()
