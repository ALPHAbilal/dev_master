#!/usr/bin/env python3
"""Tutor state helper. All agents touch the DB through here, not raw SQL.

Every rule that matters is enforced here, not in prose. A refusal exits
non-zero and says why. An agent that forgets a rule cannot write past it.

    init                         create/upgrade the schema
    session <agent> <note>       open a session, print past_interactions
    brief                        what any agent needs on arrival (SessionStart hook)
    status                       counts by state, unswept, due, last floors

    sweep-next [n]               never-swept concepts, shallowest first
    probe <slug> <phase> <faculty> <result> [-q] [-a] [--seconds] [--below]
    floor <slug> --explains a,b,c --descents N

    teach-open <slug>            refused with no prior attempt on that concept
    teach-close <slug> --explanation-file F   refused without a gate
    gate open <slug> --kind K [--spec P] [--target T]
    gate close <id> --result PASS|FAIL|ABANDONED
    gate list

    promote <slug> <state> [--evidence E]     APPLIED needs unaided production
    demote <slug> [--reason R]
    revise --trigger T --evidence E --change C

    profile [--json]             per-faculty aggregates: the radar's data
    velocity                     probes-per-APPLIED, median seconds, per-week
    gaps                         never swept vs never in the bank
    map                          position / frontier / blocking / gaps / next

    spine-load <csv>             load canonical concepts (source='spine')
    learner add <name> <rules-file> | learner use <name> | learner show
"""
import argparse
import csv
import json
import sqlite3
import statistics
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / 'tutor.db'
SCHEMA = HERE / 'schema.sql'

STATES = ('UNKNOWN', 'SEEN', 'EXPLAINED', 'APPLIED')
EVIDENCE = ('none', 'assisted', 'unaided', 'transferred')
FACULTIES = ('write', 'read', 'debug', 'recall', 'design', 'vocabulary')
PHASES = ('SWEEP', 'DESCEND', 'DRILL', 'REBUILD', 'BUILD', 'TEACH', 'BREAK', 'TRANSFER')
RESULTS = ('HIT', 'MISS', 'PARTIAL')
PRODUCTION_PHASES = ('REBUILD', 'BUILD')
TRIGGERS = ('LADDER', 'BLIND_SPOT', 'TOO_WIDE', 'ALREADY_HAD', 'LEVERAGE')

# Review intervals in days. Stronger evidence buys a longer silence.
REVIEW = {'SEEN': 3, 'EXPLAINED': 7, 'APPLIED': 30}
REVIEW_TRANSFERRED = 90


def die(msg):
    """A refusal. Non-zero exit, reason on stderr, nothing written."""
    print(f"REFUSED: {msg}", file=sys.stderr)
    sys.exit(1)


def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def now():
    return datetime.now().isoformat(timespec='seconds')


def concept(con, slug):
    row = con.execute("SELECT * FROM concepts WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        die(f"no concept '{slug}'. It must be in the bank before it can be graded.")
    return row


def current_session(con):
    row = con.execute("SELECT id FROM sessions ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        die("no session. Run `session <agent> <note>` first.")
    return row['id']


# ---- arrival -------------------------------------------------------------

def init():
    con = connect()
    con.executescript(SCHEMA.read_text(encoding='utf-8'))
    con.commit()
    print(f"initialised {DB}")


def session(agent='unknown', note=''):
    """Open a session and report how many came before. Call ONCE per conversation."""
    con = connect()
    cur = con.execute(
        "INSERT INTO sessions (started_at, agent, dir, note) VALUES (?,?,?,?)",
        (now(), agent, str(Path.cwd()), note))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    print(f"session_id={cur.lastrowid} past_interactions={n - 1}")


def _position(con):
    rows = con.execute(
        "SELECT state, COUNT(*) c FROM concepts GROUP BY state").fetchall()
    total = sum(r['c'] for r in rows)
    parts = ' '.join(f"{r['state']}={r['c']}" for r in rows)
    print(f"POSITION {total} concepts: {parts}")


def brief():
    """Injected at SessionStart, so no agent has to remember to ask."""
    con = connect()
    learner_row = con.execute("SELECT * FROM learners WHERE active = 1").fetchone()
    if learner_row:
        print(f"LEARNER {learner_row['name']}")
        print(learner_row['rules'])
        print()
    n = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    print(f"past_interactions={n}  (you are not the first agent here;"
          f" read the state, do not re-derive it)")
    _position(con)
    due = con.execute(
        "SELECT slug FROM concepts WHERE next_review <= date('now')"
        " ORDER BY next_review").fetchall()
    print(f"DUE {len(due)}: {', '.join(r['slug'] for r in due[:8]) or '-'}")
    open_gates = con.execute(
        "SELECT g.id, g.kind, g.spec_path, g.target, c.slug FROM gates g"
        " JOIN concepts c ON c.id = g.concept_id WHERE g.closed_at IS NULL").fetchall()
    if open_gates:
        print("OPEN GATES (he writes these; you do not):")
        for g in open_gates:
            print(f"  #{g['id']} {g['kind']} {g['slug']}"
                  f" spec={g['spec_path']} target={g['target']}")
    else:
        print("OPEN GATES: none")


def status():
    con = connect()
    n = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    print(f"sessions: {n}")
    _position(con)
    unswept = con.execute(
        "SELECT COUNT(*) FROM concepts WHERE swept_in IS NULL").fetchone()[0]
    print(f"never swept: {unswept}")
    due = con.execute(
        "SELECT COUNT(*) FROM concepts WHERE next_review <= date('now')").fetchone()[0]
    print(f"due for review: {due}")
    for f in con.execute(
            "SELECT c.slug, f.descents, f.found_at FROM floors f "
            "JOIN concepts c ON c.id = f.concept_id ORDER BY f.id DESC LIMIT 3"):
        print(f"floor: {f['slug']} ({f['descents']} descents, {f['found_at'][:10]})")


def sweep_next(n=12):
    """Sweep order: never-swept first, shallow before deep, so coverage stays broad."""
    con = connect()
    for r in con.execute(
            "SELECT slug, name, depth, source, file, line FROM concepts "
            "WHERE swept_in IS NULL ORDER BY depth, id LIMIT ?", (int(n),)):
        where = f"{r['file']}:{r['line']}" if r['file'] else f"({r['source']})"
        print(f"[{r['depth']}] {r['slug']:<28} {r['name']:<34} {where}")


# ---- probing -------------------------------------------------------------

def probe(args):
    """The only way a question gets recorded. Stamps the faculty and the clock."""
    if args.faculty not in FACULTIES:
        die(f"faculty must be one of {FACULTIES}, got '{args.faculty}'")
    if args.phase not in PHASES:
        die(f"phase must be one of {PHASES}, got '{args.phase}'")
    if args.result not in RESULTS:
        die(f"result must be one of {RESULTS}, got '{args.result}'")

    con = connect()
    c = concept(con, args.slug)
    sid = current_session(con)
    con.execute(
        "INSERT INTO probes (session_id, concept_id, phase, faculty, depth_below,"
        " question, answer, result, seconds, asked_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (sid, c['id'], args.phase, args.faculty, args.below,
         args.question, args.answer, args.result, args.seconds, now()))
    con.execute(
        "UPDATE concepts SET attempts = attempts + 1, fails = fails + ?,"
        " updated_at = ? WHERE id = ?",
        (1 if args.result == 'MISS' else 0, now(), c['id']))
    if args.phase == 'SWEEP' and c['swept_in'] is None:
        con.execute("UPDATE concepts SET swept_in = ? WHERE id = ?", (sid, c['id']))
    con.commit()
    print(f"probe recorded: {args.slug} {args.phase}/{args.faculty} -> {args.result}")


def floor(args):
    con = connect()
    c = concept(con, args.slug)
    con.execute(
        "INSERT INTO floors (session_id, concept_id, explains, descents, found_at)"
        " VALUES (?,?,?,?,?)",
        (current_session(con), c['id'], args.explains, args.descents, now()))
    con.commit()
    print(f"floor: {args.slug} explains [{args.explains}]"
          f" after {args.descents} descents")
    print("Teach up from here, never down.")


# ---- teaching ------------------------------------------------------------

def teach_open(args):
    """Teaching is legal only after an attempt. No attempt, no explanation."""
    con = connect()
    c = concept(con, args.slug)
    attempts = con.execute(
        "SELECT COUNT(*) FROM probes WHERE concept_id = ?", (c['id'],)).fetchone()[0]
    if attempts == 0:
        die(f"'{args.slug}' has never been probed. Explaining before an attempt is "
            f"the failure that killed every previous attempt. Probe it first.")
    if c['explanation']:
        print(f"ALREADY TAUGHT (session {c['taught_in']}). Reuse this text, do not "
              f"reword it — two agents teaching it two ways is the drift:\n")
        print(c['explanation'])
        return
    is_floor = con.execute(
        "SELECT COUNT(*) FROM floors WHERE concept_id = ?", (c['id'],)).fetchone()[0]
    if not is_floor:
        print(f"WARNING: '{args.slug}' is not a recorded floor. Teaching above the "
              f"floor patches a symptom. Descend first unless you know why not.")
    print(f"teach-open {args.slug}: {attempts} prior attempts, {c['fails']} fails.")
    print("Name the thing he already does but cannot say. Vocabulary first.")
    print("You must `gate open` before teach-close will succeed.")


def teach_close(args):
    con = connect()
    c = concept(con, args.slug)
    text = Path(args.explanation_file).read_text(encoding='utf-8').strip()
    if not text:
        die("empty explanation. teach-close writes the canonical text or nothing.")
    gate = con.execute(
        "SELECT id FROM gates WHERE concept_id = ? ORDER BY id DESC LIMIT 1",
        (c['id'],)).fetchone()
    if gate is None:
        die(f"no gate for '{args.slug}'. Teaching that does not end in blank-page "
            f"production is a lecture. Run `gate open` first.")
    con.execute(
        "UPDATE concepts SET explanation = ?, taught_in = ?, updated_at = ?"
        " WHERE id = ?", (text, current_session(con), now(), c['id']))
    con.commit()
    print(f"taught: {args.slug} (cached; every later agent reuses this text)")
    print(f"gate #{gate['id']} decides whether it counts.")


# ---- gates ---------------------------------------------------------------

def gate_open(args):
    con = connect()
    c = concept(con, args.slug)
    if args.kind not in ('rebuild', 'build', 'transfer'):
        die("kind must be rebuild|build|transfer")
    cur = con.execute(
        "INSERT INTO gates (session_id, concept_id, kind, spec_path, target, opened_at)"
        " VALUES (?,?,?,?,?,?)",
        (current_session(con), c['id'], args.kind, args.spec, args.target, now()))
    con.commit()
    print(f"gate #{cur.lastrowid} open: {args.slug} ({args.kind})")
    if args.spec:
        print(f"  Read of {args.spec} is now blocked by hook.")
    if args.target:
        print(f"  Agent writes to {args.target} are now blocked by hook.")


def gate_close(args):
    if args.result not in ('PASS', 'FAIL', 'ABANDONED'):
        die("result must be PASS|FAIL|ABANDONED")
    con = connect()
    row = con.execute("SELECT * FROM gates WHERE id = ?", (args.id,)).fetchone()
    if row is None:
        die(f"no gate #{args.id}")
    if row['closed_at']:
        die(f"gate #{args.id} already closed ({row['result']})")
    con.execute("UPDATE gates SET closed_at = ?, result = ? WHERE id = ?",
                (now(), args.result, args.id))
    con.commit()
    print(f"gate #{args.id} closed: {args.result}")


def gate_list(args=None):
    con = connect()
    for g in con.execute(
            "SELECT g.*, c.slug FROM gates g JOIN concepts c ON c.id = g.concept_id"
            " ORDER BY g.id DESC LIMIT 20"):
        state = g['result'] or 'OPEN'
        print(f"#{g['id']:<4} {state:<9} {g['kind']:<8} {g['slug']:<26}"
              f" spec={g['spec_path']} target={g['target']}")


# ---- grading -------------------------------------------------------------

def promote(args):
    """APPLIED needs unaided production. transferred needs a second context."""
    if args.state not in STATES:
        die(f"state must be one of {STATES}")
    if args.evidence not in EVIDENCE:
        die(f"evidence must be one of {EVIDENCE}")

    con = connect()
    c = concept(con, args.slug)

    if args.evidence == 'assisted' and args.state == 'APPLIED':
        die("assisted evidence never reaches APPLIED, however well he followed.")

    if args.state == 'APPLIED':
        placeholders = ','.join('?' * len(PRODUCTION_PHASES))
        proof = con.execute(
            "SELECT id FROM probes WHERE concept_id = ? AND result = 'HIT'"
            f" AND phase IN ({placeholders})",
            (c['id'], *PRODUCTION_PHASES)).fetchone()
        if proof is None:
            die(f"'{args.slug}' has no HIT probe from REBUILD or BUILD. APPLIED means "
                f"he produced it from a blank page. Open a gate instead.")

    if args.evidence == 'transferred':
        if c['state'] != 'APPLIED':
            die(f"'{args.slug}' is {c['state']}. Transfer is a second, later, unaided "
                f"use of something already APPLIED.")
        t = con.execute(
            "SELECT id FROM probes WHERE concept_id = ? AND phase = 'TRANSFER'"
            " AND result = 'HIT'", (c['id'],)).fetchone()
        if t is None:
            die(f"'{args.slug}' has no HIT probe from a TRANSFER phase. Re-test it in "
                f"a different context or language first.")

    days = REVIEW_TRANSFERRED if args.evidence == 'transferred' \
        else REVIEW.get(args.state)
    nxt = (date.today() + timedelta(days=days)).isoformat() if days else None
    con.execute(
        "UPDATE concepts SET state = ?, evidence = ?, next_review = ?, updated_at = ?"
        " WHERE id = ?", (args.state, args.evidence, nxt, now(), c['id']))
    con.commit()
    print(f"{args.slug}: {c['state']}/{c['evidence']} ->"
          f" {args.state}/{args.evidence} (review {nxt})")


def demote(args):
    """Demote as readily as promote. One state down, back tomorrow."""
    con = connect()
    c = concept(con, args.slug)
    i = STATES.index(c['state'])
    new = STATES[max(0, i - 1)]
    nxt = (date.today() + timedelta(days=1)).isoformat()
    con.execute(
        "UPDATE concepts SET state = ?, next_review = ?, updated_at = ? WHERE id = ?",
        (new, nxt, now(), c['id']))
    con.commit()
    print(f"{args.slug}: {c['state']} -> {new} (retry {nxt}) {args.reason or ''}")


def revise(args):
    """Only on evidence, never on difficulty."""
    if args.trigger not in TRIGGERS:
        die(f"trigger must be one of {TRIGGERS}. 'it was hard' is not a trigger — "
            f"that is him flinching.")
    if not args.evidence.strip():
        die("revise needs the evidence that triggered it. No evidence, no revision.")
    con = connect()
    con.execute(
        "INSERT INTO ladder_log (ts, trigger, evidence, change) VALUES (?,?,?,?)",
        (now(), args.trigger, args.evidence, args.change))
    con.commit()
    print(f"ladder revised [{args.trigger}]: {args.change}")


# ---- sight ---------------------------------------------------------------

def profile(args):
    """Per-faculty aggregates. This is the radar's data. It is a shape, not a level."""
    con = connect()
    out = {}
    for fac in FACULTIES:
        rows = con.execute(
            "SELECT p.result, p.seconds, c.depth FROM probes p"
            " JOIN concepts c ON c.id = p.concept_id WHERE p.faculty = ?",
            (fac,)).fetchall()
        n = len(rows)
        hits = sum(1 for r in rows if r['result'] == 'HIT')
        secs = [r['seconds'] for r in rows if r['seconds']]
        out[fac] = {
            'attempts': n,
            'hits': hits,
            'hit_rate': round(hits / n, 2) if n else None,
            'median_seconds': round(statistics.median(secs)) if secs else None,
            'max_depth': max((r['depth'] for r in rows if r['result'] == 'HIT'),
                             default=0),
        }
    if args.json:
        print(json.dumps(out, indent=2))
        return
    print(f"{'FACULTY':<12}{'ATT':>5}{'HIT':>5}{'RATE':>7}{'MED s':>7}{'DEPTH':>7}")
    for fac, d in out.items():
        rate = f"{d['hit_rate']:.0%}" if d['hit_rate'] is not None else '-'
        print(f"{fac:<12}{d['attempts']:>5}{d['hits']:>5}{rate:>7}"
              f"{str(d['median_seconds'] or '-'):>7}{d['max_depth']:>7}")
    untested = [f for f, d in out.items() if d['attempts'] == 0]
    if untested:
        print(f"\nNEVER TESTED: {', '.join(untested)}")
        print("These axes are not zero, they are unmeasured. Do not draw them.")


def velocity(args=None):
    """Probes-per-APPLIED and calendar rate. 'Short time', with an instrument."""
    con = connect()
    applied = con.execute(
        "SELECT id, slug FROM concepts WHERE state = 'APPLIED'").fetchall()
    costs = [con.execute("SELECT COUNT(*) FROM probes WHERE concept_id = ?",
                         (c['id'],)).fetchone()[0] for c in applied]
    secs = [r[0] for r in con.execute(
        "SELECT seconds FROM probes WHERE seconds IS NOT NULL")]
    print(f"APPLIED concepts: {len(applied)}")
    if costs:
        print(f"probes per APPLIED: median {statistics.median(costs):.0f},"
              f" max {max(costs)}")
    if secs:
        print(f"median seconds to answer: {statistics.median(secs):.0f}")
    else:
        print("median seconds to answer: unmeasured"
              " (no probe has carried a clock yet)")
    print("APPLIED per week:")
    for w in con.execute(
            "SELECT strftime('%Y-%W', updated_at) w, COUNT(*) n FROM concepts"
            " WHERE state = 'APPLIED' AND updated_at IS NOT NULL"
            " GROUP BY w ORDER BY w"):
        print(f"  {w['w']}: {w['n']:>3} {'#' * w['n']}")


def gaps(args=None):
    """Two different kinds of nothing, told apart."""
    con = connect()
    unswept_code = con.execute(
        "SELECT COUNT(*) FROM concepts WHERE swept_in IS NULL AND source='code'"
    ).fetchone()[0]
    spine_total = con.execute(
        "SELECT COUNT(*) FROM concepts WHERE source='spine'").fetchone()[0]
    unswept_spine = con.execute(
        "SELECT COUNT(*) FROM concepts WHERE swept_in IS NULL AND source='spine'"
    ).fetchone()[0]
    print(f"in his code, never asked:   {unswept_code}")
    print(f"in the spine, never asked:  {unswept_spine}"
          f"   <- territory he has never entered")
    if spine_total == 0:
        print("no spine loaded: unknown-unknowns are still invisible."
              " Run `spine-load`.")
    print("by category, never swept:")
    for r in con.execute(
            "SELECT category, source, COUNT(*) n FROM concepts WHERE swept_in IS NULL"
            " GROUP BY category, source ORDER BY n DESC"):
        print(f"  {r['category']:<10} {r['source']:<6} {r['n']}")


def show_map(args=None):
    """No writes, no teaching."""
    con = connect()
    _position(con)
    frontier = con.execute(
        "SELECT slug FROM concepts WHERE state IN ('SEEN','UNKNOWN')"
        " AND (requires IS NULL OR requires = '') ORDER BY depth LIMIT 6").fetchall()
    print(f"FRONTIER {', '.join(r['slug'] for r in frontier) or '-'}")
    blocking = con.execute(
        "SELECT c.slug, COUNT(o.id) n FROM concepts c"
        " JOIN concepts o ON (',' || o.requires || ',') LIKE ('%,' || c.slug || ',%')"
        " WHERE c.state IN ('UNKNOWN','SEEN') GROUP BY c.slug ORDER BY n DESC LIMIT 5"
    ).fetchall()
    print("BLOCKING " + (', '.join(f"{r['slug']}({r['n']})" for r in blocking) or '-'))
    gaps()
    nxt = con.execute(
        "SELECT slug, name, gate FROM concepts WHERE state IN ('UNKNOWN','SEEN')"
        " ORDER BY depth LIMIT 1").fetchone()
    if nxt:
        print(f"NEXT {nxt['slug']} — {nxt['name']}")
        print(f"  done looks like: {nxt['gate'] or 'no gate set'}")


# ---- the spine -----------------------------------------------------------

def spine_load(args):
    """Canonical concepts, so a hole can exist where he has never been.

    Merges by slug: a concept already derived from his own code keeps its
    file/line and its history, and is never overwritten. Only new rows insert.
    """
    con = connect()
    added = skipped = 0
    with open(args.csv, newline='', encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            slug = row['slug'].strip()
            if not slug:
                continue
            if con.execute("SELECT 1 FROM concepts WHERE slug = ?",
                           (slug,)).fetchone():
                skipped += 1
                continue
            con.execute(
                "INSERT INTO concepts (slug, name, definition, category, depth,"
                " requires, gate, source, state, evidence, updated_at)"
                " VALUES (?,?,?,?,?,?,?,'spine','UNKNOWN','none',?)",
                (slug, row['name'].strip(), row['definition'].strip(),
                 row['category'].strip(), int(row['depth']),
                 row.get('requires', '').strip(), row.get('gate', '').strip(), now()))
            added += 1
    con.commit()
    print(f"spine: {added} added, {skipped} already in the bank from his own code")


# ---- learners ------------------------------------------------------------

def learner(args):
    con = connect()
    if args.action == 'show':
        for r in con.execute("SELECT name, active FROM learners ORDER BY id"):
            print(f"{'*' if r['active'] else ' '} {r['name']}")
        return
    if args.action == 'add':
        rules = Path(args.rules_file).read_text(encoding='utf-8').strip()
        if not rules:
            die("a learner with no rules is a learner no agent knows how to treat.")
        con.execute(
            "INSERT INTO learners (name, rules, active, created_at) VALUES (?,?,0,?)",
            (args.name, rules, now()))
        con.commit()
        print(f"learner added: {args.name} (inactive; `learner use {args.name}`)")
        return
    if args.action == 'use':
        if not con.execute("SELECT 1 FROM learners WHERE name = ?",
                           (args.name,)).fetchone():
            die(f"no learner '{args.name}'")
        con.execute("UPDATE learners SET active = 0")
        con.execute("UPDATE learners SET active = 1 WHERE name = ?", (args.name,))
        con.commit()
        print(f"active learner: {args.name}")


# ---- cli -----------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog='tutor_db.py', description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd')

    sub.add_parser('init')
    s = sub.add_parser('session')
    s.add_argument('agent')
    s.add_argument('note', nargs='?', default='')
    sub.add_parser('brief')
    sub.add_parser('status')
    s = sub.add_parser('sweep-next')
    s.add_argument('n', nargs='?', default=12)

    s = sub.add_parser('probe')
    s.add_argument('slug')
    s.add_argument('phase')
    s.add_argument('faculty')
    s.add_argument('result')
    s.add_argument('--question', '-q', default='')
    s.add_argument('--answer', '-a', default='')
    s.add_argument('--seconds', type=int, default=None)
    s.add_argument('--below', type=int, default=0)

    s = sub.add_parser('floor')
    s.add_argument('slug')
    s.add_argument('--explains', default='')
    s.add_argument('--descents', type=int, default=1)

    s = sub.add_parser('teach-open')
    s.add_argument('slug')
    s = sub.add_parser('teach-close')
    s.add_argument('slug')
    s.add_argument('--explanation-file', required=True)

    g = sub.add_parser('gate').add_subparsers(dest='gate_cmd')
    go = g.add_parser('open')
    go.add_argument('slug')
    go.add_argument('--kind', required=True)
    go.add_argument('--spec', default=None)
    go.add_argument('--target', default=None)
    gc = g.add_parser('close')
    gc.add_argument('id', type=int)
    gc.add_argument('--result', required=True)
    g.add_parser('list')

    s = sub.add_parser('promote')
    s.add_argument('slug')
    s.add_argument('state')
    s.add_argument('--evidence', default='unaided')
    s = sub.add_parser('demote')
    s.add_argument('slug')
    s.add_argument('--reason', default='')

    s = sub.add_parser('revise')
    s.add_argument('--trigger', required=True)
    s.add_argument('--evidence', required=True)
    s.add_argument('--change', required=True)

    s = sub.add_parser('profile')
    s.add_argument('--json', action='store_true')
    sub.add_parser('velocity')
    sub.add_parser('gaps')
    sub.add_parser('map')

    s = sub.add_parser('spine-load')
    s.add_argument('csv')

    s = sub.add_parser('learner')
    s.add_argument('action', choices=('add', 'use', 'show'))
    s.add_argument('name', nargs='?')
    s.add_argument('rules_file', nargs='?')
    return p


DISPATCH = {
    'init': lambda a: init(),
    'session': lambda a: session(a.agent, a.note),
    'brief': lambda a: brief(),
    'status': lambda a: status(),
    'sweep-next': lambda a: sweep_next(a.n),
    'probe': probe,
    'floor': floor,
    'teach-open': teach_open,
    'teach-close': teach_close,
    'gate': lambda a: {'open': gate_open, 'close': gate_close,
                       'list': gate_list}[a.gate_cmd](a),
    'promote': promote,
    'demote': demote,
    'revise': revise,
    'profile': profile,
    'velocity': lambda a: velocity(),
    'gaps': lambda a: gaps(),
    'map': lambda a: show_map(),
    'spine-load': spine_load,
    'learner': learner,
}


def main():
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] or ['status'])
    if args.cmd not in DISPATCH:
        parser.print_help()
        return
    DISPATCH[args.cmd](args)


if __name__ == '__main__':
    main()
