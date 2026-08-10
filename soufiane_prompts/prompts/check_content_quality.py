#!/usr/bin/env python3
"""Content-level quality gate for exec/pays_ville_exec.

Unlike a schema check (which only verifies the JSON *shape*), this compares the
ACTUAL question text in each response against the questions written in that
record's own prompt. pays_ville_exec is NOT a lettered/pinned file, so the model
was free to paraphrase or invent questions even when the schema was strict --
this is the only way to catch that.

For every output record it decides one verdict:
  ok            - valid nested schema AND all 10 questions match the prompt, in slot
  schema        - JSON missing/extra keys, not parseable, or empty field
  qmismatch     - schema fine, but >=1 question differs from the prompt
  unmatched     - could not find this record's prompt in the source file
  no_questions  - prompt did not contain exactly 10 '❖ Question:' lines (can't verify)

Writes the union of everything-not-ok to a DEFECTIVE file with the source index
(so it can be regenerated) and the exact slot(s) that differ.

    python check_content_quality.py                       # full run, main output
    python check_content_quality.py --limit 5000          # only first N output rows (quick)
    python check_content_quality.py --out responses/exec/pays_ville_exec_output.SPLICED.json

Root cause note: response is stored as a JSON *string*; we json.loads it.
"""
import json, sys, hashlib, collections, argparse

_ap = argparse.ArgumentParser()
_ap.add_argument('--out', default='responses/exec/pays_ville_exec_output.json',
                 help='output file to grade (default: main pays_ville_exec output)')
_ap.add_argument('--src', default='exec/pays_ville_exec.json',
                 help='source file with the prompts to compare against')
_ap.add_argument('--limit', type=int, default=None,
                 help='only check the first N output rows (quick sanity run)')
# tolerate a bare positional number for backward compat: `... 5000`
_argv = sys.argv[1:]
if len(_argv) == 1 and _argv[0].isdigit():
    _argv = ['--limit', _argv[0]]
_args = _ap.parse_args(_argv)

SRC = _args.src
OUT = _args.out
DST = OUT.replace('.json', '') + '_CONTENT_DEFECTIVE_ids.jsonl'
EXP = {f'question_{i}' for i in range(1, 6)} | {f'reponse_{i}' for i in range(1, 6)}
LIMIT = _args.limit

import re
Q = re.compile(r'❖ Question:\s*(.+)')


def norm(s):
    """Normalize a question for comparison.

    The SOURCE prompts over-escape apostrophes in city names (e.g. "M\\'Sila",
    "N\\'Djamena"); the model correctly emits "M'Sila". That is a source-data
    artifact, NOT a wrong question, so we strip stray backslashes before comparing.
    Also collapse whitespace so trivial spacing never counts as a mismatch.
    """
    s = str(s).replace('\\', '')
    return ' '.join(s.split()).strip()


def prompt_questions(prompt):
    """The 10 questions from a prompt, normalized. None if not exactly 10."""
    qs = [norm(m) for m in Q.findall(prompt)]
    return qs if len(qs) == 10 else None


def key_of(rec):
    return (rec.get('type'), rec.get('job_id'), rec.get('country_id'), rec.get('region_id'))


def stream_array(path):
    """Yield (index, record) from a top-level JSON array, streaming (never load whole)."""
    dec = json.JSONDecoder()
    buf = ''
    started = False
    i = 0
    with open(path, encoding='utf-8') as f:
        while True:
            if not started:
                while '[' not in buf:
                    c = f.read(65536)
                    if not c:
                        return
                    buf += c
                buf = buf[buf.index('[') + 1:]
                started = True
            buf = buf.lstrip()
            while buf[:1] == ',':
                buf = buf[1:].lstrip()
            if buf[:1] == ']':
                return
            try:
                rec, idx = dec.raw_decode(buf)
            except json.JSONDecodeError:
                c = f.read(65536)
                if not c:
                    return
                buf += c
                continue
            buf = buf[idx:]
            yield i, rec
            i += 1


# ---- Pass 1: source -> key -> (index, questions-hash) ---------------------
print('pass 1: indexing source prompts ...', flush=True)
src = {}          # key -> (index, qhash)
src_q_example = {} # key -> questions list, kept ONLY for a capped set (for examples)
collisions = 0
no_q_src = 0
for i, rec in stream_array(SRC):
    k = key_of(rec)
    qs = prompt_questions(rec.get('prompt', ''))
    if qs is None:
        no_q_src += 1
        qh = None
    else:
        qh = hashlib.md5('\n'.join(qs).encode('utf-8')).hexdigest()
    if k in src:
        collisions += 1
    src[k] = (i, qh, qs if len(src_q_example) < 40 else None)
    if len(src_q_example) < 40 and qs is not None:
        src_q_example[k] = qs
print(f'  source records indexed: {len(src):,} | key collisions: {collisions} | '
      f'prompts without exactly 10 Qs: {no_q_src}', flush=True)


# ---- Pass 2: output -> verdict per record --------------------------------
print('pass 2: checking output responses ...', flush=True)
verdict = collections.Counter()
defects = []            # dicts to write
examples = []           # (key, slot, prompt_q, resp_q) for display
n = 0
for line_no, line in enumerate(open(OUT, encoding='utf-8')):
    if LIMIT and n >= LIMIT:
        break
    if not line.strip():
        continue
    n += 1
    r = json.loads(line)
    k = key_of(r)
    src_hit = src.get(k)

    # ---- schema check ----
    reason = None
    resp_qs = None
    resp = r.get('response')
    try:
        o = json.loads(resp) if isinstance(resp, str) else resp
    except Exception:
        reason = 'schema'
    if reason is None:
        if not (isinstance(o, dict) and set(o.keys()) == {'bloc_principal', 'questions'}
                and o['bloc_principal'].strip()):
            reason = 'schema'
        else:
            q = o['questions']
            if not (isinstance(q, dict) and set(q.keys()) == {'questions_e', 'questions_f'}):
                reason = 'schema'
            else:
                resp_qs = []
                for g in ('questions_e', 'questions_f'):
                    gg = q[g]
                    if not (isinstance(gg, dict) and set(gg.keys()) == EXP):
                        reason = 'schema'
                        break
                    if any(not str(gg[kk]).strip() for kk in gg):
                        reason = 'schema'
                        break
                    resp_qs += [norm(gg[f'question_{i}']) for i in range(1, 6)]

    # ---- content check (only if schema fine) ----
    diff_slots = []
    if reason is None:
        if src_hit is None:
            reason = 'unmatched'
        elif src_hit[1] is None:
            reason = 'no_questions'
        else:
            resp_hash = hashlib.md5('\n'.join(resp_qs).encode('utf-8')).hexdigest()
            if resp_hash != src_hit[1]:
                reason = 'qmismatch'
                # find which slots differ (need source questions)
                sqs = src_q_example.get(k)
                for idx in range(10):
                    if sqs is not None and idx < len(sqs):
                        if resp_qs[idx] != sqs[idx]:
                            diff_slots.append(idx + 1)
                            if len(examples) < 8:
                                examples.append((k, idx + 1, sqs[idx], resp_qs[idx]))
                    else:
                        diff_slots.append(idx + 1)

    verdict[reason or 'ok'] += 1
    if reason:
        idx = src_hit[0] if src_hit else None
        defects.append({'record_index': idx, 'reason': reason,
                        'diff_slots': diff_slots or None,
                        'type': r.get('type'), 'job_id': r.get('job_id'),
                        'job_name': r.get('job_name'), 'job_category': r.get('job_category'),
                        'country_id': r.get('country_id'), 'country_name': r.get('country_name'),
                        'region_id': r.get('region_id'), 'region_name': r.get('region_name')})

# ---- report --------------------------------------------------------------
print(f'\n=== CONTENT QUALITY — {n:,} output records ===\n')
for k in ('ok', 'schema', 'qmismatch', 'unmatched', 'no_questions'):
    v = verdict.get(k, 0)
    print(f'  {k:<14} {v:>9,}  ({100*v/n:5.2f}%)')
bad = n - verdict.get('ok', 0)
print(f'\n  TOTAL not-ok: {bad:,} ({100*bad/n:.2f}%)')

if examples:
    print('\n  QUESTION-MISMATCH EXAMPLES (prompt vs response):')
    for k, slot, pq, rq in examples:
        print(f'   {k} slot {slot}\n     prompt: {pq[:80]}\n     resp  : {rq[:80]}')

defects.sort(key=lambda d: (d['record_index'] is None, d['record_index']))
with open(DST, 'w', encoding='utf-8') as fh:
    fh.write(json.dumps({'_comment': 'Content-defective records: schema bad OR question text '
                         'differs from the prompt. Regenerate record_index and splice by '
                         '(type,job_id,country_id,region_id).',
                         '_count': len(defects),
                         '_verdict': dict(verdict)}, ensure_ascii=False) + '\n')
    for d in defects:
        fh.write(json.dumps(d, ensure_ascii=False) + '\n')
print(f'\n  wrote {DST}  ({len(defects):,} records)')
