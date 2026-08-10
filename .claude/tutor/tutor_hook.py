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


# ---- v3 phase routing: the hook is the ONLY dispatcher --------------------
# SKILL.md no longer tells the agent which phase file to read. This does, from
# the DB's real phase, every turn. The pointer is injected (phase-guard) and the
# read is enforced (phase-gate) so it cannot be skipped.

SKILL = PROJECT / '.claude' / 'skills' / 'tutor_v3'
STATE = HERE / '.phase_gate.json'      # shared between the two hook processes

# phase (from targets table) -> the one file that governs it
PHASE_FILE = {
    'INTAKE': 'phases/00-intake.md',
    'SCAN':   'phases/01-scan.md',
    'READ':   'phases/03-read.md',
    'UNLOCK': 'phases/02-unlock.md',
    'BUILD':  'phases/circle.md',
}

# Phase sequence for auto-advancement when unlock_gate opens
PHASE_SEQUENCE = ['SCAN', 'READ', 'UNLOCK', 'BUILD']

# tutor_db.py subcommands that DO tutoring — blocked until the phase file is read.
# Read-only / meta commands (brief, status, statusline, tree, target, ...) are not.
GATED_CMDS = {'probe', 'gate', 'attempt', 'promote', 'demote', 'teach-open',
              'teach-close', 'push', 'review', 'misconception', 'transfer'}


def active_target(con):
    try:
        return con.execute(
            "SELECT * FROM targets WHERE phase != 'retired' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        return None                 # v2 db without the targets table: no v3 routing


def next_phase(phase):
    """Return the next phase in the sequence, or current if at end."""
    try:
        idx = PHASE_SEQUENCE.index(phase)
        return PHASE_SEQUENCE[idx + 1]
    except (ValueError, IndexError):
        return phase  # Not in sequence or already at end


def current_phase(con):
    t = active_target(con)
    if t is None:
        return 'INTAKE'             # no anchor yet -> intake is the only legal move

    phase = t['phase'] if t['phase'] in PHASE_FILE else 'INTAKE'

    # If this phase's unlock_gate is open, advance to next phase
    if t['unlock_gate'] == 'open' and phase in PHASE_SEQUENCE:
        phase = next_phase(phase)

    return phase


def load_state():
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def save_state(d):
    try:
        STATE.write_text(json.dumps(d))
    except Exception:
        pass                        # never let a state write break the turn


def guard_enabled(con):
    row = con.execute("SELECT value FROM meta WHERE key='phase_guard'").fetchone()
    return (row is None) or (row['value'] != 'off')   # default ON


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
    """The most-violated rule: showing him the file he is supposed to rebuild.
    Also records when the agent reads the active phase file (opens phase-gate)."""
    _mark_phase_read(data)
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


def cmd_phase_guard(data):
    """UserPromptSubmit: point the agent at the ONE file that governs this turn.
    stdout is injected as context, deterministically, before the agent answers."""
    con = connect()
    if not guard_enabled(con):
        return
    if active_target(con) is None:
        return                      # not in a tutoring engagement: stay silent
    phase = current_phase(con)
    rel = PHASE_FILE[phase]
    expected = str((SKILL / rel).resolve())
    sid = data.get('session_id') or ''

    st = load_state()
    # reset the read-requirement only when the session or the phase changes;
    # within one phase in one session the agent reads the file once.
    if st.get('session_id') != sid or st.get('phase') != phase:
        st = {'session_id': sid, 'phase': phase, 'expected': expected, 'read': False}
        save_state(st)

    gates = open_gates(con)
    gate_note = ''
    if gates:
        g = gates[0]
        gate_note = (f"\nOPEN GATE #{g['id']} ({g['slug']}): he writes {g['target']}, "
                     f"you do not.")
    already = " (already read this phase)" if st.get('read') else ""
    print(
        f"## TUTOR PHASE GUARD (deterministic router)\n"
        f"ACTIVE PHASE = {phase}. The file that governs THIS turn is:\n"
        f"  {SKILL.name}/{rel}\n"
        f"Read it now and follow it{already}. Do not rely on SKILL.md to tell you "
        f"which phase file to use — SKILL.md no longer routes; this hook does.\n"
        f"The PreToolUse gate BLOCKS {sorted(GATED_CMDS)} until you have read that "
        f"file this phase. LAW 0 always applies.{gate_note}")


def cmd_phase_gate(data):
    """PreToolUse(Bash): a gated tutor_db.py command cannot run until the active
    phase file has actually been Read this session. Turns the pointer into a wall."""
    cmd = (data.get('tool_input') or {}).get('command') or ''
    if 'tutor_db.py' not in cmd:
        return                      # not a tutor action: nothing to gate
    # which subcommand? the token after tutor_db.py
    try:
        after = cmd.split('tutor_db.py', 1)[1].split()
        sub = next((t for t in after if not t.startswith('-')), '')
    except Exception:
        return
    if sub not in GATED_CMDS:
        return
    con = connect()
    if not guard_enabled(con) or active_target(con) is None:
        return
    st = load_state()
    sid = data.get('session_id') or ''
    # fail OPEN if we have no matching state yet (phase-guard hasn't run) — never
    # block on our own missing bookkeeping. Block only on a positive "not read".
    if st.get('session_id') != sid or not st.get('expected'):
        return
    if st.get('read'):
        return
    phase = st.get('phase', '?')
    block(f"BLOCKED by phase-gate: you are in phase {phase} and have not read the "
          f"file that governs it.\nRead this first, then retry:\n  {st['expected']}\n"
          f"(the phase router points here every turn; reading it is mandatory "
          f"before {sub}.)")


def _mark_phase_read(data):
    """Called from read-guard: if the agent reads the expected phase file, the
    gate opens for this phase+session."""
    path = (data.get('tool_input') or {}).get('file_path')
    if not path:
        return
    st = load_state()
    exp = st.get('expected')
    if exp and same_file(path, exp):
        st['read'] = True
        save_state(st)


COMMANDS = {
    'brief': cmd_brief,
    'read-guard': cmd_read_guard,
    'write-guard': cmd_write_guard,
    'stop-check': cmd_stop_check,
    'phase-guard': cmd_phase_guard,
    'phase-gate': cmd_phase_gate,
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
