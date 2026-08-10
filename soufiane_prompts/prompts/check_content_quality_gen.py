#!/usr/bin/env python3
"""Schema-agnostic content-quality check.

Works for ANY of the exec/marche files: it uses run_prompts' own question
extractor (lettered ❖ Question E1 / plain ❖ Question:) to know what each record's
prompt asked, and auto-detects whether the response schema is FLAT
({bloc_principal, questions_e, questions_f}) or NESTED
({bloc_principal, questions:{questions_e, questions_f}}).

Verdicts per record:
  ok            schema fine AND all 10 questions == prompt, in slot
  schema        missing/extra keys, unparseable, or empty field
  qmismatch     schema fine but >=1 question differs from the prompt
  unmatched     record's prompt not found in the source
  no_questions  prompt didn't yield exactly 10 extractable questions

    python check_content_quality_gen.py --src exec/prompts_exec_profile_ville.json \
        --out responses/exec/prompts_exec_profile_ville_output.json
    python check_content_quality_gen.py --src ... --out ... --limit 5000
"""
import json, sys, hashlib, collections, argparse
import run_prompts as rp

ap = argparse.ArgumentParser()
ap.add_argument('--src', required=True, help='source file with the prompts')
ap.add_argument('--out', required=True, help='output file to grade')
ap.add_argument('--limit', type=int, default=None)
args = ap.parse_args()

SRC, OUT = args.src, args.out
DST = OUT.replace('.json', '') + '_CONTENT_DEFECTIVE_ids.jsonl'
REL = SRC.replace('\\', '/')          # key run_prompts uses for extraction
EXP = {f'question_{i}' for i in range(1, 6)} | {f'reponse_{i}' for i in range(1, 6)}


def norm(s):
    return ' '.join(str(s).replace('\\', '').split()).strip()


def key_of(r):
    return (r.get('type'), r.get('job_id'), r.get('country_id'), r.get('region_id'))


def stream_array(path):
    dec = json.JSONDecoder(); buf = ''; started = False; i = 0
    with open(path, encoding='utf-8') as f:
        while True:
            if not started:
                while '[' not in buf:
                    c = f.read(65536)
                    if not c: return
                    buf += c
                buf = buf[buf.index('[') + 1:]; started = True
            buf = buf.lstrip()
            while buf[:1] == ',': buf = buf[1:].lstrip()
            if buf[:1] == ']': return
            try:
                rec, idx = dec.raw_decode(buf)
            except json.JSONDecodeError:
                c = f.read(65536)
                if not c: return
                buf += c; continue
            buf = buf[idx:]
            yield i, rec; i += 1


def prompt_qs(prompt):
    """The 10 questions run_prompts would pin, normalized. None if not extractable."""
    qs = rp.questions_for(REL, prompt)
    if qs is None:
        return None
    flat = [norm(x) for x in qs['E']] + [norm(x) for x in qs['F']]
    return flat if len(flat) == 10 and all(flat) else None


def resp_groups(o):
    """Return (questions_e_dict, questions_f_dict) for flat OR nested; None if neither."""
    if not isinstance(o, dict) or not o.get('bloc_principal', '').strip():
        return None
    if set(o.keys()) == {'bloc_principal', 'questions_e', 'questions_f'}:
        return o['questions_e'], o['questions_f']
    if set(o.keys()) == {'bloc_principal', 'questions'} and isinstance(o['questions'], dict) \
            and set(o['questions'].keys()) == {'questions_e', 'questions_f'}:
        return o['questions']['questions_e'], o['questions']['questions_f']
    return None


# ---- Pass 1: index source ----
print('pass 1: indexing source prompts ...', flush=True)
src = {}; no_q = 0; coll = 0; kept_examples = 0
for i, rec in stream_array(SRC):
    k = key_of(rec)
    qs = prompt_qs(rec.get('prompt', ''))
    if qs is None: no_q += 1
    if k in src: coll += 1
    keep = None
    if qs and kept_examples < 40:
        keep = qs; kept_examples += 1
    src[k] = (i, hashlib.md5('\n'.join(qs).encode()).hexdigest() if qs else None, keep)
print(f'  indexed {len(src):,} | collisions {coll} | prompts w/o 10 Qs {no_q}', flush=True)

# ---- Pass 2: grade output ----
print('pass 2: checking output ...', flush=True)
verdict = collections.Counter(); defects = []; examples = []; n = 0
for line in open(OUT, encoding='utf-8'):
    if args.limit and n >= args.limit: break
    if not line.strip(): continue
    n += 1
    r = json.loads(line)
    k = key_of(r); hit = src.get(k)
    reason = None; rq = None
    resp = r.get('response')
    try:
        o = json.loads(resp) if isinstance(resp, str) else resp
    except Exception:
        reason = 'schema'
    if reason is None:
        g = resp_groups(o)
        if g is None:
            reason = 'schema'
        else:
            ge, gf = g
            if not (isinstance(ge, dict) and set(ge) == EXP and isinstance(gf, dict) and set(gf) == EXP):
                reason = 'schema'
            elif any(not str(ge[x]).strip() or not str(gf[x]).strip() for x in EXP):
                reason = 'schema'
            else:
                rq = [norm(ge[f'question_{i}']) for i in range(1, 6)] + \
                     [norm(gf[f'question_{i}']) for i in range(1, 6)]
    if reason is None:
        if hit is None: reason = 'unmatched'
        elif hit[1] is None: reason = 'no_questions'
        elif hashlib.md5('\n'.join(rq).encode()).hexdigest() != hit[1]:
            reason = 'qmismatch'
            sqs = hit[2]
            if sqs and len(examples) < 8:
                for j in range(10):
                    if rq[j] != sqs[j]:
                        examples.append((k, j + 1, sqs[j], rq[j])); break
    verdict[reason or 'ok'] += 1
    if reason:
        defects.append({'record_index': hit[0] if hit else None, 'reason': reason,
                        'type': r.get('type'), 'job_id': r.get('job_id'),
                        'country_id': r.get('country_id'), 'country_name': r.get('country_name'),
                        'region_id': r.get('region_id'), 'region_name': r.get('region_name')})

print(f'\n=== CONTENT QUALITY — {n:,} output records ===\n')
for k in ('ok', 'schema', 'qmismatch', 'unmatched', 'no_questions'):
    v = verdict.get(k, 0)
    print(f'  {k:<14} {v:>9,}  ({100*v/n:5.2f}%)')
print(f'\n  TOTAL not-ok: {n - verdict.get("ok",0):,}')
if examples:
    print('\n  MISMATCH EXAMPLES (prompt vs response):')
    for k, slot, pq, rq in examples:
        print(f'   {k} slot {slot}\n     prompt: {pq[:80]}\n     resp  : {rq[:80]}')
defects.sort(key=lambda d: (d['record_index'] is None, d['record_index']))
with open(DST, 'w', encoding='utf-8') as fh:
    fh.write(json.dumps({'_count': len(defects), '_verdict': dict(verdict)}, ensure_ascii=False) + '\n')
    for d in defects: fh.write(json.dumps(d, ensure_ascii=False) + '\n')
print(f'\n  wrote {DST}  ({len(defects):,} records)')
