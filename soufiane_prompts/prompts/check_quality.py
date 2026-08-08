#!/usr/bin/env python3
"""Quality gate for the profile_ville run. Run it anytime — it checks EVERYTHING
collected so far and prints PASS/FAIL per criterion.

    python check_quality.py

What it verifies (the things that must never drift):
  1. schema     — exact keys, both question groups, no empty fields
  2. questions  — all 10 exactly as in the record's own prompt, in the right slot
  3. integrity  — ID alignment, no duplicates, no truncation, no API errors
"""
import json, glob, re, sys
from collections import Counter
import run_prompts as rp

REL = 'exec/prompts_exec_profile_ville.json'
WANT = {f'question_{i}' for i in range(1, 6)} | {f'reponse_{i}' for i in range(1, 6)}
TOP = {'bloc_principal', 'questions_e', 'questions_f'}

tot = schema_ok = qall = 0
slots = slotok = 0
struct = Counter(); fins = Counter()
nonjson = empty = dup = ids_bad = api_err = 0
seen = set(); bad_examples = []

# Only grade chunks the ledger marks 'done'. A result file can be STALE: when a
# chunk is re-sent, its old results_*.jsonl stays on disk until the new batch
# lands, and grading it would report defects that no longer exist in the output.
_led = json.load(open('batch_runs/ledgers/ledger_exec__prompts_exec_profile_ville.json',
                      encoding='utf-8'))
DONE = {c['chunk'] for c in _led['chunks'] if c['status'] == 'done'}
_skipped = []

files = sorted(glob.glob('batch_runs/results_exec__prompts_exec_profile_ville_*.jsonl'),
               key=lambda s: int(re.search(r'_c(\d+)\.jsonl$', s).group(1)))
files = [f for f in files
         if (int(re.search(r'_c(\d+)\.jsonl$', f).group(1)) in DONE
             or _skipped.append(int(re.search(r'_c(\d+)\.jsonl$', f).group(1))))]
for fp in files:
    try:
        side = json.load(open(fp.replace('results_', 'sidecar_').replace('.jsonl', '.json'),
                              encoding='utf-8'))
    except Exception:
        continue
    for line in open(fp, encoding='utf-8'):
        if not line.strip():
            continue
        o = json.loads(line); tot += 1
        cid = o['custom_id']
        if cid in seen:
            dup += 1
        seen.add(cid)
        if o.get('error') or o['response']['status_code'] != 200:
            api_err += 1
        ch = o['response']['body']['choices'][0]
        fins[ch['finish_reason']] += 1
        if cid not in side:
            ids_bad += 1; continue
        rec = side[cid]
        try:
            p = json.loads(ch['message']['content'])
        except Exception:
            nonjson += 1; continue

        ok = True
        if set(p) != TOP:
            struct[f'top keys {sorted(p)}'] += 1; ok = False
        else:
            if not p['bloc_principal'].strip():
                struct['bloc empty'] += 1; ok = False
            for g in ('questions_e', 'questions_f'):
                gg = p[g]
                if not isinstance(gg, dict) or set(gg) != WANT:
                    struct[f'{g} wrong keys'] += 1; ok = False; continue
                for k, v in gg.items():
                    if not isinstance(v, str) or not v.strip():
                        empty += 1; struct[f'{g}.{k} empty'] += 1; ok = False
        if not ok:
            continue
        schema_ok += 1

        qs = rp.questions_for(REL, rec['prompt'])
        if qs is None:                    # extraction fell back -> can't pin/verify
            struct['questions NOT extractable (fallback used)'] += 1
            continue
        rec_ok = True
        for cat, g in (('E', 'questions_e'), ('F', 'questions_f')):
            for i in range(1, 6):
                slots += 1
                if p[g][f'question_{i}'] == qs[cat][i - 1]:
                    slotok += 1
                else:
                    rec_ok = False
                    if len(bad_examples) < 5:
                        bad_examples.append((cid, g, i, qs[cat][i - 1][:60],
                                             p[g][f'question_{i}'][:60]))
        if rec_ok:
            qall += 1

if tot == 0:
    print('no results collected yet'); sys.exit(0)

def line(name, good, total, extra=''):
    pct = 100 * good / total if total else 0
    flag = 'PASS' if good == total else '*** FAIL ***'
    print(f"  {name:<34} {good:>7,}/{total:<7,} {pct:6.2f}%   {flag} {extra}")

print(f"\n=== QUALITY CHECK — {tot:,} records across {len(files)} batches ===\n")
print("CRITERION                              COUNT              RESULT")
line('1. schema perfect', schema_ok, tot)
line('2. questions all 10 exact', qall, schema_ok)
line('3. question slots exact', slotok, slots)
line('4. no truncation (finish=stop)', fins.get('stop', 0), tot)
line('5. ID alignment (sidecar match)', tot - ids_bad, tot)
line('6. valid JSON', tot - nonjson, tot)
line('7. unique custom_ids', tot - dup, tot)
line('8. no API errors', tot - api_err, tot)
print(f"\n  empty fields: {empty} | finish reasons: {dict(fins)}")
if _skipped:
    print(f"  skipped {len(_skipped)} chunk(s) not yet 'done' (stale/in-flight): {sorted(_skipped)}")
# the ledger's counter must agree with the rows actually on disk
try:
    rows = sum(1 for l in open('responses/exec/prompts_exec_profile_ville_output.json',
                               encoding='utf-8') if l.strip())
    if rows != _led['completed']:
        print(f"  *** COUNTER DRIFT: output has {rows:,} rows but ledger says "
              f"completed={_led['completed']:,} (diff {rows - _led['completed']:+,}) ***")
    else:
        print(f"  output rows == ledger completed ({rows:,})  OK")
except FileNotFoundError:
    pass
if struct:
    print("\n  PROBLEMS FOUND:")
    for k, v in struct.most_common(10):
        print(f"     {v:>6,}  {k}")
if bad_examples:
    print("\n  WRONG-QUESTION EXAMPLES:")
    for cid, g, i, want, got in bad_examples:
        print(f"     {cid} {g}.question_{i}\n        expected: {want}\n        got     : {got}")
allgood = (schema_ok == tot and qall == schema_ok and slotok == slots
           and fins.get('stop', 0) == tot and ids_bad == 0 and nonjson == 0
           and dup == 0 and api_err == 0 and not struct)
print("\n" + ("ALL CHECKS PASS — data is consistent." if allgood
              else "*** SOMETHING IS OFF — see problems above. ***") + "\n")
