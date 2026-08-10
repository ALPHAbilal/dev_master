#!/usr/bin/env python3
"""Build FR->EN translation source files from the generated French content.

Each generated record looks like

    {type, job_id, job_name, ..., response: "<french JSON as a string>"}

and this writes, for every one of them,

    {type, job_id, job_name, ..., prompt: "Job title: <fr title>\\n\\n<french JSON>"}

into translate_src/<same relative path>.json  (a top-level JSON array, which is
what run_prompts' loader streams).

Why this shape: run_prompts replaces `prompt` with `response` in place and keeps
every other key untouched. So after the translation run each output record is the
ORIGINAL metadata plus an English `response` in exactly the French structure --
ids are copied by the pipeline and never sent to the model at all.

The job title is included purely as context so the model translates the same role
consistently within a page. It is passed through in FRENCH, exactly as stored.
Files with no job (the marche country/city pages) simply get the JSON alone.

    python build_translation_sources.py            # all five files
    python build_translation_sources.py --limit 50 # small files for a test run
"""
import json
import argparse
from pathlib import Path

BASE = Path(__file__).resolve().parent

# (french output file, translation source file to write)
PAIRS = [
    ('responses/exec/pays_ville_exec_output.json',
     'translate_src/exec/pays_ville_exec.json'),
    ('responses/exec/prompts_exec_profile_ville_output.json',
     'translate_src/exec/prompts_exec_profile_ville.json'),
    ('responses/marche/prompts_type1_pays_marche_output.json',
     'translate_src/marche/prompts_type1_pays_marche.json'),
    ('responses/marche/prompts_type2_pays_ville_marche_output.json',
     'translate_src/marche/prompts_type2_pays_ville_marche.json'),
    ('responses/marche/prompts_type3_pays_ville_presentation_output.json',
     'translate_src/marche/prompts_type3_pays_ville_presentation.json'),
]

ap = argparse.ArgumentParser()
ap.add_argument('--limit', type=int, default=None,
                help='only take the first N records of each file (test runs)')
args = ap.parse_args()


def build(src_rel, dst_rel, limit):
    src, dst = BASE / src_rel, BASE / dst_rel
    if not src.exists():
        print(f'  ! missing, skipped: {src_rel}')
        return 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(src, encoding='utf-8') as fin, open(dst, 'w', encoding='utf-8') as fout:
        fout.write('[\n')
        first = True
        for line in fin:
            if limit and n >= limit:
                break
            if not line.strip():
                continue
            rec = json.loads(line)
            french = rec.pop('response')          # the text to translate
            title = rec.get('job_name')
            rec['prompt'] = (f'Job title: {title}\n\n{french}' if title else french)
            if not first:
                fout.write(',\n')
            fout.write(json.dumps(rec, ensure_ascii=False))
            first = False
            n += 1
        fout.write('\n]\n')
    print(f'  {dst_rel:<58} {n:>9,} records')
    return n


print('building translation sources'
      + (f' (limit {args.limit}/file)' if args.limit else '') + ' ...')
total = sum(build(s, d, args.limit) for s, d in PAIRS)
print(f'\ntotal: {total:,} records ready to translate')
