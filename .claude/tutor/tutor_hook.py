#!/usr/bin/env python3
"""Harness-side enforcement. Rules that must not depend on an agent remembering.

Wired into .claude/settings.json. Reads the hook payload on stdin.

    brief         SessionStart  -> prints the learner's rules and current state
    read-guard    PreToolUse(Read)        -> blocks the spec file of an open gate
    write-guard   PreToolUse(Write|Edit)  -> blocks the agent writing his target
    stop-check    Stop                    -> warns when a session recorded nothing
    phase-guard   UserPromptSubmit        -> points at the one governing file
    phase-gate    PreToolUse(Bash)        -> blocks tutoring until it is read
    ship-check    PreToolUse(Bash)        -> blocks an outgoing question that
                                             uses unknown terms or too many hops

Exit codes: 0 allow, 2 block (stderr is shown to the agent).

FAIL-OPEN by design: any unexpected error exits 0. A locked database must never
stop the user working. It fails CLOSED only on a positive match against an open
gate, which is the one case where being wrong is expensive.
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import tutor_db                  # noqa: E402  the single source for DB + rules
import stack                     # noqa: E402
import router                    # noqa: E402

PROJECT = HERE.parent.parent          # .claude/tutor -> .claude -> project root
PROJECTS_DIR = HERE / 'projects'

# The hook owns no rules of its own. `detect_project_id` and the ship-check both
# live in tutor_db; v3 kept a second copy of detect_project_id here and the two
# disagreed the moment the repo was cloned under a different directory name.
detect_project_id = tutor_db.detect_project_id


def payload():
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def connect():
    con = sqlite3.connect(f'file:{tutor_db._db_path()}?mode=ro', uri=True,
                          timeout=2.0)
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


def _state_path():
    return Path(os.environ.get('TUTOR_PHASE_STATE', HERE / '.phase_gate.json'))

# phase -> the one file that governs it. ONE variable, `meta.phase`, decides
# this. v3 kept a second copy on targets.phase and a third in .phase_gate.json,
# so "which phase am I in" had three answers and they disagreed.
PHASE_FILE = {'SCAN': 'phases/01-scan.md',    'READ': 'phases/02-read.md',
              'DRILL': 'phases/03-drill.md',  'ASSEMBLE': 'phases/04-assemble.md',
              'BUILD': 'phases/05-build.md',  'SOLO': 'phases/06-solo.md'}

# The doctrine that governs the phase. ADVERSARY: question first, never hand the
# answer. ALLY: he is building — answer directly, pair, unblock fast.
MODE = {'SCAN': 'ADVERSARY', 'READ': 'ADVERSARY', 'DRILL': 'ADVERSARY',
        'ASSEMBLE': 'ADVERSARY', 'BUILD': 'ALLY', 'SOLO': 'ADVERSARY'}

# tutor_db.py subcommands that DO tutoring — blocked until the phase file is read.
# Read-only / meta commands (brief, status, statusline, tree, target, ...) are not.
# `classify` and `draft` are the whole v4 verdict path and were ungated in v3's
# equivalents, which is why the phase file went unread for an entire session.
GATED_CMDS = {'classify', 'draft', 'pass', 'promote', 'demote', 'attempt',
              'gate', 'review'}


def active_target(con):
    """Is this a live tutoring engagement at all? (No longer a phase source.)"""
    try:
        return con.execute(
            "SELECT * FROM targets WHERE phase != 'retired' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        return None                 # v2 db without the targets table: no routing


def current_phase(con):
    row = con.execute("SELECT value FROM meta WHERE key='phase'").fetchone()
    p = row[0] if row else 'SCAN'
    return p if p in PHASE_FILE else 'SCAN'


def load_state():
    try:
        return json.loads(_state_path().read_text())
    except Exception:
        return {}


def save_state(d):
    try:
        _state_path().write_text(json.dumps(d))
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
    phase = current_phase(con)
    lines.append(f"Phase: {phase} ({' -> '.join(PHASE_FILE)}) — mode "
                 f"{MODE[phase]}. He chooses the phase; you choose every rung "
                 f"inside it.")
    path = stack.path(con, detect_project_id())
    lines.append("Stack: " + (' > '.join(path) if path else
                              "empty — nothing is being taught."))
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

    Ten lines, hard. v3's pointer grew a bucket status block, an auto-archive
    side effect and a gate note, ran to twenty-odd lines every single turn, and
    became something to scroll past.
    """
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
    # within one phase in one session the agent reads the file once. The phase
    # is not stored — `expected` already encodes it, and one copy cannot drift.
    if st.get('session_id') != sid or st.get('expected') != expected:
        st = {'session_id': sid, 'expected': expected, 'read': False}
        save_state(st)

    path = stack.path(con, detect_project_id())
    already = "  (already read this phase)" if st.get('read') else ""
    print(
        f"## TUTOR — PHASE {phase} / MODE {MODE[phase]}\n"
        f"GOVERNING FILE: {expected}{already}\n"
        f"{router.DOCTRINE[MODE[phase]]}\n"
        f"STACK: {' > '.join(path) if path else 'empty — open the anchor frame'}"
        f"{'   (only the last one is teachable)' if len(path) > 1 else ''}\n"
        f"`classify` and `draft` are BLOCKED until that file is read. "
        f"Every outgoing question goes through `draft` first.")


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
    phase = current_phase(con)
    block(f"BLOCKED by phase-gate: you are in phase {phase} and have not read the "
          f"file that governs it.\nRead this first, then retry:\n  {st['expected']}\n"
          f"(the phase router points here every turn; reading it is mandatory "
          f"before {sub}.)")


def cmd_ship_check(data):
    """PreToolUse(Bash): a `draft` that would fail the gate never runs.

    The command refuses it too — this is the same check, one call earlier, so
    the agent gets the reason instead of a non-zero exit it has to interpret.
    """
    cmd = (data.get('tool_input') or {}).get('command') or ''
    if 'tutor_db.py' not in cmd or ' draft' not in cmd:
        return
    try:
        args = cmd.split('tutor_db.py', 1)[1].split()
        if 'draft' not in args:
            return

        def opt(name, default=None):
            return args[args.index(name) + 1] if name in args else default

        about = opt('--about')
        hops = int(opt('--hops', '1'))
        terms = [t.strip() for t in (opt('--terms', '') or '').split(',')
                 if t.strip()]
    except (ValueError, IndexError):
        return                      # unparseable: let the command refuse it
    if not about:
        return
    con = connect()
    ok, reason = tutor_db.ship_check(con, detect_project_id(), terms, hops, about)
    if not ok:
        block(f"BLOCKED by ship-check — this question does not go out.\n{reason}")


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
    'ship-check': cmd_ship_check,
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
