#!/usr/bin/env python3
"""Write a random sample of FR->EN translations to a readable .txt for review.

Pairs every sampled record's French source with its English translation, field by
field, so the two can be read side by side without opening the huge JSON files.

    python sample_translations.py                     # 100 from pays_ville_exec
    python sample_translations.py --n 50
    python sample_translations.py --file marche/prompts_type1_pays_marche
    python sample_translations.py --file exec/prompts_exec_profile_ville --n 100

Output lands in samples/<name>_sample.txt
"""
import json
import random
import argparse
from pathlib import Path

BASE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument('--file', default='exec/pays_ville_exec',
                help='relative name without _output.json, e.g. marche/prompts_type1_pays_marche')
ap.add_argument('--n', type=int, default=100, help='how many records to sample (max)')
ap.add_argument('--seed', type=int, default=None, help='fix the seed for a reproducible sample')
args = ap.parse_args()

FR_PATH = BASE / 'responses' / f'{args.file}_output.json'
EN_PATH = BASE / 'translations' / f'{args.file}_output.json'
OUT = BASE / 'samples' / f"{args.file.replace('/', '__')}_sample.txt"
OUT.parent.mkdir(parents=True, exist_ok=True)

for p in (FR_PATH, EN_PATH):
    if not p.exists():
        raise SystemExit(f'missing: {p}')


def key(r):
    return (r.get('type'), r.get('job_id'), r.get('country_id'), r.get('region_id'))


def fields(o):
    """[(label, text), ...] for flat, nested or bloc-only responses."""
    out = [('bloc_principal', o.get('bloc_principal', ''))]
    if 'questions_e' in o:
        groups = [('E', o['questions_e']), ('F', o['questions_f'])]
    elif isinstance(o.get('questions'), dict):
        groups = [('E', o['questions']['questions_e']), ('F', o['questions']['questions_f'])]
    else:
        groups = []
    for tag, g in groups:
        for i in range(1, 6):
            out.append((f'{tag}{i} question', g[f'question_{i}']))
            out.append((f'{tag}{i} answer',   g[f'reponse_{i}']))
    return out


# ---- pick the sample from the ENGLISH side (it is the shorter/partial file) ----
if args.seed is not None:
    random.seed(args.seed)
print('reading translations ...')
en_recs = []
with open(EN_PATH, encoding='utf-8') as f:
    for line in f:
        if line.strip():
            en_recs.append(line)
n = min(args.n, len(en_recs))
picked = random.sample(en_recs, n)
EN = {}
for line in picked:
    r = json.loads(line)
    EN[key(r)] = r
print(f'  {len(en_recs):,} translated records available -> sampling {n}')

# ---- pull the matching French records in one streaming pass ----
print('matching French sources ...')
FR = {}
with open(FR_PATH, encoding='utf-8') as f:
    for line in f:
        if not line.strip():
            continue
        r = json.loads(line)
        k = key(r)
        if k in EN and k not in FR:
            FR[k] = r
            if len(FR) == len(EN):
                break
print(f'  matched {len(FR)}/{len(EN)}')

# ---- write the review file ----
with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write(f'TRANSLATION SAMPLE - {args.file}\n')
    fh.write(f'{n} random records | French source vs English translation\n')
    fh.write('=' * 100 + '\n')
    for i, (k, en) in enumerate(EN.items(), 1):
        fr = FR.get(k)
        if fr is None:
            continue
        meta = ' | '.join(f'{x}={en.get(x)}' for x in
                          ('type', 'job_id', 'job_name', 'country_name', 'region_name')
                          if en.get(x) is not None)
        fh.write(f'\n\n{"#" * 100}\n# RECORD {i}/{n}   {meta}\n{"#" * 100}\n')
        fo, eo = json.loads(fr['response']), json.loads(en['response'])
        for (lbl, ftxt), (_, etxt) in zip(fields(fo), fields(eo)):
            fw, ew = len(ftxt.split()), len(etxt.split())
            fh.write(f'\n--- {lbl}   [FR {fw}w -> EN {ew}w]\n')
            fh.write(f'FR: {ftxt}\n')
            fh.write(f'EN: {etxt}\n')
print(f'\nwrote {OUT.relative_to(BASE)}')
