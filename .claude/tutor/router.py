#!/usr/bin/env python3
"""Deterministic context router for the tutor.

The registry (bucket keys, form questions, gap types, angles) lives in the DB.
This module seeds it and computes, from current state, the exact slice the
agent needs THIS turn: which questions to answer, which keys exist for it,
and the next teaching move. Pure code — same state in, same slice out.
"""
import json

GAP_TYPES = [
    ('model', "doesn't know what the thing IS or what it produces"),
    ('reason', "knows what it does, not WHY it is built this way"),
    ('application', "knows what/why, not WHEN to reach for it"),
    ('tradeoff', "doesn't see the cost/benefit against the alternatives"),
]

ANGLES = [
    ('mechanical', "what it does: inputs, outputs, observable behavior — run it, show it", 1),
    ('practical', "where the REAL codebase uses it and what breaks without it", 2),
    ('reasoning', "why this choice: trade-offs, alternatives, when NOT to use it", 3),
]

FORM_QUESTIONS = [
    ('assess-hole',
     "Does the learner's latest answer reveal a hole — explicit ('I don't know') "
     "or implicit (their words show a wrong model)?",
     'none,explicit,implicit', '{"always": true}', 1),
    ('assess-gap',
     "If a hole: which gap type is it? (required with --gap when --hole != none)",
     'model,reason,application,tradeoff', '{"always": true}', 2),
    ('assess-demonstrated',
     "If no hole: did he DEMONSTRATE it (correct prediction/production) or just "
     "claim it? A claim is a hint, not evidence.",
     'demonstrated,claimed', '{"always": true}', 3),
    ('assess-angle-result',
     "Which angle were you teaching, and what result did this answer show for it?",
     'pass,partial,fail', '{"current_angle": true}', 4),
    ('assess-misconception',
     "Does this answer resurface a known OPEN misconception? If yes, also run: "
     "misconception hit <slug>.",
     None, '{"open_misconceptions_min": 1}', 5),
]

BUCKET_KEYS = [
    ('primary_concept', "slug of the concept the bucket is resolving", 'string',
     '{"always": true}'),
    ('chain', "discovery chain: [{concept, name, blocked_by, status}] — status is "
     "needs_teaching|teaching|passed", 'array', '{"always": true}'),
    ('status', "bucket lifecycle: in_progress|ready_archive|archived", 'string',
     '{"always": true}'),
    ('context.gaps', "concept_context/<slug>/gaps.json: [{gap, evidence, status "
     "open|closed, opened_at, closed_at}] — open a gap ONLY via `assess`, close "
     "ONLY via `assess --close-gap` after a probe proves it is gone", 'array',
     '{"has_context": true}'),
    ('context.angles', "concept_context/<slug>/angles.json: [{angle, result, ts}] "
     "— one row per teaching pass; latest row per angle is its current result",
     'array', '{"has_context": true}'),
    ('context.log', "concept_context/<slug>/log.json: [{ts, event, detail}] — the "
     "temporary teaching memory for this concept; wiped to passed_context/ on pass",
     'array', '{"has_context": true}'),
]


def seed_registry(conn):
    """Idempotent: INSERT OR REPLACE every registry row."""
    conn.executemany(
        "INSERT OR REPLACE INTO gap_types(slug, description) VALUES (?,?)", GAP_TYPES)
    conn.executemany(
        "INSERT OR REPLACE INTO angles(slug, description, ord) VALUES (?,?,?)", ANGLES)
    conn.executemany(
        "INSERT OR REPLACE INTO form_questions(slug, question, answers, applies_when, ord) "
        "VALUES (?,?,?,?,?)", FORM_QUESTIONS)
    conn.executemany(
        "INSERT OR REPLACE INTO bucket_keys(name, description, value_type, applies_when) "
        "VALUES (?,?,?,?)", BUCKET_KEYS)
    conn.commit()


# ---- condition evaluator ----------------------------------------------------
# AND semantics: every field present in the condition must hold in the state.
# Unknown condition fields fail closed (return False) so a typo in a seed row
# hides a key instead of spraying it into every turn.

_CHECKS = {
    'always': lambda v, s: bool(v),
    'phase_in': lambda v, s: s.get('phase') in v,
    'has_context': lambda v, s: s.get('has_context', False) == v,
    'open_gaps_min': lambda v, s: len(s.get('open_gaps', [])) >= v,
    'open_misconceptions_min': lambda v, s: s.get('open_misconceptions', 0) >= v,
    'current_angle': lambda v, s: bool(s.get('current_angle')) == v,
    'angles_unexplored_min': lambda v, s: v <= sum(
        1 for a, _ in s.get('_angle_order', []) if a not in s.get('angle_results', {})),
}


def matches(cond: dict, state: dict) -> bool:
    for field, want in cond.items():
        check = _CHECKS.get(field)
        if check is None or not check(want, state):
            return False
    return True


def load_registry(conn) -> dict:
    return {
        'questions': [
            {'slug': r[0], 'question': r[1], 'answers': r[2],
             'applies_when': json.loads(r[3])}
            for r in conn.execute(
                "SELECT slug, question, answers, applies_when FROM form_questions "
                "ORDER BY ord")],
        'keys': [
            {'name': r[0], 'description': r[1], 'value_type': r[2],
             'applies_when': json.loads(r[3])}
            for r in conn.execute(
                "SELECT name, description, value_type, applies_when FROM bucket_keys")],
        'gap_types': {r[0]: r[1] for r in
                      conn.execute("SELECT slug, description FROM gap_types")},
        'angles': [(r[0], r[1]) for r in
                   conn.execute("SELECT slug, description FROM angles ORDER BY ord")],
    }


def _next_move(state, registry) -> str:
    slug = state.get('slug')
    angle_order = registry['angles']
    results = state.get('angle_results', {})
    if not slug:
        return ("no active concept in the bucket — nothing to teach. "
                "Resolve the bucket chain first (bucket-show).")
    if not state.get('has_context'):
        first = angle_order[0][0] if angle_order else 'mechanical'
        return (f"no teaching context for '{slug}' yet — it is created by your "
                f"first `assess`. Teach angle '{first}' ({dict(angle_order).get(first, '')}) "
                f"and assess his next answer.")
    gaps = state.get('open_gaps', [])
    unexplored = [a for a, _ in angle_order if a not in results]
    failed = [a for a, _ in angle_order if results.get(a) in ('fail', 'partial')]
    if gaps:
        g = gaps[0]
        desc = registry['gap_types'].get(g, '')
        via = state.get('current_angle') or (unexplored[0] if unexplored
                                             else angle_order[0][0])
        return (f"gap '{g}' is OPEN ({desc}). Teach it via angle '{via}', then "
                f"probe with a test that would FAIL if the gap persists. Close it "
                f"with: assess {slug} --close-gap {g} --evidence \"<what he did>\".")
    if unexplored:
        a = unexplored[0]
        return (f"angle '{a}' not yet explored — teach it: "
                f"{dict(angle_order).get(a, '')}. Log the result on your next assess "
                f"with --angle {a} --angle-result pass|partial|fail.")
    if failed:
        a = failed[0]
        return (f"angle '{a}' last resulted '{results[a]}' — re-teach it from a "
                f"different example in the real code, then re-assess with "
                f"--angle {a}.")
    return (f"all angles pass and no open gaps — run: concept-pass {slug}. "
            f"Context relocates to passed_context/ and the chain advances.")


def compute_slice(state: dict, registry: dict) -> dict:
    state = dict(state, _angle_order=registry['angles'])
    questions = [q for q in registry['questions']
                 if matches(q['applies_when'], state)]
    keys = [k for k in registry['keys'] if matches(k['applies_when'], state)]
    results = state.get('angle_results', {})
    summary = (f"phase={state.get('phase')} concept={state.get('slug')} | "
               f"open_gaps={state.get('open_gaps', [])} | "
               f"angles={{{', '.join(f'{a}:{r}' for a, r in results.items()) or '-'}}}")
    return {'questions': questions, 'keys': keys,
            'next_move': _next_move(state, registry), 'summary': summary}


def render_slice(s: dict) -> str:
    lines = ["== TURN BRIEF (computed — this is your working context) ==",
             s['summary'], "",
             "ANSWER THIS FORM about the learner's latest answer (via `assess`):"]
    for q in s['questions']:
        ans = f"  [{q['answers']}]" if q['answers'] else ''
        lines.append(f"  {q['slug']}: {q['question']}{ans}")
    lines.append("")
    lines.append("KEYS you may touch right now (nothing else exists for you):")
    for k in s['keys']:
        lines.append(f"  {k['name']} ({k['value_type']}): {k['description']}")
    lines.append("")
    lines.append(f"NEXT MOVE: {s['next_move']}")
    return '\n'.join(lines)
