#!/usr/bin/env python3
"""Tutor state helper. All agents touch the DB through here, not raw SQL.

Every rule that matters is enforced here, not in prose. A refusal exits
non-zero and says why. An agent that forgets a rule cannot write past it.

    init                         create/upgrade the schema
    session <agent> <note>       open a session, print past_interactions
    brief                        what any agent needs on arrival (SessionStart hook)
    status                       counts by state, unswept, due, last floors

    sweep-next [n]               never-swept concepts, shallowest first
    ask <slug[,slug...]>         start the clock as the question goes on screen
    probe <slug> <phase> <faculty> <result> [-q] [-a] [--error-class] [--below]
    floor <slug> --explains a,b,c --descents N

    teach-open <slug>            refused with no prior attempt on that concept
    teach-close <slug> --explanation-file F   refused without a gate
    gate open <slug> --kind K [--spec P] [--target T]
    gate close <id> --result PASS|FAIL|ABANDONED
    gate list

    promote <slug> CAN|CANT [--evidence E] --copy-checked   CAN needs production
    demote <slug> [--reason R]
    revise --trigger T --evidence E --change C

    profile [--json]             per-faculty aggregates: the radar's data
    velocity                     probes-per-CAN, median seconds, per-week
    gaps                         never swept vs never in the bank
    map                          position / frontier / blocking / gaps / next

    concepts-load <csv>          load the bank from HIS code (source='code');
                                 depth 3+ inserts parked=1, off the ladder
    spine-load <csv>             load canonical concepts (source='spine')
    learner add <name> <rules-file> | learner use <name> | learner show

  v2 (see tutor_versions/v1_2026-08-05/POSTMORTEM.md for why each exists):
    attempt snap <phase> <slug> --src F   copy + diff what he wrote, BEFORE grading
    attempt log [slug]                    the portfolio: shorter and faster over time
    attempt grade <phase> <slug> <result> attach the verdict to the artifact
    phase [--set P] [--why W]    his only routing choice, four times, ever
    assume --teaching S --assumed a,b,c   declare prerequisites, then invite a veto
    assume --veto <slug>                  he vetoed one: logs BLIND_SPOT, teach it first
    due-slice                    what is stale, to be reviewed INSIDE a real build
"""
import argparse
import csv
import json
import os
import sqlite3
import statistics
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / 'tutor.db'
SCHEMA = HERE / 'schema.sql'
PROJECTS_DIR = HERE / 'projects'


def detect_project_id():
    """Detect current project from git remote or directory name."""
    try:
        import subprocess
        remote_url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        if remote_url:
            name = Path(remote_url).stem
            return name.replace(".git", "")
    except:
        pass
    # Fallback: use directory name
    return Path.cwd().name


def bucket_path(project_id=None):
    """Return path to bucket file for given project."""
    if project_id is None:
        project_id = detect_project_id()
    path = PROJECTS_DIR / project_id / 'tutor_state.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def read_bucket(project_id=None):
    """Read bucket state for project (empty dict if not exists)."""
    path = bucket_path(project_id)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except:
            return {}
    return {}


def write_bucket(data, project_id=None):
    """Write bucket state for project."""
    path = bucket_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def init_bucket():
    """Create new empty bucket structure."""
    return {
        'primary_concept': None,
        'chain': [],  # [{concept, name, blocked_by, status}, ...]
        'resolution_plan': [],  # order to solve
        'status': 'empty',
        'started_at': None
    }

# v2: two states, not four. v1's four-state value is preserved in concepts.state_v1
# and is never written again. "Only APPLIED counts" was already the doctrine;
# SEEN and EXPLAINED triggered no decision in 12 sessions, so they are gone.
STATES = ('CANT', 'CAN')
EVIDENCE = ('none', 'assisted', 'guided', 'unaided', 'transferred')
# v2 faculties stay legal (historical probes keep their meaning). v3 adds the
# nine circle-verbs: `implement` aliases `write`, `understand` folds `read`.
FACULTIES = ('write', 'read', 'debug', 'recall', 'design', 'vocabulary',
             'understand', 'decompose', 'reason', 'implement',
             'evaluate', 'communicate', 'improve')

# v2 phases are the learner's four, plus the diagnostics that feed them.
# The v1 names stay legal so 73 historical probes keep their meaning.
LEARNER_PHASES = ('FLOOR', 'READ', 'BUILD_V1', 'BUILD_V2', 'CAPSTONE')
PHASES = LEARNER_PHASES + ('SWEEP', 'DESCEND', 'DRILL', 'TEACH',
                           'REBUILD', 'BUILD', 'BREAK', 'TRANSFER')
RESULTS = ('HIT', 'MISS', 'PARTIAL')

# Review severities, worst first. The first two BLOCK promotion: a review whose
# findings can be ignored is a review that teaches nothing.
SEVERITIES = ('blocker', 'correctness', 'robustness', 'clarity', 'naming')
BLOCKING = ('blocker', 'correctness')
# FLOOR counts: the wide depth-1 gates ARE blank-page production (he writes the
# loop, not a prediction about one). READ is deliberately absent -- predicting
# what a file does is not producing it.
PRODUCTION_PHASES = ('FLOOR', 'BUILD_V1', 'BUILD_V2', 'CAPSTONE', 'REBUILD', 'BUILD')
# Phases where he edits a real file, so an archived attempt must exist first.
ARTIFACT_PHASES = ('BUILD_V1', 'BUILD_V2', 'CAPSTONE')

# A MISS is not one thing. v1 collapsed all five into MISS and rediscovered the
# difference in prose every session; two typos cost three exchanges.
#   gap     he does not know it            -> teach
#   syntax  knows it, mis-writes the form  -> drill the form, do not re-teach
#   typo    pirnt / wount_words            -> costs nothing, teaches nothing
#   bleed   another language leaking (// ! =) -> unlearn, name the source
#   fatigue dropped a rule seen minutes ago -> stop the session
ERROR_CLASSES = ('gap', 'syntax', 'typo', 'bleed', 'fatigue')
NO_PENALTY = ('typo', 'fatigue')          # never counts as a fail against a concept

TRIGGERS = ('LADDER', 'BLIND_SPOT', 'TOO_WIDE', 'ALREADY_HAD', 'LEVERAGE')

# How `seconds` was obtained. Only `measured` is evidence about recall.
CLOCKS = ('measured', 'batch', 'away', 'unmeasured', 'self-reported')
# Past this, on ONE live question, he is not thinking -- he is elsewhere. His
# real gaps on 2026-08-05 were 44 and 67 minutes. Treating those as think-time
# would say he reconstructs everything, which is false.
AWAY_AFTER = 600

# Review intervals in days. Stronger evidence buys a longer silence.
REVIEW = {'CANT': 1, 'CAN': 30}
REVIEW_TRANSFERRED = 90

def review_interval(state, depth, evidence):
    """Spaced repetition: decay curves by depth + evidence."""
    base = REVIEW.get(state, 1)
    if evidence == 'unaided':
        decay = 1 + (depth * 0.3)  # Deeper = longer intervals
    elif evidence == 'transferred':
        return REVIEW_TRANSFERRED
    else:
        decay = 1  # Default for guided/assisted
    return int(base * decay)


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
        "SELECT state, COUNT(*) c FROM concepts WHERE parked = 0 GROUP BY state").fetchall()
    total = sum(r['c'] for r in rows)
    if not total:
        print("POSITION the bank is EMPTY. Every other verb reads from a bank that "
              "does not exist yet -- run `/tutor concepts <dir>` first.")
        return
    parts = ' '.join(f"{r['state']}={r['c']}" for r in rows)
    print(f"POSITION {total} concepts: {parts}")


def _momentum(con):
    """The escalation signal. Computed from probes, not stored -- the trailing run
    of consecutive HITs across the most recent questions. A streak means he has
    OUTGROWN the current density: stop drilling siblings, widen or jump. Its
    absence is exactly what made 9 sessions feel uniform."""
    rows = con.execute(
        "SELECT result FROM probes ORDER BY asked_at DESC, id DESC LIMIT 12").fetchall()
    streak = 0
    for r in rows:
        if r['result'] == 'HIT':
            streak += 1
        else:
            break
    if streak == 0:
        return
    print(f"MOMENTUM {streak} HIT(s) in a row.")
    if streak >= 3:
        print("  He is clearing rungs first-pass. STOP drilling siblings of an owned"
              " cluster. Either WIDEN the gate (one slice using 5+ owned concepts at"
              " once) or offer the phase jump. Same density on a streak IS the drill trap.")


def _density(con):
    """The 20/60/20 ratio, by LOGGED events for the current session. It cannot see
    prose length, so it is a proxy and says so -- but 'too much talking' becomes a
    number instead of a vibe. explain = teaches + pushes; struggle = probes +
    attempts; review = review findings raised."""
    sid = con.execute("SELECT id FROM sessions ORDER BY id DESC LIMIT 1").fetchone()
    if sid is None:
        return
    sid = sid['id']
    explain = (con.execute("SELECT COUNT(*) FROM concepts WHERE taught_in=?", (sid,)).fetchone()[0]
               + con.execute("SELECT COUNT(*) FROM stalls WHERE session_id=?", (sid,)).fetchone()[0])
    struggle = (con.execute("SELECT COUNT(*) FROM probes WHERE session_id=?", (sid,)).fetchone()[0]
                + con.execute("SELECT COUNT(*) FROM attempts WHERE session_id=?", (sid,)).fetchone()[0])
    review = con.execute("SELECT COUNT(*) FROM reviews WHERE session_id=?", (sid,)).fetchone()[0]
    tot = explain + struggle + review
    if tot == 0:
        return
    pe, ps, pr = (round(100*explain/tot), round(100*struggle/tot), round(100*review/tot))
    print(f"DENSITY this run (logged events, proxy): explain {pe}% / struggle {ps}%"
          f" / review {pr}%  (target ~20/60/20)")
    if struggle and ps < 50:
        print("  struggle share is low -- you are talking more than he is producing."
              " Fewer worked examples, wider gates.")
    elif struggle >= 3 and pe < 10:
        print("  explain share is near zero -- the overcorrection. He is being drilled"
              " with almost no teaching. If a MISS has a real gap, TEACH it (teach-open"
              " logs it); do not just re-gate. 0% explain is not a badge.")


def brief():
    """Injected at SessionStart, so no agent has to remember to ask."""
    con = connect()
    learner_row = con.execute("SELECT * FROM learners WHERE active = 1").fetchone()
    if learner_row:
        print(f"LEARNER {learner_row['name']}")
        print(learner_row['rules'])
        print()
    n = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    if n:
        print(f"past_interactions={n}  (you are not the first agent here;"
              f" read the state, do not re-derive it)")
    else:
        print("past_interactions=0  (you ARE the first agent here. Nothing has been"
              " measured — do not infer what he knows from any code in this repo)")
    ph = con.execute("SELECT value FROM meta WHERE key='phase'").fetchone()
    parked = con.execute("SELECT COUNT(*) FROM concepts WHERE parked=1").fetchone()[0]
    print(f"PHASE {ph['value'] if ph else 'FLOOR'}"
          f"   ({' -> '.join(LEARNER_PHASES)})")
    print("  YOU pick every rung inside a phase. Never ask him 'which concept next?'."
          " He chooses the PHASE only.")
    _position(con)
    if parked:
        print(f"  ({parked} concepts parked at depth 3+ — off the ladder, not lost)")
    _momentum(con)
    _density(con)
    due = con.execute(
        "SELECT slug FROM concepts WHERE next_review <= date('now')"
        " ORDER BY next_review").fetchall()
    print(f"DUE {len(due)}: {', '.join(r['slug'] for r in due[:8]) or '-'}")
    nxt = con.execute(
        "SELECT slug, name, depth FROM concepts WHERE state='CANT' AND parked=0"
        " ORDER BY CASE WHEN next_review <= date('now') THEN 0 ELSE 1 END,"
        " depth LIMIT 1").fetchone()
    if nxt:
        print(f"SUGGEST: [{nxt['depth']}] {nxt['slug']} — {nxt['name']}")
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
    mis = con.execute(
        "SELECT m.slug, m.belief, m.aspect,"
        " (SELECT COUNT(*) FROM misconception_hits h WHERE h.misconception_id = m.id) n"
        " FROM misconceptions m WHERE m.state='OPEN' ORDER BY n DESC").fetchall()
    if mis:
        print("OPEN MISCONCEPTIONS (false beliefs, not rungs — they cross concepts):")
        for m in mis:
            print(f"  {m['slug']} [{m['aspect']}] x{m['n']} — believes: {m['belief']}")
        print("  Watch for these in EVERY answer, not only where they were found."
              " `patterns` for the full picture.")
    rev = con.execute(
        "SELECT id, slug, severity, finding FROM reviews WHERE state='OPEN'"
        " ORDER BY CASE severity WHEN 'blocker' THEN 0 WHEN 'correctness'"
        " THEN 1 ELSE 2 END, id").fetchall()
    if rev:
        print("OPEN REVIEW FINDINGS (he answers these; blocking ones hold the credit):")
        for r in rev[:8]:
            print(f"  #{r['id']} [{r['severity']}] {r['slug']} — {r['finding']}")
    cap = con.execute("SELECT slug, title, state FROM capstones WHERE"
                      " state != 'SHIPPED'").fetchall()
    for c in cap:
        print(f"CAPSTONE {c['state']}: {c['slug']} — {c['title']}")
    hyp = con.execute("SELECT COUNT(DISTINCT hypothesis) FROM stalls"
                      " WHERE hyp_state='OPEN'").fetchone()[0]
    if hyp:
        print(f"OPEN STALL HYPOTHESES: {hyp}. These are guesses about holes,"
              " recorded when he froze — not facts.")
        if hyp >= 3:
            print("  3+ open. Run `push interview` and put them to him as claims"
                  " he can deny, then PROBE every yes.")
    lk = con.execute("SELECT COUNT(*) FROM lookups").fetchone()[0]
    if lk == 0 and n >= 3:
        print("LOOKUPS 0 across every session. Either nothing has ever been"
              " uncertain, or uncertainty is being hidden. Only one of those is"
              " true — search in the open and log it with `lookup`.")


def status():
    con = connect()
    n = con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    print(f"sessions: {n}")
    _position(con)
    unswept = con.execute(
        "SELECT COUNT(*) FROM concepts WHERE swept_in IS NULL AND parked = 0").fetchone()[0]
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
            "WHERE swept_in IS NULL AND parked = 0 ORDER BY depth, id LIMIT ?", (int(n),)):
        where = f"{r['file']}:{r['line']}" if r['file'] else f"({r['source']})"
        print(f"[{r['depth']}] {r['slug']:<28} {r['name']:<34} {where}")


# ---- probing -------------------------------------------------------------

def ask(args):
    """Start the clock. Run this the moment the question goes on his screen.

    THE CLOCK IS A SUBTRACTION, NEVER A QUESTION. v2 made --seconds required and
    supplied nothing, so the agent begged him for it -- "how many minutes did
    test.py take?" -- and on 2026-08-05 he answered "around 30 minitues" for a
    fifteen-question sweep and the agent divided. Fifteen invented numbers that
    look exactly like measurements.

    One slug = one live question, and the probe gets a real elapsed.
    Many slugs = one worksheet, ONE clock. The span belongs to the batch and is
    never divided among its questions.
    """
    slugs = [s.strip() for s in args.slugs.split(',') if s.strip()]
    if not slugs:
        die("ask needs at least one slug")
    con = connect()
    for s in slugs:
        concept(con, s)                       # refuses an unknown slug now, not later
    sid = current_session(con)
    open_row = con.execute(
        "SELECT id, slugs, asked_at FROM asks WHERE session_id = ? AND closed_at IS NULL"
        " ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
    if open_row:
        # Two clocks running means neither is trustworthy. Abandon the old one
        # rather than silently attribute his time to the wrong question.
        con.execute("UPDATE asks SET closed_at = ? WHERE id = ?", (now(), open_row['id']))
        print(f"note: abandoned the clock still running on [{open_row['slugs']}]"
              f" -- it was never probed, so it records nothing.", file=sys.stderr)
    cur = con.execute(
        "INSERT INTO asks (session_id, slugs, phase, faculty, asked_at)"
        " VALUES (?,?,?,?,?)",
        (sid, ','.join(slugs), args.phase, args.faculty, now()))
    con.commit()
    kind = 'batch' if len(slugs) > 1 else 'single'
    print(f"clock #{cur.lastrowid} running ({kind}): {', '.join(slugs)}")
    if len(slugs) > 1:
        print("  one clock for the whole worksheet. The span is a fact about the"
              " batch; it will NOT be divided among the questions.")
    print("  Put the question on his screen NOW. Do nothing else until he answers.")


def _consume_clock(con, sid, slug):
    """(seconds, clock) for this probe, by subtraction. Never asks anybody."""
    row = con.execute(
        "SELECT * FROM asks WHERE session_id = ? AND closed_at IS NULL"
        " AND (',' || slugs || ',') LIKE ('%,' || ? || ',%')"
        " ORDER BY id DESC LIMIT 1", (sid, slug)).fetchone()
    if not row:
        return None, 'unmeasured'
    elapsed = int((datetime.now() -
                   datetime.fromisoformat(row['asked_at'])).total_seconds())
    slugs = [s for s in row['slugs'].split(',') if s]
    if len(slugs) > 1:
        clock = 'batch'
    elif elapsed > AWAY_AFTER:
        # Not "very slow recall" -- absence. He has gaps of 44 and 67 minutes.
        clock = 'away'
    else:
        clock = 'measured'
    remaining = [s for s in slugs if s != slug]
    if remaining:
        con.execute("UPDATE asks SET slugs = ? WHERE id = ?",
                    (','.join(remaining), row['id']))
    else:
        con.execute("UPDATE asks SET closed_at = ? WHERE id = ?", (now(), row['id']))
    return elapsed, clock


def probe(args):
    """The only way a question gets recorded. Stamps the faculty and the clock.

    The clock is NOT an argument. It is `now() - asks.asked_at`. If no `ask` was
    opened, this records clock='unmeasured' and seconds NULL -- a known hole,
    which is strictly better than a number somebody invented.

    Still refused: a non-HIT with no `--error-class`. A typo and a missing
    concept are not the same event and must not demote the same way.
    """
    if args.faculty not in FACULTIES:
        die(f"faculty must be one of {FACULTIES}, got '{args.faculty}'")
    if args.phase not in PHASES:
        die(f"phase must be one of {PHASES}, got '{args.phase}'")
    if args.result not in RESULTS:
        die(f"result must be one of {RESULTS}, got '{args.result}'")
    if args.seconds is not None:
        die("--seconds is gone. The clock is a SUBTRACTION, never a question.\n"
            "  Run `ask <slug>` at the moment you put the question on his screen;"
            " this command then subtracts.\n"
            "  Never ask him how long something took -- he estimated once,"
            " 'around 30 minitues' for fifteen questions, and it was divided"
            " into fifteen fake measurements.\n"
            "  If no clock was running, that is fine: the probe records"
            " UNMEASURED and a known hole beats an invented number.")
    if args.result != 'HIT' and not args.error_class:
        die(f"a {args.result} needs --error-class {ERROR_CLASSES}. 'He got it wrong' "
            f"is not a finding; which WAY it was wrong decides what happens next.")
    if args.error_class and args.error_class not in ERROR_CLASSES:
        die(f"error-class must be one of {ERROR_CLASSES}, got '{args.error_class}'")

    con = connect()
    c = concept(con, args.slug)
    sid = current_session(con)
    secs, clock = _consume_clock(con, sid, args.slug)
    con.execute(
        "INSERT INTO probes (session_id, concept_id, phase, faculty, depth_below,"
        " question, answer, result, seconds, clock, error_class, asked_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, c['id'], args.phase, args.faculty, args.below,
         args.question, args.answer, args.result, secs, clock,
         args.error_class, now()))
    # A typo or a fatigue slip is not evidence against the concept.
    penalise = args.result == 'MISS' and args.error_class not in NO_PENALTY
    con.execute(
        "UPDATE concepts SET attempts = attempts + 1, fails = fails + ?,"
        " updated_at = ? WHERE id = ?",
        (1 if penalise else 0, now(), c['id']))
    if args.phase == 'SWEEP' and c['swept_in'] is None:
        con.execute("UPDATE concepts SET swept_in = ? WHERE id = ?", (sid, c['id']))
    con.commit()
    tail = f" [{args.error_class}]" if args.error_class else ""
    free = "" if penalise or args.result == 'HIT' else " (no fail recorded)"
    stamp = {'measured': f"{secs}s measured",
             'batch': f"{secs}s for the whole batch -- do not divide it",
             'away': f"{secs}s: he left the desk, not slow recall",
             'unmeasured': "clock UNMEASURED"}[clock]
    verdict = "✓ PASS" if args.result == 'HIT' else "✗ FAIL"
    print(f"\n[HYPOTHESIS-VERIFY]")
    print(f"  Concept: {args.slug} — {c['name']}")
    print(f"  Tested:  {args.phase}/{args.faculty}")
    print(f"  Verdict: {verdict}{tail}")
    print(f"  Time:    {stamp}\n")
    print(f"probe recorded: {args.slug} {args.phase}/{args.faculty}"
          f" -> {args.result}{tail} ({stamp}){free}")
    if clock == 'unmeasured':
        print("  No `ask` was open, so seconds is NULL. That is correct -- do NOT"
              " ask him how long it took. Run `ask <slug>` when you put the NEXT"
              " question on screen and the clock records itself.", file=sys.stderr)

    _fatigue_check(con, sid)
    _suggest_teach(con, c, args.result, args.error_class)
    _log_to_bucket(c, args.result, args.error_class)


def _log_to_bucket(concept, result, error_class):
    """Log probe result with chain tracking."""
    if result != 'MISS' or error_class in NO_PENALTY:
        return  # Only log real gaps

    project_id = detect_project_id()
    bucket = read_bucket(project_id)

    # Initialize if empty
    if not bucket or bucket.get('status') == 'empty':
        bucket = init_bucket()
        bucket['primary_concept'] = concept['slug']
        bucket['started_at'] = now()
        bucket['status'] = 'in_progress'

    # Add or update chain entry
    existing = next((c for c in bucket['chain'] if c['concept'] == concept['slug']), None)
    if not existing:
        bucket['chain'].append({
            'concept': concept['slug'],
            'name': concept['name'],
            'blocked_by': None,
            'status': 'needs_teaching',
            'discovered_at': now()
        })

    # Recompute plan whenever chain changes
    bucket['resolution_plan'] = compute_resolution_plan(bucket['chain'])
    bucket['status'] = 'in_progress'

    write_bucket(bucket, project_id)


def compute_resolution_plan(chain):
    """Topological sort: resolve dependencies first (no blockers first)."""
    if not chain:
        return []

    plan = []
    remaining = {c['concept']: c for c in chain}
    visited = set()

    while remaining:
        # Find concepts with no blockers in remaining set
        ready = [c for c in remaining.values()
                if not c['blocked_by'] or c['blocked_by'] not in remaining]

        if not ready:
            # Circular dependency fallback: just add remaining
            plan.extend(list(remaining.keys()))
            break

        # Add ready concepts to plan
        for c in ready:
            if c['concept'] not in visited:
                plan.append(c['concept'])
                visited.add(c['concept'])
                del remaining[c['concept']]

    return plan


def detect_blockers(con, chain, primary_concept):
    """Identify which gaps block the primary concept."""
    # For each concept in chain, check if it's required by primary
    for entry in chain:
        concept_slug = entry['concept']

        # Check if this concept appears in requires field of primary
        primary = concept(con, primary_concept)
        requires = (primary.get('requires') or '').split(',')

        if concept_slug in requires:
            entry['blocks_primary'] = True
        else:
            # Check if it indirectly blocks (blocks something that blocks primary)
            entry['blocks_primary'] = False

    return chain


def archive_bucket(project_id=None):
    """Archive completed bucket to db, then empty it."""
    if project_id is None:
        project_id = detect_project_id()

    bucket = read_bucket(project_id)

    if bucket.get('status') != 'in_progress' or not bucket.get('chain'):
        return  # Nothing to archive

    con = connect()

    # Store in db as history
    con.execute(
        "INSERT INTO discovery_chains (project_id, primary_concept, chain_json, status, archived_at) "
        "VALUES (?,?,?,?,?)",
        (project_id, bucket.get('primary_concept'), json.dumps(bucket['chain']),
         'archived', now())
    )
    con.commit()

    # Empty the bucket
    write_bucket(init_bucket(), project_id)


def _suggest_teach(con, concept, result, error_class):
    """Auto-suggest teaching when MISS with real gap detected."""
    if result != 'MISS' or error_class in NO_PENALTY:
        return  # Only teach on real gaps, not typos/fatigue

    fail_count = con.execute(
        "SELECT COUNT(*) FROM probes WHERE concept_id = ? AND result = 'MISS'",
        (concept['id'],)).fetchone()[0]

    if fail_count == 1:
        print(f"\n⚠️  SUGGESTION: '{concept['slug']}' failed. Run teach-open to explain "
              f"the gap, then re-test.", file=sys.stderr)
    elif fail_count >= 2:
        print(f"\n🔴 PATTERN: '{concept['slug']}' failed {fail_count}x. Teaching needed "
              f"before next probe.", file=sys.stderr)


def _fatigue_check(con, sid):
    """The stop signal v1 kept guessing at. Two measurable symptoms, this session:
    answers getting slower, and errors turning clerical."""
    rows = con.execute(
        "SELECT result, seconds, clock, error_class FROM probes WHERE session_id = ?"
        " ORDER BY id", (sid,)).fetchall()
    if len(rows) < 6:
        return
    # Only `measured` is a recall signal. A batch span belongs to the batch, an
    # `away` span is him at lunch, and `unmeasured` is nothing at all. Feeding
    # any of those to a slowdown test is how a stop signal becomes superstition.
    secs = [r['seconds'] for r in rows
            if r['seconds'] is not None and r['clock'] == 'measured']
    warn = []
    if len(secs) >= 6:
        first, last = secs[:3], secs[-3:]
        if statistics.median(last) > 2 * max(statistics.median(first), 1):
            warn.append(f"answers slowed {statistics.median(first):.0f}s"
                        f" -> {statistics.median(last):.0f}s")
    recent = [r['error_class'] for r in rows[-4:]]
    if sum(1 for e in recent if e in NO_PENALTY) >= 2:
        warn.append("errors turned clerical (typo/fatigue) in the last 4 probes")
    if warn:
        print("FATIGUE: " + "; ".join(warn) +
              "\n  -> land the session. A rung lost while tired is a rung re-taught.",
              file=sys.stderr)


def bucket_show(args=None):
    """Show current bucket state for this project."""
    project_id = detect_project_id()
    bucket = read_bucket(project_id)

    print(f"PROJECT: {project_id}")
    print(f"BUCKET PATH: {bucket_path(project_id)}")

    if not bucket or bucket.get('status') == 'empty':
        print("BUCKET: empty (no active discovery chains)")
        return

    print("BUCKET (active discovery chains):")
    print(f"  Primary: {bucket.get('primary_concept')}")
    print(f"  Status: {bucket.get('status')}")
    print(f"  Chain ({len(bucket.get('chain', []))} concepts):")
    for entry in bucket.get('chain', []):
        blocks = " [blocks primary]" if entry.get('blocks_primary') else ""
        print(f"    - {entry['concept']:<20} status={entry['status']}{blocks}")

    if bucket.get('resolution_plan'):
        print(f"\n  Resolution order: {' → '.join(bucket['resolution_plan'])}")


def bucket_archive(args=None):
    """Archive completed bucket to database."""
    project_id = detect_project_id()
    archive_bucket(project_id)
    print(f"Bucket archived for {project_id}")


def teach_suggest(args=None):
    """Show concepts that need teaching based on failure patterns."""
    con = connect()

    # Find concepts with MISS probes that lack teaching
    needs_teach = con.execute("""
        SELECT c.slug, c.name, COUNT(p.id) fails, c.depth
        FROM concepts c
        JOIN probes p ON p.concept_id = c.id AND p.result = 'MISS'
        WHERE c.parked = 0 AND c.state = 'CANT'
        GROUP BY c.id
        ORDER BY fails DESC, c.depth
    """).fetchall()

    if not needs_teach:
        print("no concepts with confirmed gaps (all MISS probes have teaching or no gaps detected)")
        return

    print(f"CONCEPTS NEEDING TEACHING ({len(needs_teach)}):")
    for n in needs_teach[:10]:
        print(f"  [{n['depth']}] {n['slug']:<28} {n['name']:<34} ({n['fails']}x failed)")
        print(f"       → Run: teach-open {n['slug']}")


def route_next(args=None):
    """Auto-route: smart next concept based on verb coverage + due + sweep order."""
    con = connect()

    # Step 1: Check verb coverage (which verbs need work)
    verbs_covered = con.execute(
        "SELECT DISTINCT verb FROM concepts WHERE state='CAN' AND verb IS NOT NULL AND parked=0"
    ).fetchall()
    covered = {v['verb'] for v in verbs_covered} if verbs_covered else set()
    all_verbs = set(FACULTIES[6:])  # Circle verbs: understand through improve
    starved = all_verbs - covered

    # Step 2: Prefer due/stale concepts
    due = con.execute(
        "SELECT id FROM concepts WHERE state='CANT' AND parked=0"
        " AND next_review IS NOT NULL AND next_review <= date('now')"
        " ORDER BY next_review LIMIT 1"
    ).fetchone()

    # Step 3: Route to starved verb first, then unswept
    if starved:
        nxt = con.execute(
            "SELECT slug, name, depth, verb FROM concepts"
            " WHERE state='CANT' AND parked=0 AND verb IN ("
            + ','.join('?' * len(starved)) + ") AND swept_in IS NOT NULL"
            " ORDER BY depth LIMIT 1",
            tuple(starved)
        ).fetchone()
    else:
        nxt = None

    if not nxt:
        nxt = con.execute(
            "SELECT slug, name, depth, verb FROM concepts"
            " WHERE state='CANT' AND parked=0 AND swept_in IS NULL"
            " ORDER BY depth LIMIT 1"
        ).fetchone()

    if nxt:
        verb_note = f" [{nxt['verb']}]" if nxt['verb'] else ""
        due_note = " (stale)" if due and due['id'] == nxt['id'] else ""
        print(f"[{nxt['depth']}] {nxt['slug']:<28} {nxt['name']}{verb_note}{due_note}")
    else:
        print("all CANT concepts are parked or all are owned. Gate is ready to unlock.")


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
    # v2.4: SKIP-ON-HIT. Teaching what he just got right is where the hours went --
    # 4 of 5 concepts in one 2026-08-08 session were already owned and re-drilled.
    # The signal for "he owns it, nothing to teach" is: latest probe HIT AND no
    # diagnosed floor. A floor means a real failure was found -- teach into that
    # even if a later confirmation probe hit. No floor + a HIT = he just produced
    # it; re-probe a different instance if you doubt the HIT, do not explain.
    latest = con.execute(
        "SELECT result FROM probes WHERE concept_id = ? ORDER BY asked_at DESC,"
        " id DESC LIMIT 1", (c['id'],)).fetchone()
    has_floor = con.execute(
        "SELECT COUNT(*) FROM floors WHERE concept_id = ?", (c['id'],)).fetchone()[0]
    if latest and latest['result'] == 'HIT' and not has_floor:
        die(f"'{args.slug}' latest probe is a HIT and no floor is recorded -- he just "
            f"produced it, there is no failure to teach into. Move on, or if you "
            f"suspect the HIT was shallow, re-probe a DIFFERENT instance and teach "
            f"only if that misses.")
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
    # v2.4: record that teaching HAPPENED, cheaply, at open -- so the density
    # meter stops reading 0% while prose explanation goes untracked. teach-close
    # still writes the canonical cached text; this only stamps the event.
    con.execute("UPDATE concepts SET taught_in = ?, updated_at = ? WHERE id = ?",
                (current_session(con), now(), c['id']))
    con.commit()
    print(f"teach-open {args.slug}: {attempts} prior attempts, {c['fails']} fails."
          f" (logged as an explain event this session)")
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
    """CAN needs unaided production. transferred needs a second context."""
    if args.state not in STATES:
        die(f"state must be one of {STATES}")
    if args.evidence not in EVIDENCE:
        die(f"evidence must be one of {EVIDENCE}")

    con = connect()
    c = concept(con, args.slug)

    if args.evidence == 'assisted' and args.state == 'CAN':
        die("assisted evidence never reaches CAN, however well he followed.")
    if args.evidence == 'guided' and args.state == 'CAN':
        die("guided means characters went into his file from a push. It finished"
            " the gate; it did not prove the concept. Run the twin -- same idea,"
            " different instance, no push above L2 -- and promote on that.")

    if args.state == 'CAN':
        placeholders = ','.join('?' * len(PRODUCTION_PHASES))
        proof = con.execute(
            "SELECT id FROM probes WHERE concept_id = ? AND result = 'HIT'"
            f" AND phase IN ({placeholders})",
            (c['id'], *PRODUCTION_PHASES)).fetchone()
        if proof is None:
            die(f"'{args.slug}' has no HIT probe from a production phase "
                f"{PRODUCTION_PHASES}. CAN means he produced it from a blank page. "
                f"Open a gate instead.")
        # v2: an artifact-phase promotion requires the artifact to have been kept.
        # "Snapshot before grading" as prose is exactly the kind of rule v1 lost.
        art = con.execute(
            "SELECT phase FROM probes WHERE concept_id = ? AND result = 'HIT'"
            f" AND phase IN ({','.join('?' * len(ARTIFACT_PHASES))})",
            (c['id'], *ARTIFACT_PHASES)).fetchone()
        if art:
            snap = con.execute(
                "SELECT n FROM attempts WHERE slug = ? ORDER BY n DESC LIMIT 1",
                (args.slug,)).fetchone()
            if snap is None:
                die(f"'{args.slug}' passed in {art['phase']} but no attempt was ever "
                    f"archived for it. Run `attempt snap {art['phase']} {args.slug} "
                    f"--src <his file>` BEFORE grading -- the file he edits gets "
                    f"overwritten, and the diff between attempts is the evidence.")

        # v2.2: a review whose findings can be ignored is theatre. Blocking
        # findings hold the credit until he FIXES them or they are WAIVED with
        # a stated reason -- which is what "iterative feedback" means when it is
        # not a slogan.
        open_findings = con.execute(
            "SELECT id, severity, finding FROM reviews WHERE slug = ? AND"
            f" state = 'OPEN' AND severity IN ({','.join('?' * len(BLOCKING))})",
            (args.slug, *BLOCKING)).fetchall()
        if open_findings:
            for r in open_findings:
                print(f"  #{r['id']} [{r['severity']}] {r['finding']}",
                      file=sys.stderr)
            die(f"{len(open_findings)} blocking review finding(s) still OPEN on "
                f"'{args.slug}'. He has not answered the review yet -- crediting "
                f"now teaches that review output is optional.")

        # v2.3: the twin. A gate that took characters from a push measured the
        # push. Credit needs a LATER gate on the same concept that took none
        # above L2 -- same idea, different instance.
        charged = con.execute(
            "SELECT MAX(gate_id) g, COUNT(*) n FROM stalls WHERE slug = ?"
            " AND level_n >= 3", (args.slug,)).fetchone()
        if charged and charged['n']:
            twin = con.execute(
                "SELECT id FROM gates WHERE concept_id = ? AND id > ?"
                " AND result = 'PASS' AND id NOT IN"
                " (SELECT gate_id FROM stalls WHERE level_n >= 3"
                "  AND gate_id IS NOT NULL)",
                (c['id'], charged['g'])).fetchone()
            if twin is None:
                die(f"'{args.slug}' took {charged['n']} charged push(es) — code "
                    f"went into his file on gate #{charged['g']}. That gate "
                    f"measured the push. Open a twin: same idea, different "
                    f"instance, no push above L2, and promote on that one.")

        # Force transfer: CAN requires 2 different instances, not just one proof
        hit_probes = con.execute(
            "SELECT DISTINCT phase FROM probes WHERE concept_id = ? AND result = 'HIT'"
            " AND phase IN (SELECT DISTINCT phase FROM probes WHERE concept_id = ?)",
            (c['id'], c['id'])).fetchall()
        distinct_phases = len(set(p['phase'] for p in hit_probes))
        if distinct_phases < 2 and c['state'] != 'CAN':
            die(f"promote '{args.slug}' to CAN requires 2 HIT probes on different "
                f"instances/phases. Currently {distinct_phases} phase(s). "
                f"Test again in a different context first.")

        # v2: the copy check that fired once by luck in v1 (E16) is now mechanical.
        if not args.copy_checked:
            die(f"promote '{args.slug}' needs --copy-checked. Before crediting, compare "
                f"his submission against YOUR last two messages. If he reproduced your "
                f"worked example, that is not evidence -- re-probe with a different "
                f"instance. Pass --copy-checked once you have actually done it.")

    if args.evidence == 'transferred':
        if c['state'] != 'CAN':
            die(f"'{args.slug}' is {c['state']}. Transfer is a second, later, unaided "
                f"use of something already CAN.")
        t = con.execute(
            "SELECT id FROM probes WHERE concept_id = ? AND phase = 'TRANSFER'"
            " AND result = 'HIT'", (c['id'],)).fetchone()
        if t is None:
            die(f"'{args.slug}' has no HIT probe from a TRANSFER phase. Re-test it in "
                f"a different context or language first.")

    days = review_interval(args.state, c['depth'], args.evidence)
    nxt = (date.today() + timedelta(days=days)).isoformat() if days else None
    con.execute(
        "UPDATE concepts SET state = ?, evidence = ?, next_review = ?, updated_at = ?"
        " WHERE id = ?", (args.state, args.evidence, nxt, now(), c['id']))
    con.commit()

    # Track in bucket if promoted to CAN
    if args.state == 'CAN':
        _update_bucket_on_promote(args.slug)

    if c['state'] == args.state and c['evidence'] == args.evidence:
        print(f"{args.slug}: NO CHANGE — already {args.state}/{args.evidence}."
              f" Owned count did not move. (review reset to {nxt})")
    else:
        print(f"{args.slug}: {c['state']}/{c['evidence']} ->"
              f" {args.state}/{args.evidence} (NEW, review {nxt})")


def _update_bucket_on_promote(slug):
    """Update bucket status when concept is promoted to CAN."""
    project_id = detect_project_id()
    bucket = read_bucket(project_id)

    if not bucket or bucket.get('status') == 'empty':
        return  # No active bucket

    # Mark this concept as resolved in chain
    for entry in bucket.get('chain', []):
        if entry['concept'] == slug:
            entry['status'] = 'resolved'
            break

    # Check if all are resolved
    all_resolved = all(e['status'] == 'resolved' for e in bucket.get('chain', []))

    if all_resolved:
        bucket['status'] = 'ready_archive'

    write_bucket(bucket, project_id)


def demote(args):
    """Demote as readily as promote. With two states there is one step: CAN -> CANT.

    A typo or a fatigue slip must not cost a rung. v1 had no way to say that, so
    `pirnt` and `wount_words` were argued about in prose three times.
    """
    if args.error_class and args.error_class in NO_PENALTY:
        die(f"a '{args.error_class}' does not demote. Name it, do not charge for it.")
    con = connect()
    c = concept(con, args.slug)
    i = STATES.index(c['state']) if c['state'] in STATES else 1
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


# ---- misconceptions: the shape of how he is wrong -------------------------
# A floor is a position on the ladder. A misconception is a false belief, and it
# does not live on the ladder at all -- it resurfaces in concepts that share no
# prerequisite. v2 noticed one in prose ("the None idea again, in different
# clothes") and had nowhere to put it.

ASPECTS = ('language', 'engineering', 'data', 'api', 'process')


def misconception(args):
    con = connect()
    act = args.action
    # one column, not a new table: separates a HIT (belief shown) from a
    # SURVIVED test (belief absent). Without it a disproof can only be filed as
    # a hit -- the exact error that inflated a count in session 9.
    cols = [r[1] for r in con.execute("PRAGMA table_info(misconception_hits)")]
    if 'kind' not in cols:
        con.execute("ALTER TABLE misconception_hits ADD COLUMN kind TEXT"
                    " NOT NULL DEFAULT 'hit'")
        con.commit()

    if act == 'list':
        rows = con.execute(
            "SELECT m.*, (SELECT COUNT(*) FROM misconception_hits h"
            "  WHERE h.misconception_id = m.id AND h.kind = 'hit') n,"
            " (SELECT COUNT(*) FROM misconception_hits h"
            "  WHERE h.misconception_id = m.id AND h.kind = 'survived') s"
            " FROM misconceptions m ORDER BY m.state, n DESC").fetchall()
        if not rows:
            print("no misconceptions on record.")
            return
        for r in rows:
            mark = '*' if r['state'] == 'OPEN' else ' '
            surv = f", {r['s']} survived" if r['s'] else ""
            print(f"{mark} {r['slug']:<24} [{r['aspect']}] {r['n']} hit(s){surv}"
                  f"{'' if r['state'] == 'OPEN' else '  RETIRED'}")
            print(f"    believes : {r['belief']}")
            print(f"    true     : {r['correction']}")
            if r['state'] == 'RETIRED':
                print(f"    retired  : {r['retired_evidence']}")
        return

    if act == 'open':
        seen = [s.strip() for s in (args.seen_in or '').split(',') if s.strip()]
        if len(seen) < 2:
            die("a misconception needs >=2 concepts it surfaced under. One "
                "concept is a miss, not a pattern -- record it as a probe.")
        if args.aspect not in ASPECTS:
            die(f"aspect must be one of {ASPECTS}, got '{args.aspect}'")
        for s in seen:
            concept(con, s)          # refuses on a slug that is not in the bank
        if not args.belief.strip() or not args.correction.strip():
            die("both --belief and --correction are required. A misconception "
                "you cannot state as a false sentence is not one yet.")
        sid = current_session(con)
        cur = con.execute(
            "INSERT INTO misconceptions (slug, name, belief, correction, aspect,"
            " opened_in, opened_at, state) VALUES (?,?,?,?,?,?,?,'OPEN')",
            (args.slug, args.name, args.belief.strip(), args.correction.strip(),
             args.aspect, sid, now()))
        for s in seen:
            con.execute(
                "INSERT INTO misconception_hits (misconception_id, session_id,"
                " concept, note, ts) VALUES (?,?,?,?,?)",
                (cur.lastrowid, sid, s, args.evidence or 'opening evidence', now()))
        con.commit()
        print(f"misconception OPEN: {args.slug} [{args.aspect}] across {seen}")
        print(f"  believes: {args.belief.strip()}")
        print(f"  true    : {args.correction.strip()}")
        print("It is disproved by production that does not exhibit it, never by "
              "an explanation.")
        return

    m = con.execute("SELECT * FROM misconceptions WHERE slug = ?",
                    (args.slug,)).fetchone()
    if m is None:
        die(f"no misconception '{args.slug}'.")

    if act == 'hit':
        if not args.note.strip():
            die("a hit needs what he actually wrote. 'it happened again' is not "
                "evidence of anything.")
        con.execute(
            "INSERT INTO misconception_hits (misconception_id, session_id,"
            " concept, note, ts) VALUES (?,?,?,?,?)",
            (m['id'], current_session(con), args.concept, args.note.strip(), now()))
        con.commit()
        n = con.execute("SELECT COUNT(*) FROM misconception_hits WHERE"
                        " misconception_id = ? AND kind = 'hit'",
                        (m['id'],)).fetchone()[0]
        print(f"{args.slug}: hit #{n}"
              + (f" under {args.concept}" if args.concept else ""))
        if n >= 4:
            print("  4+ hits. Explaining it again is not working -- it needs a "
                  "gate that makes the belief impossible to act on.")
        return

    if act == 'survived':
        # the belief was TESTED and did NOT appear. This is disproof evidence,
        # not a hit -- it must never touch the hit counter. Reach for `retire`
        # once the disproof is a real unaided artifact.
        if not args.note.strip():
            die("survived needs what he wrote that did NOT exhibit the belief. "
                "That artifact is the whole point -- name it.")
        if m['state'] == 'RETIRED':
            print(f"{args.slug} is already retired.")
            return
        con.execute(
            "INSERT INTO misconception_hits (misconception_id, session_id,"
            " concept, note, ts, kind) VALUES (?,?,?,?,?,'survived')",
            (m['id'], current_session(con), args.concept, args.note.strip(), now()))
        con.commit()
        s = con.execute("SELECT COUNT(*) FROM misconception_hits WHERE"
                        " misconception_id = ? AND kind = 'survived'",
                        (m['id'],)).fetchone()[0]
        print(f"{args.slug}: survived #{s}"
              + (f" under {args.concept}" if args.concept else "")
              + " (belief absent -- NOT a hit)")
        if s >= 2:
            print("  2+ clean survivals. If one is an unaided artifact, "
                  "`retire` it -- do not keep testing a belief he no longer holds.")
        return

    if act == 'retire':
        if m['state'] == 'RETIRED':
            print(f"{args.slug} was already retired.")
            return
        if not (args.evidence or '').strip():
            die("retiring needs the unaided artifact that did NOT exhibit it. "
                "'he seems to get it now' is the v1 failure, written down.")
        con.execute(
            "UPDATE misconceptions SET state='RETIRED', retired_at=?,"
            " retired_evidence=? WHERE id=?", (now(), args.evidence.strip(), m['id']))
        con.commit()
        print(f"misconception RETIRED: {args.slug} -- {args.evidence.strip()}")
        return


# ---- the push ladder -------------------------------------------------------
# Ordered, and you climb one rung at a time. 0-2 add no information he did not
# already have, so they cost nothing. 3+ put characters in his file and are
# charged: the concept cannot reach CAN on that gate, only on a later twin with
# no pushes above 2.
LEVELS = ('RESTATE', 'LOCATE', 'QUESTION', 'SHAPE', 'SKELETON', 'LINE')
FREE_LEVEL = 2                 # <= this is not a hint, it is the contract again
LEVEL_HELP = {
    'RESTATE':  'the contract again, in different words. no new information.',
    'LOCATE':   'where the next thing goes. "the loop body is empty."',
    'QUESTION': 'a question whose answer IS the next line.',
    'SHAPE':    'comment lines in his file: # open the file here, name the handle',
    'SKELETON': 'structure with the holes left in: with ____ as f:',
    'LINE':     'one working line. one. it costs the promotion.',
}
# What the freeze IS. Different holes, different remedies -- and two of them are
# made worse by a hint, which is why the ladder refuses to climb for them.
FREEZE_KINDS = {
    'blank':  'does not know what the program should DO -> decomposition hole',
    'form':   'knows what, cannot write the form        -> drill the form',
    'recall': 'knows the shape, forgot the name         -> he SEARCHES, you watch',
    'commit': 'knows it, will not type it               -> nerve, not knowledge',
}


def push(args):
    """A metered nudge into his file. The only door: the write-guard has no other."""
    con = connect()
    if args.action == 'list':
        rows = con.execute("SELECT * FROM stalls ORDER BY id DESC LIMIT 30").fetchall()
        if not rows:
            print("no stalls recorded.")
            return
        for r in rows:
            mark = {'OPEN': '?', 'CONFIRMED': '!', 'FALSE': 'x'}[r['hyp_state']]
            print(f"#{r['id']:<4} {r['slug']:<20} L{r['level_n']} {r['level']:<9}"
                  f" [{r['kind']}] {mark} {r['hyp_state']}")
            print(f"      hypothesis: {r['hypothesis']}")
            if r['hyp_evidence']:
                print(f"      verdict by {r['hyp_by']}: {r['hyp_evidence']}")
        return

    if args.action == 'verdict':
        s = con.execute("SELECT * FROM stalls WHERE id=?", (args.id,)).fetchone()
        if s is None:
            die(f"no stall #{args.id}.")
        if args.confirmed == args.false_:
            die("pass exactly one of --confirmed / --false. A hypothesis you"
                " cannot call either way was too vague to be worth recording —"
                " rewrite it as a claim he could deny.")
        if args.by not in ('probe', 'learner'):
            die("--by must be probe or learner.")
        if not (args.evidence or '').strip():
            die("a verdict needs the evidence. What did he write, or what did he"
                " say, in his words?")
        state = 'CONFIRMED' if args.confirmed else 'FALSE'
        # One hypothesis, however many pushes carried it. Climbing the ladder on
        # one freeze restates the same guess at each rung; the verdict lands on
        # all of them or the interview asks him the same thing four times.
        cur = con.execute(
            "UPDATE stalls SET hyp_state=?, hyp_by=?, hyp_evidence=?,"
            " hyp_closed_at=? WHERE hypothesis=? AND hyp_state='OPEN'",
            (state, args.by, args.evidence.strip(), now(), s['hypothesis']))
        con.commit()
        print(f"stall #{args.id} hypothesis {state} (by {args.by})"
              + (f" — closed {cur.rowcount} pushes carrying it"
                 if cur.rowcount > 1 else ""))
        if args.by == 'learner' and state == 'CONFIRMED':
            print("  His self-report is a HINT, not evidence. Probe it before you"
                  " insert a rung on the strength of it.")
        if state == 'FALSE':
            print("  Good. A falsified hypothesis is worth more than a vague one"
                  " left open — it removes a rung you were about to waste.")
        if state == 'CONFIRMED':
            same = con.execute(
                "SELECT DISTINCT slug FROM stalls WHERE hyp_state='CONFIRMED'"
                " AND kind=?", (s['kind'],)).fetchall()
            if len(same) >= 2:
                print(f"  CONFIRMED '{s['kind']}' freezes now span {len(same)}"
                      f" concepts: {', '.join(r['slug'] for r in same)}.")
                print("  That is a pattern, not a rung. Open a misconception or a"
                      " floor — do not fix it one concept at a time.")
        return

    if args.action == 'interview':
        rows = con.execute(
            "SELECT MIN(id) id, hypothesis, kind,"
            " GROUP_CONCAT(DISTINCT slug) slugs, COUNT(*) n,"
            " MAX(level_n) top FROM stalls WHERE hyp_state='OPEN'"
            " GROUP BY kind, hypothesis ORDER BY n DESC").fetchall()
        if not rows:
            print("no open hypotheses. Nothing to interview him about.")
            return
        print("OPEN HYPOTHESES — put these to him as claims he can DENY.\n")
        print("Rules for this conversation:")
        print("  * one at a time, stated as a flat claim: 'you freeze when the")
        print("    output shape is not written down yet.' Not 'do you struggle")
        print("    with...' — a vague question gets a vague yes.")
        print("  * a 'yes' is a HINT. Follow every yes with a probe that would")
        print("    fail if it were true, and record the verdict --by probe.")
        print("  * a 'no' is worth more. Record it FALSE and drop the rung.\n")
        for k in FREEZE_KINDS:
            g = [r for r in rows if r['kind'] == k]
            if not g:
                continue
            print(f"[{k}] {FREEZE_KINDS[k]}")
            for r in g:
                cost = f", climbed to L{r['top']}" if r['top'] >= 3 else ""
                print(f"  #{r['id']} {r['slugs']} ({r['n']} push{'es' if r['n'] > 1 else ''}"
                      f"{cost}): {r['hypothesis']}")
            print()
        multi = [r for r in rows if len(set(r['slugs'].split(','))) >= 2]
        for r in multi:
            print(f"  ** #{r['id']} froze him on {len(set(r['slugs'].split(',')))}"
                  f" different concepts. If he confirms it, that is a"
                  f" misconception, not a rung.")
        print(f"{len(rows)} distinct hypotheses open. Record each: push verdict"
              " <id> --confirmed|--false --by probe|learner --evidence \"...\"")
        return

    # ---- the push itself ---------------------------------------------------
    lvl = args.level
    if lvl not in LEVELS:
        die(f"level must be one of {LEVELS}")
    n = LEVELS.index(lvl)
    if args.kind not in FREEZE_KINDS:
        die(f"--kind must be one of {tuple(FREEZE_KINDS)}:\n  " +
            '\n  '.join(f'{k}: {v}' for k, v in FREEZE_KINDS.items()))
    if len((args.hypothesis or '').strip()) < 15:
        die("--hypothesis is required on every push. A freeze is data: what hole"
            " does THIS one suggest? The push unblocks the hour; the hypothesis"
            " is the only part that survives the week.")

    g = con.execute("SELECT g.*, c.slug FROM gates g JOIN concepts c"
                    " ON c.id = g.concept_id WHERE g.closed_at IS NULL"
                    " ORDER BY g.id DESC LIMIT 1").fetchone()
    if g is None:
        die("no open gate. He cannot be stuck on a blank page that was never"
            " opened — open the gate first, or this is just you writing code.")

    prev = con.execute("SELECT * FROM stalls WHERE gate_id=? ORDER BY id DESC"
                       " LIMIT 1", (g['id'],)).fetchone()
    if prev is None and n > 1:
        die(f"the first push on a gate is L0 RESTATE or L1 LOCATE. Opening at"
            f" {lvl} assumes you already know why he is stuck, and you do not —"
            f" you have not asked him anything yet.")
    if prev and n > prev['level_n'] + 1:
        die(f"no skipping: last push was L{prev['level_n']} {prev['level']}, so"
            f" the next is L{prev['level_n']+1} {LEVELS[prev['level_n']+1]}."
            f" Jumping to {lvl} hands him the answer and calls it a nudge.")

    target = g['target']
    tpath = Path(target) if Path(target).is_absolute() else HERE.parent.parent / target
    cur_sha = _sha(tpath.read_bytes()) if tpath.exists() else _sha(b'')

    # The anti-crutch lock. A bigger hint is not something you get for not
    # trying. Free levels (<=2) are exempt: two questions in a row before he
    # touches the keyboard is a conversation, not a crutch. Putting CHARACTERS
    # in a file he has not touched since the last push is finishing his work.
    if prev and n >= 3 and prev['file_sha'] == cur_sha:
        die(f"{target} has not changed since the L{prev['level_n']} push. He has"
            f" not tried anything with it yet, so writing in it now is not a"
            f" nudge — it is doing the gate for him. Re-serve L{prev['level_n']}"
            f" ({prev['level']}) in different words and wait.")

    # Two freezes that a hint makes WORSE.
    if args.kind == 'recall' and n >= 3:
        die("kind=recall: he knows the shape and forgot the NAME. Handing him the"
            " name teaches him to ask you next time. The remedy is the search --"
            " tell him which source answers it and why, watch him look it up, and"
            " log it with `lookup`. That is the skill that outlives this session.")
    if args.kind == 'commit' and n >= 3:
        die("kind=commit: he knows it and will not type it. That is nerve, not"
            " knowledge, and information does not fix it. Tell him to write the"
            " version he thinks is wrong and run it. Being wrong on the screen in"
            " 20 seconds beats being right in his head in 20 minutes.")

    text = (args.text or '').strip('\n')
    if n >= 3 and not text:
        die(f"L{n} {lvl} puts characters in his file. --text is required.")
    if lvl == 'SHAPE':
        bad = [ln for ln in text.splitlines()
               if ln.strip() and not ln.lstrip().startswith('#')]
        if bad:
            die("SHAPE is comments only — the shape of the work, not the work."
                f" This line is code: {bad[0].strip()!r}")
    if lvl == 'SKELETON':
        if '___' not in text:
            die("SKELETON leaves the holes in. Use ___ where he must decide:"
                " `with ____ as f:`. Without a hole it is not a skeleton, it is"
                " the answer with extra steps.")
    if lvl == 'LINE':
        body = [ln for ln in text.splitlines() if ln.strip()]
        if len(body) != 1:
            die(f"LINE is ONE line. You passed {len(body)}. If one line does not"
                f" unblock him, the gate is too big — close it ABANDONED and"
                f" split the contract instead of writing the file for him.")

    if n >= 3:
        lines = tpath.read_text(encoding='utf-8').splitlines(True) if tpath.exists() else []
        at = args.anchor if args.anchor is not None else len(lines) + 1
        at = max(1, min(at, len(lines) + 1))
        block = text if text.endswith('\n') else text + '\n'
        lines[at - 1:at - 1] = [block]
        tpath.parent.mkdir(parents=True, exist_ok=True)
        tpath.write_text(''.join(lines), encoding='utf-8')
        cur_sha = _sha(tpath.read_bytes())
    else:
        at = None

    con.execute(
        "INSERT INTO stalls (session_id, gate_id, slug, level_n, level, kind,"
        " hypothesis, text, target, anchor, file_sha, ts)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (current_session(con), g['id'], g['slug'], n, lvl, args.kind,
         args.hypothesis.strip(), text or None, target, at, cur_sha, now()))
    con.commit()
    cnt = con.execute("SELECT COUNT(*) FROM stalls WHERE gate_id=?",
                      (g['id'],)).fetchone()[0]
    print(f"push L{n} {lvl} [{args.kind}] on gate #{g['id']} {g['slug']}"
          f"  (push {cnt} on this gate)")
    if n >= 3:
        print(f"  wrote {len(text.splitlines())} line(s) into {target} at line {at}")
        print("  CHARGED: this gate can no longer reach CAN. He needs a twin --"
              " same idea, different instance, no push above L2.")
    if cnt >= 4:
        print("  4 pushes on one gate. The gate is too big or the floor is below"
              " it. Close it ABANDONED and descend — grinding him through it"
              " teaches that stalling is answered with more hints.")
    print(f"  hypothesis logged OPEN: {args.hypothesis.strip()}")
    print("  Test it before you believe it: `push interview` when the gate closes.")


def lookup(args):
    """Record an uncertainty that was resolved by SEARCHING, in front of him.

    Refuses the two ways this decays into theatre: a source that is not a
    source, and a correction recorded as "I refined my answer" instead of the
    false sentence itself.
    """
    con = connect()
    if args.action == 'list':
        rows = con.execute("SELECT * FROM lookups ORDER BY id DESC LIMIT 20").fetchall()
        if not rows:
            print("no lookups on record. If nothing has been uncertain in five"
                  " sessions, the tutor is performing fluency, not modelling it.")
            return
        for r in rows:
            print(f"#{r['id']} {r['ts'][:16]}  {r['claim']}")
            print(f"    why      : {r['strategy']}")
            print(f"    source   : {r['source']}")
            print(f"    found    : {r['found']}")
            if r['corrected']:
                print(f"    I WAS WRONG: {r['corrected']}")
        return

    for f in ('claim', 'strategy', 'source', 'found'):
        if not (getattr(args, f) or '').strip():
            die(f"--{f} is required. An unrecorded lookup is a lookup he cannot"
                " learn the procedure from.")
    src = args.source.strip()
    if not (src.startswith('http') or '/' in src or src.startswith('man ')
            or src.startswith('help(')):
        die("--source must be the thing you actually read: a URL, a doc path, a"
            " man page, help(). 'my knowledge' is what you were unsure of, not a"
            " source.")
    if (args.corrected or '').strip():
        low = args.corrected.strip().lower()
        for weasel in ('refined', 'clarified', 'nuance', 'more precise'):
            if weasel in low:
                die("--corrected must be the FALSE SENTENCE you said, quoted, not"
                    " a description of having improved. 'I said X; X is wrong'.")
    sid = current_session(con)
    con.execute(
        "INSERT INTO lookups (session_id, claim, strategy, source, found,"
        " corrected, concept, ts) VALUES (?,?,?,?,?,?,?,?)",
        (sid, args.claim.strip(), args.strategy.strip(), src, args.found.strip(),
         (args.corrected or '').strip() or None, args.concept, now()))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM lookups").fetchone()[0]
    print(f"lookup #{n}: {args.claim.strip()}")
    print(f"  source: {src}")
    if (args.corrected or '').strip():
        print("  logged as a CORRECTION. Say it to him in those words -- watching"
              " you be wrong on purpose is the lesson.")


def review(args):
    """Studio code review: findings on ONE attempt, fixed, then reviewed again.

    A finding is a concrete failure with an input, never a preference. Blocking
    findings hold the promotion until they are FIXED or explicitly WAIVED with a
    reason -- see promote().
    """
    con = connect()
    act = args.action

    if act == 'list':
        q = ("SELECT * FROM reviews" + (" WHERE state='OPEN'" if args.open_only else "")
             + " ORDER BY state, id DESC LIMIT 40")
        rows = con.execute(q).fetchall()
        if not rows:
            print("no review findings.")
            return
        for r in rows:
            loc = f"{r['file']}:{r['line']}" if r['file'] else '-'
            print(f"#{r['id']:<4} {r['state']:<6} r{r['round']} [{r['severity']}]"
                  f" {r['slug']} {loc}")
            print(f"      {r['finding']}")
            if r['resolution']:
                print(f"      -> {r['resolution']}")
        return

    if act == 'add':
        if args.severity not in SEVERITIES:
            die(f"severity must be one of {SEVERITIES}")
        f = (args.finding or '').strip()
        if len(f) < 20:
            die("a finding names a concrete failure with the input that causes"
                " it: 'loses every row if it dies at record 900', not 'could be"
                " cleaner'. Under 20 characters it is a preference.")
        if args.severity in BLOCKING and not any(
                ch.isdigit() or ch in "'\"" for ch in f):
            die("a blocker/correctness finding must carry the concrete case --"
                " an input, a value, a quoted line. Without one he cannot"
                " reproduce it, and an unreproducible finding is an opinion.")
        att = None
        if args.attempt:
            att = args.attempt
        else:
            row = con.execute("SELECT id FROM attempts WHERE slug=? ORDER BY id"
                              " DESC LIMIT 1", (args.slug,)).fetchone()
            att = row['id'] if row else None
        if att is None:
            die("nothing to review: no archived attempt for this slug. Run"
                " `attempt snap` first -- reviewing a file you did not archive"
                " is v1 grading log.md in place.")
        rnd = con.execute("SELECT COALESCE(MAX(round),0)+1 FROM reviews WHERE"
                          " slug=?", (args.slug,)).fetchone()[0]
        if args.round:
            rnd = args.round
        cur = con.execute(
            "INSERT INTO reviews (session_id, attempt_id, slug, round, file,"
            " line, severity, finding, opened_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (current_session(con), att, args.slug, rnd, args.file, args.line,
             args.severity, f, now()))
        con.commit()
        print(f"review #{cur.lastrowid} round {rnd} [{args.severity}] {args.slug}")
        if args.severity in BLOCKING:
            print("  BLOCKING: promotion refuses while this is OPEN.")
        return

    r = con.execute("SELECT * FROM reviews WHERE id=?", (args.id,)).fetchone()
    if r is None:
        die(f"no review finding #{args.id}.")

    if act == 'fix':
        if not (args.resolution or '').strip():
            die("closing a finding needs what HE changed, in his diff. 'fixed'"
                " is the same nothing as 'he seems to get it now'.")
        con.execute("UPDATE reviews SET state='FIXED', resolution=?, fixed_in=?,"
                    " closed_at=? WHERE id=?",
                    (args.resolution.strip(), args.attempt, now(), args.id))
        con.commit()
        print(f"review #{args.id} FIXED: {args.resolution.strip()}")
        return

    if act == 'waive':
        if not (args.resolution or '').strip():
            die("waiving needs the reason it does not apply here. A waiver with"
                " no reason is the finding being deleted because it was"
                " inconvenient.")
        con.execute("UPDATE reviews SET state='WAIVED', resolution=?,"
                    " closed_at=? WHERE id=?",
                    (args.resolution.strip(), now(), args.id))
        con.commit()
        print(f"review #{args.id} WAIVED: {args.resolution.strip()}")
        return


def capstone(args):
    """Open-ended work: no spec file, no right answer, decisions that are HIS."""
    con = connect()
    act = args.action

    if act == 'list':
        rows = con.execute("SELECT * FROM capstones ORDER BY id DESC").fetchall()
        if not rows:
            print("no capstone on record.")
            return
        for r in rows:
            print(f"{r['slug']:<20} {r['state']:<9} by {r['proposed_by']}"
                  f"  {r['title']}")
            print(f"    decisions HE resolves:")
            for d in r['decisions'].splitlines():
                print(f"      - {d}")
            if r['artifact']:
                print(f"    shipped: {r['artifact']}")
        return

    if act == 'propose':
        decisions = [d.strip() for d in (args.decision or []) if d.strip()]
        if len(decisions) < 2:
            die("a capstone needs >=2 --decision forks that the brief does NOT"
                " settle. With none, the requirements determine the program and"
                " you have written a gate with a longer description.")
        if not (args.brief or '').strip():
            die("--brief states what must be TRUE when it works -- inputs,"
                " outputs, what survives a crash. Never how.")
        for d in decisions:
            low = d.lower()
            if low.startswith(('use ', 'write ', 'implement ')):
                die(f"'{d}' is an instruction, not a fork. A decision reads as a"
                    " question with more than one defensible answer.")
        con.execute(
            "INSERT INTO capstones (slug, title, brief, decisions, constraints,"
            " proposed_by, state, opened_at) VALUES (?,?,?,?,?,?,'PROPOSED',?)",
            (args.slug, args.title or args.slug, args.brief.strip(),
             '\n'.join(decisions), args.constraints, args.by, now()))
        con.commit()
        print(f"capstone PROPOSED: {args.slug}  ({len(decisions)} open decisions)")
        print("  You do not resolve these for him. If he asks which to pick, the"
              " answer is the trade-off, not the choice.")
        return

    c = con.execute("SELECT * FROM capstones WHERE slug=?", (args.slug,)).fetchone()
    if c is None:
        die(f"no capstone '{args.slug}'.")

    if act == 'start':
        con.execute("UPDATE capstones SET state='ACTIVE' WHERE id=?", (c['id'],))
        con.commit()
        print(f"capstone ACTIVE: {args.slug}")
        return

    if act == 'ship':
        if not (args.artifact or '').strip():
            die("shipping needs the thing that RUNS -- a path, a command that"
                " works. A description of what it would do is a plan.")
        if not (args.defense or '').strip():
            die("--defense is required: why he chose each fork, in HIS words. A"
                " capstone with no defense measured typing, not design.")
        opn = con.execute("SELECT COUNT(*) FROM reviews WHERE slug=? AND"
                          " state='OPEN' AND severity IN (?,?)",
                          (args.slug,) + BLOCKING).fetchone()[0]
        if opn:
            die(f"{opn} blocking review finding(s) still OPEN on {args.slug}."
                " Ship means it survives the review, not that he stopped editing.")
        con.execute("UPDATE capstones SET state='SHIPPED', shipped_at=?,"
                    " artifact=?, defense=? WHERE id=?",
                    (now(), args.artifact.strip(), args.defense.strip(), c['id']))
        con.commit()
        print(f"capstone SHIPPED: {args.slug} -> {args.artifact.strip()}")
        return


def patterns(args=None):
    """The detector. Prints what an agent must LOOK at before it teaches.

    Everything here is a candidate, never a verdict: the agent still has to read
    the answers and decide. The point is that the candidate cannot go unnoticed
    because a session ran long or an agent forgot to look back.
    """
    con = connect()

    print("=== OPEN MISCONCEPTIONS ===")
    rows = con.execute(
        "SELECT m.*, (SELECT COUNT(*) FROM misconception_hits h"
        "  WHERE h.misconception_id = m.id) n FROM misconceptions m"
        " WHERE m.state='OPEN' ORDER BY n DESC").fetchall()
    if not rows:
        print("  none recorded. If two unrelated misses share a wrong belief,"
              " that is a misconception -- open it, do not narrate it.")
    for r in rows:
        print(f"  {r['slug']:<24} [{r['aspect']}] {r['n']} hit(s)")
        print(f"      believes: {r['belief']}")

    print("\n=== REPEAT MISSES (same concept, 2+ fails) ===")
    rows = con.execute(
        "SELECT c.slug, c.fails, c.attempts FROM concepts c"
        " WHERE c.fails >= 2 ORDER BY c.fails DESC").fetchall()
    if not rows:
        print("  none.")
    for r in rows:
        print(f"  {r['slug']:<24} {r['fails']}/{r['attempts']} failed"
              f"   <- what did NOT change between attempts is the real gap")

    print("\n=== ERROR CLASSES ON MISSES ===")
    rows = con.execute(
        "SELECT COALESCE(error_class,'(none)') k, COUNT(*) n FROM probes"
        " WHERE result != 'HIT' GROUP BY k ORDER BY n DESC").fetchall()
    total = sum(r['n'] for r in rows)
    for r in rows:
        print(f"  {r['k']:<12} {r['n']:>3}")
    if total and rows and rows[0]['n'] == total and total >= 6:
        print(f"  ALL {total} misses carry one class. Either every miss really is"
              f" the same kind,\n  or the class is being filled in reflexively --"
              f" which measures nothing.")

    print("\n=== MEASURED BY ASPECT (categories in the bank) ===")
    rows = con.execute(
        "SELECT c.category,"
        "  COUNT(DISTINCT c.id) total,"
        "  COUNT(DISTINCT CASE WHEN c.parked=0 THEN c.id END) live,"
        "  COUNT(DISTINCT p.concept_id) probed"
        " FROM concepts c LEFT JOIN probes p ON p.concept_id = c.id"
        " GROUP BY c.category ORDER BY probed DESC").fetchall()
    print(f"  {'CATEGORY':<12}{'IN BANK':>9}{'ON LADDER':>11}{'PROBED':>8}")
    for r in rows:
        print(f"  {r['category']:<12}{r['total']:>9}{r['live']:>11}{r['probed']:>8}")
    blind = [r['category'] for r in rows if r['probed'] == 0]
    if blind:
        print(f"  NEVER PROBED: {', '.join(blind)}")
        print("  These are not strengths and not weaknesses. They are unmeasured,"
              "\n  and a profile drawn without saying so is a lie.")

    print("\n=== MEASURED BY FACULTY ===")
    rows = con.execute(
        "SELECT faculty, COUNT(*) n, SUM(result='HIT') hits FROM probes"
        " GROUP BY faculty").fetchall()
    seen = {r['faculty']: r for r in rows}
    for fac in FACULTIES:
        r = seen.get(fac)
        if r:
            print(f"  {fac:<12}{r['hits']:>3}/{r['n']:<4} hit")
        else:
            print(f"  {fac:<12}  never tested")

    print("\n=== REVIEW FINDINGS (the studio record) ===")
    rows = con.execute(
        "SELECT severity, COUNT(*) n, SUM(state='OPEN') open FROM reviews"
        " GROUP BY severity ORDER BY n DESC").fetchall()
    if not rows:
        print("  none. If nothing he wrote has ever drawn a finding, either he"
              " writes\n  flawless code or the review is being skipped.")
    for r in rows:
        print(f"  {r['severity']:<12}{r['n']:>3} total, {r['open']} open")
    rounds = con.execute(
        "SELECT slug, MAX(round) r, COUNT(*) n FROM reviews GROUP BY slug"
        " HAVING r >= 2 ORDER BY r DESC").fetchall()
    for r in rounds:
        print(f"  {r['slug']}: {r['r']} rounds — iteration, which is the point."
              " Compare round 1 findings to round {0}.".format(r['r']))

    print("\n=== STALLS (where he froze, and what it cost) ===")
    rows = con.execute(
        "SELECT kind, COUNT(*) n, SUM(level_n >= 3) charged,"
        " SUM(hyp_state='OPEN') open, SUM(hyp_state='CONFIRMED') ok,"
        " SUM(hyp_state='FALSE') no FROM stalls GROUP BY kind"
        " ORDER BY n DESC").fetchall()
    if not rows:
        print("  none recorded.")
    for r in rows:
        print(f"  {r['kind']:<8}{r['n']:>3} pushes, {r['charged']} charged"
              f"   hypotheses: {r['ok']} confirmed / {r['no']} false /"
              f" {r['open']} untested")
    trend = con.execute(
        "SELECT gate_id, slug, COUNT(*) n, MAX(level_n) top FROM stalls"
        " WHERE gate_id IS NOT NULL GROUP BY gate_id ORDER BY gate_id").fetchall()
    if len(trend) >= 2:
        print("  per gate, oldest first: " +
              '  '.join(f"#{r['gate_id']}:{r['n']}@L{r['top']}" for r in trend))
        print("  This line is the whole point. Pushes per gate must FALL. If it"
              "\n  is flat, he is being carried and the ladder is above his floor.")
    hyp = con.execute("SELECT COUNT(*) n, SUM(hyp_by='learner') selfrep FROM"
                      " stalls WHERE hyp_state='CONFIRMED'").fetchone()
    if hyp['n'] and (hyp['selfrep'] or 0) == hyp['n']:
        print(f"  All {hyp['n']} confirmed hypotheses rest on HIS say-so. Nothing"
              " has been probed.\n  His self-report is a hint; his code is"
              " evidence. Probe one before building on it.")

    print("\n=== LOOKUPS (uncertainty resolved in the open) ===")
    lk = con.execute("SELECT COUNT(*) n, SUM(corrected IS NOT NULL) c"
                     " FROM lookups").fetchone()
    print(f"  {lk['n'] or 0} searched, {lk['c'] or 0} of them corrected something"
          " the agent had already said.")
    if not lk['n']:
        print("  Zero. An agent that is never unsure is modelling a thing that"
              " does not exist,\n  and he is watching it.")


# ---- sight ---------------------------------------------------------------

def profile(args):
    """Per-faculty aggregates. This is the radar's data. It is a shape, not a level."""
    con = connect()
    out = {}
    for fac in FACULTIES:
        rows = con.execute(
            "SELECT p.result, p.seconds, p.clock, c.depth FROM probes p"
            " JOIN concepts c ON c.id = p.concept_id WHERE p.faculty = ?",
            (fac,)).fetchall()
        n = len(rows)
        hits = sum(1 for r in rows if r['result'] == 'HIT')
        # Only a `measured` span says anything about recall. A batch span is a
        # fact about the worksheet, an `away` span is him at lunch, and the 18
        # v1/v2 rows marked `self-reported` are his own estimate, divided.
        secs = [r['seconds'] for r in rows
                if r['seconds'] and r['clock'] == 'measured']
        out[fac] = {
            'attempts': n,
            'hits': hits,
            'hit_rate': round(hits / n, 2) if n else None,
            'timed': len(secs),
            'median_seconds': round(statistics.median(secs)) if secs else None,
            'max_depth': max((r['depth'] for r in rows if r['result'] == 'HIT'),
                             default=0),
        }
    if args.json:
        print(json.dumps(out, indent=2))
        return
    print(f"{'FACULTY':<12}{'ATT':>5}{'HIT':>5}{'RATE':>7}{'TIMED':>7}{'MED s':>7}{'DEPTH':>7}")
    for fac, d in out.items():
        rate = f"{d['hit_rate']:.0%}" if d['hit_rate'] is not None else '-'
        print(f"{fac:<12}{d['attempts']:>5}{d['hits']:>5}{rate:>7}{d['timed']:>7}"
              f"{str(d['median_seconds'] or '-'):>7}{d['max_depth']:>7}")
    if not any(d['timed'] for d in out.values()):
        print("\nMED s is blank because NOTHING has been measured yet -- and that is"
              "\nthe honest reading, not a bug. Open a clock with `ask <slug>` when"
              "\nyou put a question on screen. Never ask him how long he took.")
    untested = [f for f, d in out.items() if d['attempts'] == 0]
    if untested:
        print(f"\nNEVER TESTED: {', '.join(untested)}")
        print("These axes are not zero, they are unmeasured. Do not draw them.")


def velocity(args=None):
    """Probes-per-CAN and calendar rate. 'Short time', with an instrument."""
    con = connect()
    applied = con.execute(
        "SELECT id, slug FROM concepts WHERE state = 'CAN'").fetchall()
    costs = [con.execute("SELECT COUNT(*) FROM probes WHERE concept_id = ?",
                         (c['id'],)).fetchone()[0] for c in applied]
    secs = [r[0] for r in con.execute(
        "SELECT seconds FROM probes WHERE seconds IS NOT NULL")]
    print(f"CAN (owned) concepts: {len(applied)}")
    if costs:
        print(f"probes per CAN: median {statistics.median(costs):.0f},"
              f" max {max(costs)}")
    if secs:
        print(f"median seconds to answer: {statistics.median(secs):.0f}")
    else:
        print("median seconds to answer: unmeasured"
              " (no probe has carried a clock yet)")
    print("newly owned per week:")
    for w in con.execute(
            "SELECT strftime('%Y-%W', updated_at) w, COUNT(*) n FROM concepts"
            " WHERE state = 'CAN' AND updated_at IS NOT NULL"
            " GROUP BY w ORDER BY w"):
        print(f"  {w['w']}: {w['n']:>3} {'#' * w['n']}")


def gaps(args=None):
    """Two different kinds of nothing, told apart."""
    con = connect()
    unswept_code = con.execute(
        "SELECT COUNT(*) FROM concepts WHERE swept_in IS NULL AND parked=0 AND source='code'"
    ).fetchone()[0]
    spine_total = con.execute(
        "SELECT COUNT(*) FROM concepts WHERE source='spine' AND parked=0").fetchone()[0]
    unswept_spine = con.execute(
        "SELECT COUNT(*) FROM concepts WHERE swept_in IS NULL AND parked=0 AND source='spine'"
    ).fetchone()[0]
    print(f"in his code, never asked:   {unswept_code}")
    print(f"in the spine, never asked:  {unswept_spine}"
          f"   <- territory he has never entered")
    if spine_total == 0:
        print("no spine loaded: unknown-unknowns are still invisible."
              " Run `spine-load`.")
    print("by category, never swept:")
    for r in con.execute(
            "SELECT category, source, COUNT(*) n FROM concepts WHERE swept_in IS NULL AND parked = 0"
            " GROUP BY category, source ORDER BY n DESC"):
        print(f"  {r['category']:<10} {r['source']:<6} {r['n']}")


def show_map(args=None):
    """No writes, no teaching."""
    con = connect()
    _position(con)
    frontier = con.execute(
        "SELECT slug FROM concepts WHERE state = 'CANT' AND parked = 0"
        " AND (requires IS NULL OR requires = '') ORDER BY depth LIMIT 6").fetchall()
    print(f"FRONTIER {', '.join(r['slug'] for r in frontier) or '-'}")
    blocking = con.execute(
        "SELECT c.slug, COUNT(o.id) n FROM concepts c"
        " JOIN concepts o ON (',' || o.requires || ',') LIKE ('%,' || c.slug || ',%')"
        " WHERE c.state = 'CANT' AND c.parked = 0 GROUP BY c.slug ORDER BY n DESC LIMIT 5"
    ).fetchall()
    print("BLOCKING " + (', '.join(f"{r['slug']}({r['n']})" for r in blocking) or '-'))
    gaps()
    nxt = con.execute(
        "SELECT slug, name, gate FROM concepts WHERE state = 'CANT' AND parked = 0"
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
    added = skipped = parked_n = 0
    with open(args.csv, newline='', encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            slug = row['slug'].strip()
            if not slug:
                continue
            depth = int(row['depth'])
            parked = 1 if depth >= 3 else 0
            if con.execute("SELECT 1 FROM concepts WHERE slug = ?",
                           (slug,)).fetchone():
                skipped += 1
                continue
            con.execute(
                "INSERT INTO concepts (slug, name, definition, category, depth,"
                " requires, gate, source, state, evidence, parked, updated_at)"
                " VALUES (?,?,?,?,?,?,?,'spine','CANT','none',?,?)",
                (slug, row['name'].strip(), row['definition'].strip(),
                 row['category'].strip(), depth,
                 row.get('requires', '').strip(), row.get('gate', '').strip(),
                 parked, now()))
            added += 1
            parked_n += parked
    con.commit()
    print(f"spine: {added} added ({added - parked_n} on the ladder, {parked_n} parked"
          f" at depth 3+), {skipped} already in the bank from his own code")


def concepts_load(args):
    """Phase 1 output: concepts extracted from HIS OWN code, with where they live.

    Same merge-by-slug rule as spine-load — a slug already in the bank keeps its
    history and is never overwritten. Depth 3+ inserts parked=1: off the routing
    ladder, kept as a checklist on the file being rebuilt (v2 rule).
    """
    con = connect()
    added = skipped = parked_n = 0
    with open(args.csv, newline='', encoding='utf-8') as fh:
        for row in csv.DictReader(fh):
            slug = row['slug'].strip()
            if not slug:
                continue
            if con.execute("SELECT 1 FROM concepts WHERE slug = ?",
                           (slug,)).fetchone():
                skipped += 1
                continue
            depth = int(row['depth'])
            parked = 1 if depth >= 3 else 0
            parked_n += parked
            con.execute(
                "INSERT INTO concepts (slug, name, definition, category, depth,"
                " file, line, snippet, requires, gate, source, state, evidence,"
                " parked, swept_in, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,'code','CANT','none',?,NULL,?)",
                (slug, row['name'].strip(), row['definition'].strip(),
                 row['category'].strip(), depth,
                 row.get('file', '').strip() or None,
                 int(row['line']) if row.get('line', '').strip() else None,
                 row.get('snippet', '').strip() or None,
                 row.get('requires', '').strip(), row.get('gate', '').strip(),
                 parked, now()))
            added += 1
    con.commit()
    print(f"concepts: {added} added ({added - parked_n} on the ladder, "
          f"{parked_n} parked at depth 3+), {skipped} already in the bank")


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


# ---- v3 circle: target (the anchor as data) + the unlock gate ------------

def target(args):
    """INTAKE writes the anchor here; every later phase reads it. The target and
    its codebase are DATA, so a different repo needs zero code change."""
    con = connect()
    if args.target_cmd == 'show':
        rows = con.execute(
            "SELECT id, learner, name, codebase_path, phase, unlock_gate, size "
            "FROM targets WHERE phase != 'retired' ORDER BY id").fetchall()
        if not rows:
            print("no target yet. run INTAKE: `target set ...`")
            return
        for r in rows:
            print(f"#{r['id']} [{r['learner']}] {r['name']}  ({r['size']})")
            print(f"    codebase: {r['codebase_path']}")
            print(f"    phase: {r['phase']}   unlock-gate: {r['unlock_gate']}")
        return
    if args.target_cmd == 'set':
        if not args.name or not args.learner:
            die("a target needs --learner and --name; the anchor is not optional.")
        if not args.additional:
            con.execute("UPDATE targets SET phase='retired' "
                        "WHERE learner=? AND phase!='retired'", (args.learner,))
        con.execute(
            "INSERT INTO targets (learner, name, codebase_path, inputs, outputs,"
            " size, scripts, phase, unlock_gate, created_at) "
            "VALUES (?,?,?,?,?,?,?, 'SCAN', 'open', ?)",
            (args.learner, args.name, args.codebase, args.inputs, args.outputs,
             args.size, args.scripts, now()))
        con.commit()
        tid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        print(f"target #{tid} set: {args.name}")
        print(f"  read it back to him in one sentence and let him correct it.")
        print(f"  next: SCAN {args.codebase or '<codebase>'} (do not teach in SCAN)")
        return
    die("target: use `set` or `show`")


def unlock_gate(args):
    """The hard gate between the ladder (UNLOCK) and the pillar (BIG BUILD).
    Refuses to open BUILD while any non-parked ladder concept is still CANT."""
    con = connect()
    row = con.execute("SELECT id, name, phase FROM targets WHERE id=?",
                      (args.target_id,)).fetchone()
    if not row:
        die(f"no target #{args.target_id}")
    remaining = con.execute(
        "SELECT verb, COUNT(*) n FROM concepts "
        "WHERE state='CANT' AND parked=0 AND verb IS NOT NULL "
        "GROUP BY verb ORDER BY n DESC").fetchall()
    total = sum(r['n'] for r in remaining)
    if total:
        print(f"GATE CLOSED for #{args.target_id} ({row['name']}): "
              f"{total} ladder concept(s) still CANT. BIG BUILD stays locked.")
        for r in remaining:
            print(f"  {r['verb'] or '?':<12} {r['n']}")
        print("  unlock these first (parked depth-3+ concepts do NOT block; "
              "they return JIT during the build).")
        return
    con.execute("UPDATE targets SET phase='BUILD', unlock_gate='closed', "
                "updated_at=? WHERE id=?", (now(), args.target_id))
    con.commit()
    print(f"GATE OPEN: #{args.target_id} ({row['name']}) -> BIG BUILD.")
    print("  the ladder is unlocked. now the real scripts, by hand, through the "
          "9-verb circle.")


# ---- cli -----------------------------------------------------------------

# ---- v2: attempts, phases, assumptions -----------------------------------

PROJECT = HERE.parent.parent            # .claude/tutor -> .claude -> project
# Overridable so the test harness never writes into a real project tree.
ATTEMPTS = Path(os.environ.get('TUTOR_ATTEMPTS_DIR', PROJECT / 'attempts'))
PHASE_DIR = {'FLOOR': '01_floor', 'READ': '02_read',
             'BUILD_V1': '03_build_v1', 'BUILD_V2': '04_build_v2'}


def _sha(b):
    import hashlib
    return hashlib.sha256(b).hexdigest()[:16]


def attempt(args):
    """Snapshot what he wrote, before grading it. He edits one file; the archive
    is the agent's job, never his.

    v1 graded `log.md` in place and it was overwritten ~21 times -- 252 bytes
    survived six days of work. The diff between attempt 1 and attempt 4 IS the
    learning, and v1 destroyed it every time.
    """
    if args.phase not in LEARNER_PHASES:
        die(f"attempt phase must be one of {LEARNER_PHASES}, got '{args.phase}'")
    srcs = [Path(s) for s in args.src]
    for s in srcs:
        if not s.exists():
            die(f"no such file: {s}")

    con = connect()
    sid = current_session(con)
    cid = None
    row = con.execute("SELECT id FROM concepts WHERE slug = ?", (args.slug,)).fetchone()
    if row:
        cid = row['id']

    prev = con.execute(
        "SELECT * FROM attempts WHERE phase = ? AND slug = ? ORDER BY n DESC LIMIT 1",
        (args.phase, args.slug)).fetchone()
    n = (prev['n'] + 1) if prev else 1

    dest_dir = ATTEMPTS / PHASE_DIR[args.phase]
    dest_dir.mkdir(parents=True, exist_ok=True)

    if len(srcs) == 1:
        stored = dest_dir / f"{args.slug}_{n:02d}{srcs[0].suffix}"
        payload = srcs[0].read_bytes()
        stored.write_bytes(payload)
        text = payload.decode('utf-8', 'replace')
    else:
        stored = dest_dir / f"{args.slug}_{n:02d}"
        stored.mkdir(exist_ok=True)
        chunks = []
        for s in srcs:
            (stored / s.name).write_bytes(s.read_bytes())
            chunks.append(f"--- {s.name} ---\n" +
                          s.read_text(encoding='utf-8', errors='replace'))
        text = "\n".join(chunks)
        payload = text.encode()

    # The clock, by subtraction. Attempt 1 is timed from the moment the gate
    # opened -- that IS "blank file to saved", and it is why the agent must
    # never ask him how long test.py took. Later attempts are timed from the
    # previous snapshot.
    diff_text, added, removed, secs = None, None, None, None
    clock_from = None
    if not prev and cid:
        g = con.execute(
            "SELECT opened_at FROM gates WHERE concept_id = ? AND closed_at IS NULL"
            " ORDER BY id DESC LIMIT 1", (cid,)).fetchone()
        if g:
            secs = int((datetime.now() -
                        datetime.fromisoformat(g['opened_at'])).total_seconds())
            clock_from = 'the gate opening (blank file -> saved)'
    if prev:
        import difflib
        old_path = Path(prev['stored_path'])
        if old_path.is_dir():
            old = "\n".join(f"--- {p.name} ---\n" +
                            p.read_text(encoding='utf-8', errors='replace')
                            for p in sorted(old_path.iterdir()))
        else:
            old = old_path.read_text(encoding='utf-8', errors='replace')
        d = list(difflib.unified_diff(old.splitlines(), text.splitlines(),
                                      f"{args.slug}_{prev['n']:02d}",
                                      f"{args.slug}_{n:02d}", lineterm='', n=2))
        diff_text = "\n".join(d)
        added = sum(1 for l in d if l.startswith('+') and not l.startswith('+++'))
        removed = sum(1 for l in d if l.startswith('-') and not l.startswith('---'))
        secs = int((datetime.now() -
                    datetime.fromisoformat(prev['taken_at'])).total_seconds())

    con.execute(
        "INSERT INTO attempts (session_id, concept_id, phase, slug, n, src_path,"
        " stored_path, sha, bytes, lines, diff_prev, added, removed, seconds, taken_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, cid, args.phase, args.slug, n, ','.join(str(s) for s in srcs),
         str(stored), _sha(payload), len(payload), text.count('\n') + 1,
         diff_text, added, removed, secs, now()))
    con.commit()

    try:
        shown = stored.relative_to(PROJECT)
    except ValueError:
        shown = stored
    print(f"attempt {args.slug} #{n:02d} -> {shown}"
          f"  {text.count(chr(10)) + 1} lines")
    if prev:
        mins = f"{secs // 60}m" if secs and secs >= 60 else f"{secs}s"
        print(f"  vs #{prev['n']:02d}: +{added} -{removed} lines, {mins} apart")
        print("  GRADE THE DIFF, not just the file. What changed is what he learned;"
              " what did not change twice is the real gap.")
        if diff_text:
            print("--- diff ---")
            print(diff_text)
    else:
        print("  first attempt at this slug -- nothing to diff against yet.")
        if secs is not None:
            print(f"  {secs // 60}m {secs % 60}s, timed from {clock_from}."
                  f" Nobody was asked for that number.")


def attempt_log(args):
    """The portfolio. Getting shorter and faster is the evidence of confidence."""
    con = connect()
    q = "SELECT * FROM attempts"
    p = ()
    if args.slug:
        q += " WHERE slug = ?"
        p = (args.slug,)
    q += " ORDER BY phase, slug, n"
    rows = con.execute(q, p).fetchall()
    if not rows:
        print("no attempts recorded yet.")
        return
    print(f"{'phase':<9} {'slug':<20} {'#':>2} {'lines':>5} {'+':>4} {'-':>4} "
          f"{'gap':>6} {'result':<8} path")
    for r in rows:
        gap = ''
        if r['seconds'] is not None:
            gap = f"{r['seconds'] // 60}m" if r['seconds'] >= 60 else f"{r['seconds']}s"
        print(f"{r['phase']:<9} {r['slug']:<20} {r['n']:>2} {r['lines']:>5} "
              f"{(r['added'] if r['added'] is not None else ''):>4} "
              f"{(r['removed'] if r['removed'] is not None else ''):>4} {gap:>6} "
              f"{r['result'] or '-':<8} {Path(r['stored_path']).name}")


def attempt_grade(args):
    """Attach the verdict to the stored artifact, so the folder tells the story."""
    if args.result not in RESULTS:
        die(f"result must be one of {RESULTS}")
    con = connect()
    row = con.execute(
        "SELECT id, n FROM attempts WHERE phase = ? AND slug = ? ORDER BY n DESC LIMIT 1",
        (args.phase, args.slug)).fetchone()
    if row is None:
        die(f"no attempt stored for {args.phase}/{args.slug}. Snapshot it first.")
    con.execute("UPDATE attempts SET result = ? WHERE id = ?", (args.result, row['id']))
    con.commit()
    print(f"attempt {args.slug} #{row['n']:02d} graded {args.result}")


def phase(args):
    """The learner's only routing decision, and he makes it four times.

    v1 asked him which CONCEPT was next at six separate session-ends. He cannot
    see the map; asking him to navigate it was asking the wrong question.
    """
    con = connect()
    cur = con.execute("SELECT value FROM meta WHERE key = 'phase'").fetchone()
    if not args.set:
        print(f"phase {cur['value'] if cur else 'FLOOR'}")
        print(f"  order: {' -> '.join(LEARNER_PHASES)}")
        print("  inside a phase the agent picks every rung. He is never asked "
              "'which concept next?'")
        return
    if args.set not in LEARNER_PHASES:
        die(f"phase must be one of {LEARNER_PHASES}")
    old = cur['value'] if cur else 'FLOOR'
    con.execute("UPDATE meta SET value = ? WHERE key = 'phase'", (args.set,))
    con.execute(
        "INSERT INTO ladder_log (ts, trigger, evidence, change) VALUES (?,?,?,?)",
        (now(), 'LADDER', args.why or 'learner chose the phase transition',
         f"phase {old} -> {args.set}"))
    con.commit()
    print(f"phase {old} -> {args.set} (logged)")


def assume(args):
    """State the prerequisites before teaching, so they can be vetoed.

    All three v1 ladder repairs trace to an unstated assumption. The third only
    surfaced because the learner asked 'what does opening even look like -- you
    didn't detect them, why is that??'. That should not require him to notice.
    """
    con = connect()
    sid = current_session(con)
    if args.veto:
        row = con.execute(
            "SELECT id, teaching, assumed FROM assumptions WHERE session_id = ?"
            " ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
        if row is None:
            die("nothing assumed this session to veto.")
        con.execute("UPDATE assumptions SET vetoed = ? WHERE id = ?",
                    (args.veto, row['id']))
        con.execute(
            "INSERT INTO ladder_log (ts, trigger, evidence, change) VALUES (?,?,?,?)",
            (now(), 'BLIND_SPOT',
             f"assumed {row['assumed']} before teaching {row['teaching']};"
             f" learner vetoed: {args.veto}",
             f"teach {args.veto} first; {row['teaching']} deferred"))
        con.commit()
        print(f"VETOED: {args.veto}. Teach that first. BLIND_SPOT logged -- this is "
              f"the machine being wrong, not him.")
        return
    if not args.teaching or not args.assumed:
        die("usage: assume --teaching <slug> --assumed a,b,c   |   assume --veto <slug>")
    con.execute(
        "INSERT INTO assumptions (session_id, teaching, assumed, declared_at)"
        " VALUES (?,?,?,?)", (sid, args.teaching, args.assumed, now()))
    con.commit()
    print(f"declared: to teach '{args.teaching}' I am assuming he owns "
          f"[{args.assumed}].")
    print("Say this to him in one line and invite the veto BEFORE teaching.")


def due_slice(args=None):
    """What is going stale, so a build slice can be chosen that USES it.

    v1 reviewed by date, in isolation, disconnected from the work -- so review
    felt like an interruption and decayed again. One 12-line script (test.py)
    exercised seven concepts for free. Reviews belong inside the build.
    """
    con = connect()
    rows = con.execute(
        "SELECT slug, name, state, next_review, depth FROM concepts"
        " WHERE parked = 0 AND next_review IS NOT NULL AND next_review <= date('now','+2 day')"
        " ORDER BY next_review, depth").fetchall()
    if not rows:
        print("nothing due or nearly due.")
        return
    print(f"DUE OR NEARLY DUE ({len(rows)}):")
    for r in rows:
        print(f"  [{r['depth']}] {r['slug']:<24} {r['state']:<5} {r['next_review']}")
    print()
    print("Do NOT drill these in isolation. Choose the next slice of the real target "
          "file that USES as many of them as possible, and have him write that.")
    print("Every review then lands as progress on the project instead of a quiz.")


# ---- what he can see -----------------------------------------------------
#
# v1 performed `map` at him: 8,259 characters, 7% of the lab, zero learning.
# v2 deleted it and left him with nothing -- so on 2026-08-05 he ran four hours
# and 25% of everything he typed was "i(m waiting" / "where i cn find those??".
# Both are the same mistake: position as a MESSAGE. Position is furniture.
# `tree` writes a file he keeps open; `statusline` is one line always on screen.
# Neither is ever pasted into a reply.

PROGRESS_MD = HERE / 'PROGRESS.md'      # next to the db, so a sandbox gets its own


def _bar(done, total, width=24, fill='#', empty='.'):
    if not total:
        return empty * width
    n = int(round(width * done / total))
    return fill * n + empty * (width - n)


def _tree_lines(con):
    """The live map, as text. Same body for the file and the terminal."""
    L = []
    ph = con.execute("SELECT value FROM meta WHERE key='phase'").fetchone()
    ph = ph['value'] if ph else 'FLOOR'
    rows = con.execute(
        "SELECT slug, name, state, depth, attempts, fails, swept_in, next_review"
        " FROM concepts WHERE parked = 0 ORDER BY depth, slug").fetchall()
    parked = con.execute("SELECT COUNT(*) FROM concepts WHERE parked=1").fetchone()[0]
    total = len(rows)
    can = sum(1 for r in rows if r['state'] == 'CAN')
    touched = [r for r in rows if r['attempts'] or r['swept_in']]
    gates = con.execute(
        "SELECT g.id, g.kind, g.target, c.slug FROM gates g"
        " JOIN concepts c ON c.id = g.concept_id"
        " WHERE g.closed_at IS NULL ORDER BY g.id").fetchall()
    floors = con.execute(
        "SELECT c.slug, f.explains, f.descents, f.found_at FROM floors f"
        " JOIN concepts c ON c.id = f.concept_id ORDER BY f.id DESC").fetchall()
    snaps = con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]

    L.append("YOU ARE HERE")
    L.append("")
    for p in LEARNER_PHASES:
        mark = '>>' if p == ph else '  '
        note = {'FLOOR': 'own the language (toys ok)',
                'READ': 'predict what the real file does',
                'BUILD_V1': 'write it with the contract in front of you',
                'BUILD_V2': 'write it from memory  <-- THE GOAL',
                'CAPSTONE': 'no spec exists; the forks are yours'}[p]
        L.append(f" {mark} {p:<9} {note}")
    L.append("")
    L.append(f"    owned   [{_bar(can, total)}] {can}/{total}")
    L.append(f"    seen    [{_bar(len(touched), total)}] {len(touched)}/{total} "
             f"probed at least once")
    if parked:
        L.append(f"    parked  {parked} concepts at depth 3+ "
                 f"(off the ladder on purpose, not lost)")
    L.append("")

    if gates:
        L.append("OPEN GATE  -- this is yours to write. Nothing moves until it closes.")
        for g in gates:
            n = con.execute("SELECT COUNT(*) FROM attempts a JOIN concepts c"
                            " ON c.id=a.concept_id WHERE c.slug=?",
                            (g['slug'],)).fetchone()[0]
            L.append(f"    #{g['id']} {g['kind']} {g['slug']}  ->  {g['target']}")
            L.append(f"        attempts archived: {n}"
                     + ("   <-- nothing saved yet" if not n else ""))
        L.append("")

    if floors:
        L.append("THE THREAD YOU ARE ON")
        f = floors[0]
        L.append(f"    floor: {f['slug']}  (found after {f['descents']} descents,"
                 f" {f['found_at'][:10]})")
        chain = [s for s in (f['explains'] or '').split(',') if s]
        for i, s in enumerate(chain):
            row = con.execute("SELECT state FROM concepts WHERE slug=?", (s,)).fetchone()
            edge = '`--' if i == len(chain) - 1 else '|--'
            L.append(f"      {edge} {s:<22} {row['state'] if row else '?'}"
                     f"   (this floor explains it)")
        L.append("")

    L.append("THE LADDER")
    for d in sorted({r['depth'] for r in rows}):
        band = [r for r in rows if r['depth'] == d]
        dcan = sum(1 for r in band if r['state'] == 'CAN')
        L.append(f"  depth {d}  [{_bar(dcan, len(band), 18)}] {dcan}/{len(band)}")
        for r in band:
            if r['state'] == 'CAN':
                g = '[x]'
            elif r['fails']:
                g = '[!]'
            elif r['attempts'] or r['swept_in']:
                g = '[-]'
            else:
                g = '[ ]'
            tail = ''
            if r['fails']:
                tail = f"  {r['fails']}/{r['attempts']} missed"
            elif r['attempts']:
                tail = f"  {r['attempts']} probe(s)"
            L.append(f"      {g} {r['slug']:<26}{tail}".rstrip())
        L.append("")
    L.append("  [x] you own it   [!] probed and missed   [-] probed   [ ] untouched")
    L.append("")
    L.append(f"attempts archived so far: {snaps}"
             + ("   <-- the diff between your versions is the learning."
                " Zero means none of it was kept." if not snaps else ""))
    return L


def tree(args=None):
    """Live progress map. Written to a FILE he keeps open, never pasted at him."""
    con = connect()
    lines = _tree_lines(con)
    body = ("# PROGRESS -- regenerated by `tutor_db.py tree`, never edited by hand\n"
            f"# {now()}\n\n```\n" + '\n'.join(lines) + "\n```\n")
    PROGRESS_MD.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_MD.write_text(body, encoding='utf-8')
    if getattr(args, 'quiet', False):
        print(f"wrote {PROGRESS_MD}")
        return
    print('\n'.join(lines))
    print(f"\n(also written to {PROGRESS_MD} -- keep that file open in a tab)")


def statusline(args=None):
    """One line, always on screen, zero tokens. Read-only and fast.

    Claude Code hands us session JSON on stdin; we ignore it. Any failure prints
    nothing rather than breaking his prompt.
    """
    try:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        ph = con.execute("SELECT value FROM meta WHERE key='phase'").fetchone()
        ph = ph['value'] if ph else 'FLOOR'
        tot = con.execute("SELECT COUNT(*) FROM concepts WHERE parked=0").fetchone()[0]
        can = con.execute(
            "SELECT COUNT(*) FROM concepts WHERE parked=0 AND state='CAN'").fetchone()[0]
        due = con.execute(
            "SELECT COUNT(*) FROM concepts WHERE parked=0"
            " AND next_review <= date('now')").fetchone()[0]
        g = con.execute(
            "SELECT g.id, g.target, c.slug, "
            " (SELECT COUNT(*) FROM attempts a WHERE a.concept_id=g.concept_id) n,"
            " (SELECT COUNT(*) FROM stalls s WHERE s.gate_id=g.id) pushes,"
            " (SELECT MAX(level_n) FROM stalls s WHERE s.gate_id=g.id) top"
            " FROM gates g JOIN concepts c ON c.id=g.concept_id"
            " WHERE g.closed_at IS NULL ORDER BY g.id LIMIT 1").fetchone()
        con.close()
    except Exception:
        return
    if not tot:
        print("TUTOR  bank EMPTY -- run /tutor concepts <dir>")
        return
    i = LEARNER_PHASES.index(ph) if ph in LEARNER_PHASES else 0
    dots = ''.join('#' if k <= i else '.' for k in range(len(LEARNER_PHASES)))
    out = f"TUTOR {dots} {ph} | {can}/{tot} owned"
    if due:
        out += f" | {due} due"
    if g:
        # an open gate with nothing archived is the loudest thing here: on
        # 2026-08-05 gate #1 sat open for hours and `attempt snap` never ran.
        saved = f"({g['n']} saved)" if g['n'] else "NOTHING SAVED"
        out += f" | GATE#{g['id']} {g['slug']}->{g['target']} {saved}"
        # The cost of a push, visible to him while he is still writing.
        if g['pushes']:
            out += f" | pushes {g['pushes']} (max L{g['top']})"
            if (g['top'] or 0) >= 3:
                out += " CHARGED"
    print(out)


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
    sub.add_parser('bucket-show', help='show active discovery chains (project-scoped)')
    sub.add_parser('bucket-archive', help='archive completed bucket to database')
    s = sub.add_parser('sweep-next')
    s.add_argument('n', nargs='?', default=12)

    sub.add_parser('route-next', help='smart next concept: verb coverage + due + sweep')

    s = sub.add_parser('probe')
    s.add_argument('slug')
    s.add_argument('phase')
    s.add_argument('faculty')
    s.add_argument('result')
    s.add_argument('--question', '-q', default='')
    s.add_argument('--answer', '-a', default='')
    s.add_argument('--below', type=int, default=0)
    s.add_argument('--error-class', dest='error_class', default=None,
                   choices=ERROR_CLASSES)
    # --seconds is deliberately still parsed, and deliberately refused. Removing
    # it would make an agent that types it get a confusing argparse error; this
    # way it gets the rule.
    s.add_argument('--seconds', type=int, default=None, help=argparse.SUPPRESS)

    s = sub.add_parser('ask', help='start the clock; run it as the question goes on screen')
    s.add_argument('slugs', help='one slug, or comma-separated for one worksheet')
    s.add_argument('--phase', default=None)
    s.add_argument('--faculty', default=None)

    s = sub.add_parser('floor')
    s.add_argument('slug')
    s.add_argument('--explains', default='')
    s.add_argument('--descents', type=int, default=1)

    s = sub.add_parser('teach-open')
    s.add_argument('slug')
    s = sub.add_parser('teach-close')
    s.add_argument('slug')
    s.add_argument('--explanation-file', required=True)

    sub.add_parser('teach-suggest', help='show concepts that need teaching (gap detection)')

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
    s.add_argument('state', choices=STATES)
    s.add_argument('--evidence', default='unaided')
    s.add_argument('--copy-checked', dest='copy_checked', action='store_true',
                   help="you compared his submission against your own last two "
                        "messages and it is not a reproduction of your example")
    s = sub.add_parser('demote')
    s.add_argument('slug')
    s.add_argument('--reason', default='')
    s.add_argument('--error-class', dest='error_class', default=None,
                   choices=ERROR_CLASSES)

    s = sub.add_parser('revise')
    s.add_argument('--trigger', required=True)
    s.add_argument('--evidence', required=True)
    s.add_argument('--change', required=True)

    s = sub.add_parser('misconception',
                       help='a false belief that crosses unrelated concepts')
    s.add_argument('action', choices=('open', 'hit', 'survived', 'retire', 'list'))
    s.add_argument('slug', nargs='?')
    s.add_argument('--name', default='')
    s.add_argument('--belief', default='')
    s.add_argument('--correction', default='')
    s.add_argument('--aspect', default='language')
    s.add_argument('--seen-in', dest='seen_in', default='',
                   help='comma-separated concept slugs: 2+ required to open')
    s.add_argument('--concept', default=None, help='slug this hit surfaced under')
    s.add_argument('--note', default='', help='what he actually wrote')
    s.add_argument('--evidence', default='')

    sub.add_parser('patterns',
                   help='cross-concept signatures an agent must look at before teaching')

    s = sub.add_parser('push',
                       help='a metered nudge into his file when he freezes')
    s.add_argument('action', choices=('give', 'list', 'interview', 'verdict'))
    s.add_argument('id', nargs='?', type=int, help='stall id, for verdict')
    s.add_argument('--level', default='RESTATE', choices=LEVELS,
                   help='; '.join(f'{k}={v}' for k, v in LEVEL_HELP.items()))
    s.add_argument('--kind', default=None,
                   help='blank|form|recall|commit — what the freeze IS')
    s.add_argument('--hypothesis', default='',
                   help='what hole this freeze suggests. required.')
    s.add_argument('--text', default='', help='what goes in his file (L3+)')
    s.add_argument('--anchor', type=int, default=None, help='insert before this line')
    s.add_argument('--confirmed', action='store_true')
    s.add_argument('--false', dest='false_', action='store_true')
    s.add_argument('--by', default='probe', help='probe|learner')
    s.add_argument('--evidence', default='')

    s = sub.add_parser('lookup',
                       help='an uncertainty you resolved by SEARCHING, in front of him')
    s.add_argument('action', choices=('add', 'list'))
    s.add_argument('--claim', default='', help='what you were unsure of, as a question')
    s.add_argument('--strategy', default='', help='why THIS source, before you read it')
    s.add_argument('--source', default='', help='url / doc path / man page you read')
    s.add_argument('--found', default='', help='what the source actually says')
    s.add_argument('--corrected', default='',
                   help='the FALSE sentence you had already said, quoted')
    s.add_argument('--concept', default=None)

    s = sub.add_parser('review', help='studio code review: findings, fixes, rounds')
    s.add_argument('action', choices=('add', 'fix', 'waive', 'list'))
    s.add_argument('id', nargs='?', type=int, help='finding id, for fix/waive')
    s.add_argument('--slug', default=None)
    s.add_argument('--attempt', type=int, default=None)
    s.add_argument('--round', type=int, default=None)
    s.add_argument('--file', default=None)
    s.add_argument('--line', type=int, default=None)
    s.add_argument('--severity', default='clarity', choices=SEVERITIES)
    s.add_argument('--finding', default='',
                   help='the concrete failure WITH the input that causes it')
    s.add_argument('--resolution', default='', help='what HE changed, or why waived')
    s.add_argument('--open', dest='open_only', action='store_true')

    s = sub.add_parser('capstone', help='open-ended work with no spec to diff against')
    s.add_argument('action', choices=('propose', 'start', 'ship', 'list'))
    s.add_argument('slug', nargs='?')
    s.add_argument('--title', default=None)
    s.add_argument('--brief', default='', help='what must be TRUE when it works')
    s.add_argument('--decision', action='append', default=[],
                   help='a fork the brief does NOT settle; repeat, 2+ required')
    s.add_argument('--constraints', default=None)
    s.add_argument('--by', default='agent', choices=('learner', 'agent'))
    s.add_argument('--artifact', default='', help='the thing that RUNS')
    s.add_argument('--defense', default='', help='why he chose each fork, HIS words')

    s = sub.add_parser('profile')
    s.add_argument('--json', action='store_true')
    sub.add_parser('velocity')
    sub.add_parser('gaps')
    sub.add_parser('map')
    s = sub.add_parser('tree', help='live progress map -> PROGRESS.md (a file, not a message)')
    s.add_argument('--quiet', action='store_true',
                   help='write the file, print nothing but the path')
    sub.add_parser('statusline', help='one line for the Claude Code status bar')

    s = sub.add_parser('spine-load')
    s.add_argument('csv')

    s = sub.add_parser('concepts-load',
                       help='phase 1: load concepts mined from his own code')
    s.add_argument('csv')

    s = sub.add_parser('learner')
    s.add_argument('action', choices=('add', 'use', 'show'))
    s.add_argument('name', nargs='?')
    s.add_argument('rules_file', nargs='?')

    # ---- v2 ----------------------------------------------------------------
    a = sub.add_parser('attempt').add_subparsers(dest='attempt_cmd')
    an = a.add_parser('snap', help='copy what he wrote, diff it, before grading')
    an.add_argument('phase', choices=LEARNER_PHASES)
    an.add_argument('slug')
    an.add_argument('--src', action='append', required=True,
                    help='the file he edits; repeat for multi-file work')
    al = a.add_parser('log', help='the portfolio: every version, shorter and faster')
    al.add_argument('slug', nargs='?')
    ag = a.add_parser('grade')
    ag.add_argument('phase', choices=LEARNER_PHASES)
    ag.add_argument('slug')
    ag.add_argument('result', choices=RESULTS)

    s = sub.add_parser('phase', help='the learner chooses this, four times, ever')
    s.add_argument('--set', choices=LEARNER_PHASES, default=None)
    s.add_argument('--why', default='')

    s = sub.add_parser('assume', help='declare prerequisites so they can be vetoed')
    s.add_argument('--teaching', default=None)
    s.add_argument('--assumed', default=None)
    s.add_argument('--veto', default=None)

    sub.add_parser('due-slice', help='what is stale, to be reviewed INSIDE a build')

    # v3 circle
    t = sub.add_parser('target', help='the anchor as data (INTAKE writes it)')
    tsub = t.add_subparsers(dest='target_cmd')
    ts = tsub.add_parser('set')
    ts.add_argument('--learner', required=True)
    ts.add_argument('--name', required=True)
    ts.add_argument('--codebase', default=None)
    ts.add_argument('--inputs', default=None)
    ts.add_argument('--outputs', default=None)
    ts.add_argument('--size', default=None)
    ts.add_argument('--scripts', default=None)
    ts.add_argument('--additional', action='store_true',
                    help='keep prior targets (several scripts under one goal)')
    tsub.add_parser('show')
    ug = sub.add_parser('unlock-gate',
                        help='open BIG BUILD only when the ladder is fully unlocked')
    ug.add_argument('target_id', type=int)
    return p


DISPATCH = {
    'init': lambda a: init(),
    'session': lambda a: session(a.agent, a.note),
    'brief': lambda a: brief(),
    'status': lambda a: status(),
    'bucket-show': lambda a: bucket_show(),
    'bucket-archive': lambda a: bucket_archive(),
    'sweep-next': lambda a: sweep_next(a.n),
    'route-next': lambda a: route_next(),
    'probe': probe,
    'floor': floor,
    'teach-open': teach_open,
    'teach-close': teach_close,
    'teach-suggest': lambda a: teach_suggest(),
    'gate': lambda a: {'open': gate_open, 'close': gate_close,
                       'list': gate_list}[a.gate_cmd](a),
    'promote': promote,
    'demote': demote,
    'revise': revise,
    'misconception': misconception,
    'patterns': patterns,
    'push': push,
    'lookup': lookup,
    'review': review,
    'capstone': capstone,
    'profile': profile,
    'velocity': lambda a: velocity(),
    'gaps': lambda a: gaps(),
    'map': lambda a: show_map(),
    'tree': tree,
    'statusline': statusline,

    'spine-load': spine_load,
    'concepts-load': concepts_load,
    'learner': learner,
    'attempt': lambda a: {'snap': attempt, 'log': attempt_log,
                          'grade': attempt_grade}[a.attempt_cmd](a),
    'phase': phase,
    'assume': assume,
    'due-slice': lambda a: due_slice(),
    'ask': ask,
    'target': target,
    'unlock-gate': unlock_gate,
}

# Commands that change state. After each one PROGRESS.md is rewritten.
WRITES = ('probe', 'floor', 'promote', 'demote', 'revise', 'phase', 'assume', 'ask',
          'gate', 'attempt', 'spine-load', 'concepts-load', 'teach-open',
          'teach-close', 'session', 'learner', 'review', 'capstone', 'lookup',
          'push', 'target', 'unlock-gate')


def main():
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] or ['status'])
    if args.cmd not in DISPATCH:
        parser.print_help()
        return
    DISPATCH[args.cmd](args)
    # Keep PROGRESS.md live without anyone remembering to. A map he has to ask
    # for is a map he does not have -- that is how four hours produced
    # "where i cn find those please ??".
    if args.cmd in WRITES:
        try:
            tree(argparse.Namespace(quiet=True))
        except Exception:
            pass                        # never let the map break a real write


if __name__ == '__main__':
    main()
