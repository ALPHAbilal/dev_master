#!/usr/bin/env python3
"""Splice regenerated records back into the main pays_ville_exec output.

Matches by (type, job_id, country_id, region_id) — NOT by line position, because
the output file is not in source order. For every regenerated record:
  - if its key already exists in the main output -> REPLACE that line
  - if not (the 113 that were missing)          -> APPEND it

Writes a NEW file (pays_ville_exec_output.SPLICED.json) and leaves the original
untouched, so nothing is overwritten until you verify and swap it yourself.

    python splice_regen.py
"""
import json, collections

MAIN  = 'responses/exec/pays_ville_exec_output.json'
REGEN = 'responses/exec/pays_ville_exec_REGEN_output.json'
DST   = 'responses/exec/pays_ville_exec_output.SPLICED.json'


def key_of(r):
    return (r.get('type'), r.get('job_id'), r.get('country_id'), r.get('region_id'))


# 1) load regenerated records into key -> record
new = {}
dups = 0
with open(REGEN, encoding='utf-8') as f:
    for line in f:
        if not line.strip():
            continue
        r = json.loads(line)
        k = key_of(r)
        if k in new:
            dups += 1
        new[k] = r
print(f'regenerated records loaded: {len(new):,} | duplicate keys in regen: {dups}')

# 2) stream main output, replace where key was regenerated
used = set()
replaced = kept = 0
with open(MAIN, encoding='utf-8') as fin, open(DST, 'w', encoding='utf-8') as fout:
    for line in fin:
        if not line.strip():
            continue
        r = json.loads(line)
        k = key_of(r)
        if k in new:
            fout.write(json.dumps(new[k], ensure_ascii=False) + '\n')
            used.add(k)
            replaced += 1
        else:
            fout.write(line if line.endswith('\n') else line + '\n')
            kept += 1
    # 3) append regenerated records that had no row in main (the missing ones)
    appended = 0
    for k, r in new.items():
        if k not in used:
            fout.write(json.dumps(r, ensure_ascii=False) + '\n')
            appended += 1

print(f'replaced (existing rows) : {replaced:,}')
print(f'appended (were missing)  : {appended:,}')
print(f'untouched original rows  : {kept:,}')
print(f'total rows written       : {replaced + kept + appended:,}')
print(f'\nwrote {DST}')
print('Original left intact. Verify with check_content_quality.py against the '
      'SPLICED file, then swap it in.')
