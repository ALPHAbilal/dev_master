#!/usr/bin/env python3
"""
Prompt-runner pipeline (NOT translation).

For every record in each input JSON file, send its `prompt` field to the OpenAI
Batch API, take back whatever the model writes, and produce an output record that
is the ORIGINAL record with `prompt` REPLACED IN PLACE by `response`. Every other
key (ids, names, ...) is preserved exactly and untouched.

Pipeline pieces (mirror the translation pipeline):
  (1) LOADER    - stream each JSON array record-by-record, take first --limit per file
  (2) BUILDER   - one JSONL request per record (custom_id = <fileslug>__<index>)
  (3) SUBMIT    - upload + create batch on OpenAI
  (4) POLL      - wait for completion
  (5) DOWNLOAD  - fetch results.jsonl
  (6) MERGER    - drop `prompt`, insert `response` in its place, keep all other keys
  (7) OUTPUT    - write <name>_responses.json (one record per line)

Usage:
    python run_prompts.py --dry-run                 # build JSONL only, no API call
    python run_prompts.py --submit --wait           # first 50 from each file (default)
    python run_prompts.py --limit 50 --submit --wait
    python run_prompts.py --model gpt-4.1-nano --submit --wait
    python run_prompts.py --files exec/pays_ville_exec.json --limit 10 --submit --wait
"""

import argparse
import codecs
import json
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

import openai

BASE_DIR = Path(__file__).resolve().parent
# OpenAI key lives in the soufiane_prompts folder .env.
ENV_PATH = BASE_DIR.parent / '.env'


def load_dotenv():
    """Load settings from soufiane_prompts/.env. Real env wins."""
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# .env must be loaded BEFORE the config block below, otherwise PROMPT_* settings
# in the .env are silently ignored (they would be read before the file is parsed).
load_dotenv()

# ---- config --------------------------------------------------------------
DEFAULT_MODEL = os.getenv('PROMPT_MODEL', 'gpt-4.1-nano')  # nano by default here
TEMPERATURE = float(os.getenv('PROMPT_TEMPERATURE', '0.0'))
TOP_P = float(os.getenv('PROMPT_TOP_P', '1.0'))
SEED = int(os.getenv('PROMPT_SEED', '42'))
MAX_TOKENS = int(os.getenv('PROMPT_MAX_TOKENS', '3000'))

# Léger rappel de rôle. Le vrai contenu (rôle + tâche) vit déjà dans le user
# prompt de chaque fichier ; ce system prompt sert uniquement à s'assurer que
# le modèle respecte scrupuleusement ces consignes.
SYSTEM_PROMPT = os.getenv('PROMPT_SYSTEM', (
    "Tu es un assistant rigoureux. Suis EXACTEMENT et intégralement les "
    "instructions données dans le message de l'utilisateur.\n"
    "RÈGLES ABSOLUES :\n"
    "1. Réponds UNIQUEMENT avec un objet JSON valide — aucun texte avant ou "
    "après, pas de balises markdown (```), pas de commentaires.\n"
    "2. Respecte EXACTEMENT la structure décrite dans la section « FORMAT DE "
    "RÉPONSE ATTENDU » du message : mêmes noms de clés, même imbrication, même "
    "nombre de champs. N'ajoute AUCUNE clé, n'en supprime aucune, n'invente "
    "aucune question ni réponse supplémentaire.\n"
    "3. Recopie les questions fournies MOT POUR MOT (lignes ❖ ou listes "
    "« Catégorie E / F »), dans l'ordre. Ne les reformule JAMAIS, n'en invente "
    "aucune, ne les adapte pas à la ville.\n"
    "4. Respecte IMPÉRATIVEMENT le nombre de mots imposé. « 80-120 mots » "
    "signifie AU MINIMUM 80 mots : compte-les et développe si nécessaire. "
    "Aucun champ ne doit être vide.\n"
    "5. N'ajoute aucun titre, aucune explication et aucun texte hors de ce qui "
    "est demandé."
))

# The five input files.
DEFAULT_FILES = [
    'exec/pays_ville_exec.json',
    'exec/prompts_exec_profile_ville.json',
    'marche/prompts_type1_pays_marche.json',
    'marche/prompts_type2_pays_ville_marche.json',
    'marche/prompts_type3_pays_ville_presentation.json',
]

# ---- Structured Outputs: one strict JSON schema per input file -----------
# Each file's prompts demand a specific response structure (section "FORMAT DE
# RÉPONSE ATTENDU"). OpenAI's strict json_schema mode FORCES the model to emit
# exactly that structure — no malformed JSON, no missing/extra keys possible.

def _qa_group():
    """questions_e / questions_f block: exactly question_1..5 + reponse_1..5."""
    props, req = {}, []
    for i in range(1, 6):
        props[f'question_{i}'] = {'type': 'string'}
        props[f'reponse_{i}'] = {'type': 'string'}
        req += [f'question_{i}', f'reponse_{i}']
    return {'type': 'object', 'properties': props, 'required': req,
            'additionalProperties': False}

_SCHEMA_BLOC_ONLY = {
    'type': 'object',
    'properties': {'bloc_principal': {'type': 'string'}},
    'required': ['bloc_principal'],
    'additionalProperties': False,
}
_SCHEMA_FLAT_QA = {
    'type': 'object',
    'properties': {'bloc_principal': {'type': 'string'},
                   'questions_e': _qa_group(), 'questions_f': _qa_group()},
    'required': ['bloc_principal', 'questions_e', 'questions_f'],
    'additionalProperties': False,
}
_SCHEMA_NESTED_QA = {
    'type': 'object',
    'properties': {
        'bloc_principal': {'type': 'string'},
        'questions': {
            'type': 'object',
            'properties': {'questions_e': _qa_group(), 'questions_f': _qa_group()},
            'required': ['questions_e', 'questions_f'],
            'additionalProperties': False,
        },
    },
    'required': ['bloc_principal', 'questions'],
    'additionalProperties': False,
}

RESPONSE_SCHEMAS = {
    'exec/pays_ville_exec.json': _SCHEMA_NESTED_QA,
    'exec/_regen_subsets/pays_ville_exec_REGEN.json': _SCHEMA_NESTED_QA,   # regen subset
    'exec/prompts_exec_profile_ville.json': _SCHEMA_FLAT_QA,
    'exec/_regen_subsets/prompts_exec_profile_ville_REGEN.json': _SCHEMA_FLAT_QA,  # regen subset
    'marche/prompts_type1_pays_marche.json': _SCHEMA_BLOC_ONLY,
    'marche/prompts_type2_pays_ville_marche.json': _SCHEMA_BLOC_ONLY,
    'marche/prompts_type3_pays_ville_presentation.json': _SCHEMA_FLAT_QA,

    # ---- FR->EN translation pass -------------------------------------------
    # Built by build_translation_sources.py. Each record keeps its metadata and
    # carries a `prompt` holding the French response JSON to translate. The
    # schema is the SAME shape as the file it came from, so the translated
    # response comes back in exactly the structure the French had.
    # These are deliberately NOT in LETTERED_FILES/PLAIN_QUESTION_FILES: the
    # questions are being translated here, so pinning them to the French text
    # would forbid the very output we want.
    'translate_src/exec/pays_ville_exec.json': _SCHEMA_NESTED_QA,
    'translate_src/exec/prompts_exec_profile_ville.json': _SCHEMA_FLAT_QA,
    'translate_src/marche/prompts_type1_pays_marche.json': _SCHEMA_BLOC_ONLY,
    'translate_src/marche/prompts_type2_pays_ville_marche.json': _SCHEMA_BLOC_ONLY,
    'translate_src/marche/prompts_type3_pays_ville_presentation.json': _SCHEMA_FLAT_QA,
}


# ---- question extraction: pin the E/F questions into the schema -----------
# Some prompts list their 10 questions explicitly ("❖ Question E1: ..."). When we
# can extract them RELIABLY we pin each one into the schema with `enum`, which
# makes a wrong/invented question impossible instead of merely discouraged.
# The extractor is deliberately strict: anything unexpected returns None and the
# caller falls back to the generic schema (fail safe, never pin garbage).

_Q_LETTERED = re.compile(r'❖ Question\s*([EF])\s*(\d)\s*:\s*(.+)')

# Files whose prompts use the lettered form. Verified over 100% of records:
#   prompts_exec_profile_ville.json -> 286,605/286,605 have exactly E1-E5, F1-F5
#   type3_pays_ville_presentation   ->     579/579     idem
LETTERED_FILES = {
    'exec/prompts_exec_profile_ville.json',
    'exec/_regen_subsets/prompts_exec_profile_ville_REGEN.json',   # regen subset (28 missing)
    'marche/prompts_type3_pays_ville_presentation.json',
}

# Files whose prompts list their 10 questions with the PLAIN form "❖ Question: ..."
# (no E/F letter, no digit). The 10 appear in order and split 5+5: the first five
# are questions_e, the last five questions_f. Verified: 304,920/304,920 records of
# pays_ville_exec have exactly 10 such lines and no placeholder ❖ lines.
PLAIN_QUESTION_FILES = {
    'exec/pays_ville_exec.json',
    'exec/_regen_subsets/pays_ville_exec_REGEN.json',   # regen subset (defective/mismatch/missing)
}
_Q_PLAIN = re.compile(r'❖ Question:\s*(.+)')


def extract_questions_lettered(prompt):
    """Return {'E': [q1..q5], 'F': [q1..q5]} or None if anything is off.

    NOTE: a plain '❖ Question:' regex would also match the 2 placeholder lines in
    the FORMAT block of these prompts — which is why we require the LETTER+DIGIT.
    """
    found = _Q_LETTERED.findall(prompt)
    if len(found) != 10:
        return None
    out = {'E': [None] * 5, 'F': [None] * 5}
    for cat, digit, text in found:
        i = int(digit)
        if not 1 <= i <= 5:
            return None
        if out[cat][i - 1] is not None:      # duplicate slot (e.g. two E3)
            return None
        text = text.strip()
        # a question must be real text, not a placeholder or a stray token
        if len(text) < 10 or text.lower().startswith('[') or text.lower() == 'string':
            return None
        # SQL-escape artifact in the source data ("M\'Sila", "Cote d\'Ivoire").
        # A backslash inside an `enum` value makes OpenAI's constrained decoder
        # truncate the string mid-word (verified: same request succeeds once the
        # backslash is removed), and it reports finish_reason=stop so the
        # truncation is silent. The backslash is not part of the real name, so
        # drop it before the text is ever used as an enum value.
        text = text.replace("\\'", "'")
        out[cat][i - 1] = text
    if any(v is None for v in out['E'] + out['F']):
        return None                          # a slot never filled -> incomplete
    return out


def extract_questions_plain(prompt):
    """Return {'E': [q1..q5], 'F': [q1..q5]} from PLAIN "❖ Question: ..." prompts,
    or None if anything is off. The 10 questions split 5+5 (E then F) in order.
    """
    found = [m.strip() for m in _Q_PLAIN.findall(prompt)]
    if len(found) != 10:
        return None
    clean = []
    for text in found:
        # same guards as the lettered extractor: real text, no placeholders
        if len(text) < 10 or text.startswith('[') or text.lower() == 'string':
            return None
        # SQL-escape artifact ("M\'Sila"): a backslash in an enum value makes
        # OpenAI's constrained decoder truncate mid-word (silent, finish=stop),
        # so drop it before the text is ever used as an enum value.
        clean.append(text.replace("\\'", "'"))
    return {'E': clean[:5], 'F': clean[5:]}


def questions_for(rel, prompt):
    """Extracted questions for this record, or None when pinning doesn't apply."""
    key = str(rel).replace('\\', '/')
    if key in LETTERED_FILES:
        return extract_questions_lettered(prompt)
    if key in PLAIN_QUESTION_FILES:
        return extract_questions_plain(prompt)
    return None


def _pinned_qa_group(questions):
    """questions_e/f block where each question_N is PINNED to one exact string.

    `enum` with a single value + strict mode makes any other text impossible to
    emit, so the model cannot invent a question or copy one from the wrong list.
    Pinning question_N also anchors reponse_N, because generation is sequential.
    """
    props, req = {}, []
    for i in range(1, 6):
        props[f'question_{i}'] = {'type': 'string', 'enum': [questions[i - 1]]}
        props[f'reponse_{i}'] = {'type': 'string'}
        req += [f'question_{i}', f'reponse_{i}']
    return {'type': 'object', 'properties': props, 'required': req,
            'additionalProperties': False}


def _pinned_schema(shape, qs):
    """Build the file's schema with the 10 questions pinned. `shape` is 'flat'
    or 'nested', matching the file's FORMAT section."""
    e, f = _pinned_qa_group(qs['E']), _pinned_qa_group(qs['F'])
    if shape == 'nested':
        return {'type': 'object',
                'properties': {'bloc_principal': {'type': 'string'},
                               'questions': {'type': 'object',
                                             'properties': {'questions_e': e, 'questions_f': f},
                                             'required': ['questions_e', 'questions_f'],
                                             'additionalProperties': False}},
                'required': ['bloc_principal', 'questions'],
                'additionalProperties': False}
    return {'type': 'object',
            'properties': {'bloc_principal': {'type': 'string'},
                           'questions_e': e, 'questions_f': f},
            'required': ['bloc_principal', 'questions_e', 'questions_f'],
            'additionalProperties': False}


def response_format_for(rel, prompt=None):
    """Strict schema for a known file; plain json_object mode for unknown ones
    (still guarantees valid JSON, just not the exact key layout).

    When `prompt` is given and its 10 E/F questions can be extracted reliably,
    the questions are PINNED into the schema (see _pinned_qa_group). Anything
    unexpected falls back to the generic schema below — never pin garbage.
    """
    key = str(rel).replace('\\', '/')
    if prompt is not None and (key in LETTERED_FILES or key in PLAIN_QUESTION_FILES):
        qs = questions_for(key, prompt)
        if qs is not None:
            base = RESPONSE_SCHEMAS.get(key)
            shape = 'nested' if (base and 'questions' in base.get('properties', {})) else 'flat'
            return {'type': 'json_schema',
                    'json_schema': {'name': 'reponse', 'strict': True,
                                    'schema': _pinned_schema(shape, qs)}}
    schema = RESPONSE_SCHEMAS.get(str(rel).replace('\\', '/'))
    if schema is None:
        return {'type': 'json_object'}
    return {'type': 'json_schema',
            'json_schema': {'name': 'reponse', 'strict': True, 'schema': schema}}


BATCH_DIR = BASE_DIR / 'batch_runs'
# Output root. Override with PROMPT_OUT_DIR so a different kind of run (e.g. the
# French->English translation pass) writes into its own tree instead of mixing
# its results in with the generated content.
OUT_DIR = BASE_DIR / os.getenv('PROMPT_OUT_DIR', 'responses')
LEDGER_DIR = BATCH_DIR / 'ledgers'

# OpenAI Batch API hard limits. The script sizes chunks against these itself.
MAX_BATCH_REQUESTS = 50_000
MAX_BATCH_BYTES = 180 * 1024 * 1024   # 200MB limit, kept under with margin
# ~878 input tokens/record measured on this data. 200 x 10 = ~1.76M enqueued,
# which fits the 2M org cap — this is what makes 10 live batches possible.
DEFAULT_CHUNK = 100                   # records per batch: smaller batches finish
                                      # sooner (fewer requests to process), so
                                      # results merge earlier and the pool cycles
                                      # faster. Throughput is governed by the
                                      # token budget, not by batch size.
DEFAULT_CONCURRENCY = 10              # batches kept alive at once (token budget may cap lower)
# OpenAI caps ENQUEUED tokens per org/model (2M for gpt-4.1-nano on this org).
# Exceeding it makes batches fail outright, so the pool is paced by tokens, not
# just batch count. Kept under the real limit for margin.
DEFAULT_TOKEN_BUDGET = 1_900_000

try:
    import tiktoken
    _ENC = tiktoken.get_encoding('o200k_base')
    def count_tokens(text): return len(_ENC.encode(text))
except Exception:                      # tiktoken absent: conservative estimate
    def count_tokens(text): return len(text) // 3


# ---- (1) LOADER: stream first N records without loading the whole file ----
def stream_records(path: Path, limit: int):
    """Yield the first `limit` JSON objects from a top-level JSON array.

    Reads the file in chunks and decodes one object at a time with
    json.JSONDecoder.raw_decode, so a 2.3 GB file never enters memory whole.
    """
    decoder = json.JSONDecoder()
    buf = ''
    started = False   # have we passed the opening '['
    yielded = 0
    with open(path, 'r', encoding='utf-8') as f:
        while yielded < limit:
            if not started:
                # find the opening bracket of the array
                while '[' not in buf:
                    chunk = f.read(65536)
                    if not chunk:
                        return
                    buf += chunk
                buf = buf[buf.index('[') + 1:]
                started = True

            # strip leading whitespace / commas
            buf = buf.lstrip()
            while buf[:1] in (',',):
                buf = buf[1:].lstrip()
            if buf[:1] == ']':
                return  # end of array

            # need more data?
            if not buf:
                chunk = f.read(65536)
                if not chunk:
                    return
                buf += chunk
                continue

            try:
                obj, idx = decoder.raw_decode(buf)
            except json.JSONDecodeError:
                # object spans past the buffer; pull more bytes
                chunk = f.read(65536)
                if not chunk:
                    return
                buf += chunk
                continue

            buf = buf[idx:]
            yield obj
            yielded += 1


def stream_from(path: Path, start_offset: int, limit: int):
    """Yield (record, offset_after) starting at a byte offset inside the array.

    offset_after is the absolute byte position just past the record, so it can be
    stored in the ledger and used to resume the next chunk without rescanning the
    file from byte 0. start_offset == 0 means "start of file, find the '[' first".
    """
    decoder = json.JSONDecoder()
    yielded = 0
    # Binary reads + incremental UTF-8 decoding: text-mode tell() returns an
    # opaque cookie, not a byte count, so offsets must be tracked by hand.
    utf8 = codecs.getincrementaldecoder('utf-8')()
    buf = ''
    base = start_offset          # absolute byte offset of buf[0]

    def consume(n):
        """Drop n chars off the front of buf, advancing `base` by their byte length."""
        nonlocal buf, base
        base += len(buf[:n].encode('utf-8'))
        buf = buf[n:]

    with open(path, 'rb') as f:
        f.seek(start_offset)
        started = start_offset > 0
        while yielded < limit:
            if not started:
                while '[' not in buf:
                    raw = f.read(65536)
                    if not raw:
                        return
                    buf += utf8.decode(raw)
                consume(buf.index('[') + 1)
                started = True

            consume(len(buf) - len(buf.lstrip()))
            while buf[:1] == ',':
                consume(1)
                consume(len(buf) - len(buf.lstrip()))
            if buf[:1] == ']':
                return

            if not buf:
                raw = f.read(65536)
                if not raw:
                    return
                buf += utf8.decode(raw)
                continue

            try:
                obj, idx = decoder.raw_decode(buf)
            except json.JSONDecodeError:
                raw = f.read(65536)
                if not raw:
                    return
                buf += utf8.decode(raw)
                continue

            consume(idx)
            yield obj, base          # absolute byte position just past this record
            yielded += 1


# ---- LEDGER: what's done, what's in flight, where to resume ---------------
def ledger_path(slug: str) -> Path:
    return LEDGER_DIR / f"ledger_{slug}.json"


def load_ledger(slug: str, rel: str) -> dict:
    p = ledger_path(slug)
    if p.exists():
        led = json.loads(p.read_text(encoding='utf-8'))
        led.setdefault('run_tag', 'legacy')   # ledgers written before run tags
        return led
    return {
        "file": rel,
        "slug": slug,
        # Unique per ledger. Batch run_names embed it so a fresh start can never
        # collide with same-numbered batches from an earlier, discarded run —
        # chunk numbering restarts at 0 but the tag makes the names distinct.
        "run_tag": uuid.uuid4().hex[:8],
        "next_index": 0,      # next record index to submit
        "byte_offset": 0,     # resume point in the source file
        "completed": 0,       # records merged into the output so far
        "chunks": [],         # {chunk, start_index, count, batch_id, status, offset_after}
    }


def save_ledger(led: dict):
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    ledger_path(led['slug']).write_text(
        json.dumps(led, ensure_ascii=False, indent=2), encoding='utf-8')


def file_slug(rel_path: str) -> str:
    return rel_path.replace('/', '__').replace('\\', '__').replace('.json', '')


# ---- (2) BUILDER ---------------------------------------------------------
def build_requests(files, limit, model):
    """Return (requests, sidecar, manifest).

    sidecar  maps custom_id -> original record.
    manifest maps file slug -> original relative path (so the output tree can
    mirror the input tree: same subfolders, same filenames, + _output suffix).
    """
    requests = []
    sidecar = {}
    manifest = {}
    for rel in files:
        path = BASE_DIR / rel
        if not path.exists():
            print(f"  ! missing file, skipping: {rel}")
            continue
        slug = file_slug(rel)
        manifest[slug] = rel.replace('\\', '/')
        count = 0
        for i, record in enumerate(stream_records(path, limit)):
            prompt = record.get('prompt')
            if not prompt:
                print(f"  ! record {i} in {rel} has no 'prompt', skipping")
                continue
            custom_id = f"{slug}__{i}"
            sidecar[custom_id] = record
            requests.append({
                "custom_id": custom_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "max_completion_tokens": MAX_TOKENS,
                    "temperature": TEMPERATURE,
                    "top_p": TOP_P,
                    "seed": SEED,
                    "response_format": response_format_for(rel, prompt),
                },
            })
            count += 1
        print(f"  {rel}: {count} records")
    return requests, sidecar, manifest


# ---- (3) SUBMIT ----------------------------------------------------------
def submit(client, requests, run_name):
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = BATCH_DIR / f"requests_{run_name}.jsonl"
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for req in requests:
            f.write(json.dumps(req, ensure_ascii=False) + '\n')
    print(f"  wrote {len(requests)} requests -> {jsonl_path}")

    with open(jsonl_path, 'rb') as f:
        up = client.files.create(file=f, purpose="batch")
    print(f"  uploaded file: {up.id}")

    batch = client.batches.create(
        input_file_id=up.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"run_name": run_name},
    )
    print(f"  batch submitted: {batch.id}")
    print(f"  monitor: https://platform.openai.com/batches/{batch.id}")
    (BATCH_DIR / f"batch_info_{run_name}.json").write_text(
        json.dumps({"batch_id": batch.id, "run_name": run_name,
                    "request_count": len(requests),
                    "created_at": datetime.now().isoformat()}, indent=2))
    return batch.id


# ---- (4)+(5) POLL + DOWNLOAD --------------------------------------------
def wait_and_download(client, batch_id, run_name, interval):
    print(f"\nwaiting on batch {batch_id} (every {interval}s)...")
    start = time.time()
    while True:
        batch = client.batches.retrieve(batch_id)
        rc = batch.request_counts
        el = time.time() - start
        print(f"[{time.strftime('%H:%M:%S')}] {batch.status} | "
              f"{rc.completed}/{rc.total} (failed {rc.failed}) | "
              f"{int(el//60)}m {int(el%60)}s")
        if batch.status == "completed":
            break
        if batch.status in ("failed", "expired", "cancelled"):
            print(f"BATCH {batch.status.upper()}: {batch.errors}")
            return None
        time.sleep(interval)

    content = client.files.content(batch.output_file_id)
    text = content.content.decode('utf-8')
    results_path = BATCH_DIR / f"results_{run_name}.jsonl"
    results_path.write_text(text, encoding='utf-8')
    print(f"  saved results -> {results_path}")
    return text


# ---- (6) MERGER + (7) OUTPUT --------------------------------------------
def _output_path_for(slug, manifest):
    """Mirror the input tree under OUT_DIR, adding an _output suffix.
    exec/pays_ville_exec.json -> responses/exec/pays_ville_exec_output.json
    Falls back to a flat name if the slug isn't in the manifest."""
    rel = manifest.get(slug)
    if rel:
        rel_path = Path(rel)
        # A staging folder (translate_src/) is an implementation detail of how the
        # input was prepared; it should not reappear inside the output tree.
        if rel_path.parts and rel_path.parts[0] == 'translate_src':
            rel_path = Path(*rel_path.parts[1:])
        out = OUT_DIR / rel_path.parent / f"{rel_path.stem}_output.json"
    else:
        out = OUT_DIR / f"{slug}_output.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def merge_and_write(results_text, sidecar, run_name, manifest):
    """Attach responses to original records: drop `prompt`, put `response` in place."""
    responses = {}
    failed = 0
    for line in results_text.strip().split('\n'):
        if not line:
            continue
        r = json.loads(line)
        cid = r['custom_id']
        resp = r.get('response') or {}
        if resp.get('status_code') == 200:
            try:
                responses[cid] = resp['body']['choices'][0]['message']['content']
            except (KeyError, IndexError):
                failed += 1
        else:
            failed += 1

    # group merged records back by source file
    by_file = {}
    for cid, record in sidecar.items():
        if cid not in responses:
            continue
        merged = {}
        for k, v in record.items():
            if k == 'prompt':
                merged['response'] = responses[cid]   # replace prompt in place
            else:
                merged[k] = v
        if 'response' not in merged:                  # record had no prompt key slot
            merged['response'] = responses[cid]
        slug = cid.rsplit('__', 1)[0]
        by_file.setdefault(slug, []).append(merged)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for slug, records in by_file.items():
        out_path = _output_path_for(slug, manifest)
        with open(out_path, 'w', encoding='utf-8') as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print(f"  {out_path.relative_to(OUT_DIR)}: {len(records)} records")
        total += len(records)
    print(f"\nmerged {total} records | {failed} failed")


# ---- CHUNK BUILDER: sizes itself against the Batch API limits ------------
def build_chunk(rel, slug, start_index, start_offset, want, model):
    """Build up to `want` requests starting at start_offset.

    Stops early if the chunk would exceed MAX_BATCH_REQUESTS or MAX_BATCH_BYTES,
    so the caller never has to think about OpenAI's limits.
    Returns (requests, sidecar, offset_after, n_read).
    """
    path = BASE_DIR / rel
    cap = min(want, MAX_BATCH_REQUESTS)
    requests, sidecar = [], {}
    nbytes = 0
    ntokens = 0
    offset_after = start_offset
    n_read = 0

    for record, off in stream_from(path, start_offset, cap):
        i = start_index + n_read
        n_read += 1
        offset_after = off
        prompt = record.get('prompt')
        if not prompt:
            continue
        custom_id = f"{slug}__{i}"
        req = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "max_completion_tokens": MAX_TOKENS,
                "temperature": TEMPERATURE,
                "top_p": TOP_P,
                "seed": SEED,
                "response_format": response_format_for(rel, prompt),
            },
        }
        line_bytes = len(json.dumps(req, ensure_ascii=False).encode('utf-8')) + 1
        if requests and nbytes + line_bytes > MAX_BATCH_BYTES:
            n_read -= 1           # this record rolls into the next chunk
            offset_after = start_offset if n_read == 0 else prev_off
            break
        nbytes += line_bytes
        ntokens += count_tokens(SYSTEM_PROMPT) + count_tokens(prompt)
        requests.append(req)
        sidecar[custom_id] = record
        prev_off = off

    return requests, sidecar, offset_after, n_read, nbytes, ntokens


def merge_append(results_text, sidecar, out_path):
    """Append merged records to the output file. Output grows chunk by chunk.

    Returns a stats dict describing what came back, so the caller can log exactly
    what OpenAI returned rather than just a count.
    """
    responses = {}
    errors = []           # (custom_id, code, message) for anything not merged
    usage = {'prompt_tokens': 0, 'completion_tokens': 0}
    finish = {}           # finish_reason -> count ('length' means truncated output
    lengths = []          # response character counts

    for line in results_text.strip().split('\n'):
        if not line:
            continue
        r = json.loads(line)
        cid = r.get('custom_id')
        resp = r.get('response') or {}
        if resp.get('status_code') == 200:
            try:
                ch0 = resp['body']['choices'][0]
                responses[cid] = ch0['message']['content']
                fr = ch0.get('finish_reason', '?')
                finish[fr] = finish.get(fr, 0) + 1
                lengths.append(len(responses[cid] or ''))
                u = resp['body'].get('usage') or {}
                usage['prompt_tokens'] += u.get('prompt_tokens', 0)
                usage['completion_tokens'] += u.get('completion_tokens', 0)
            except (KeyError, IndexError) as e:
                errors.append((cid, 'malformed_response', str(e)))
        else:
            err = (resp.get('body') or {}).get('error') or {}
            errors.append((cid, err.get('code') or f"http_{resp.get('status_code')}",
                           err.get('message', '')))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with open(out_path, 'a', encoding='utf-8') as f:   # append, never truncate
        for cid, record in sidecar.items():
            if cid not in responses:
                continue
            merged = {}
            for k, v in record.items():
                if k == 'prompt':
                    merged['response'] = responses[cid]
                else:
                    merged[k] = v
            if 'response' not in merged:
                merged['response'] = responses[cid]
            f.write(json.dumps(merged, ensure_ascii=False) + '\n')
            written += 1

    # Records in the batch that produced neither a response nor an error line.
    missing = [c for c in sidecar if c not in responses
               and c not in {e[0] for e in errors}]
    return {
        'written': written, 'failed': len(errors), 'errors': errors,
        'usage': usage, 'finish': finish, 'missing': missing,
        'avg_chars': int(sum(lengths) / len(lengths)) if lengths else 0,
        'min_chars': min(lengths) if lengths else 0,
        'max_chars': max(lengths) if lengths else 0,
    }


def log_event(payload):
    """Append one structured JSON line to the permanent batch log."""
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    payload = dict(payload, ts=datetime.now().isoformat(timespec='seconds'))
    with open(BATCH_DIR / 'batch_log.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps(payload, ensure_ascii=False) + '\n')


def find_batch_by_run_name(client, run_name, scan=500):
    """Ask OpenAI whether a batch tagged with this run_name already exists.

    submit() stamps metadata={"run_name": ...} on every batch, so a chunk whose
    intent was recorded but whose ledger write never landed can be identified and
    adopted instead of resent. Returns the batch or None.
    """
    seen = 0
    after = None
    while seen < scan:
        page = client.batches.list(limit=100, after=after) if after else client.batches.list(limit=100)
        data = list(page.data)
        if not data:
            return None
        for b in data:
            meta = b.metadata or {}
            if meta.get('run_name') == run_name:
                return b
            seen += 1
        after = data[-1].id
        if not getattr(page, 'has_more', False):
            return None
    return None


# ---- ORCHESTRATOR: chunk -> submit -> wait -> merge -> next chunk --------
def orchestrate(client, rel, target, chunk_size, model, interval, concurrency,
                token_budget=DEFAULT_TOKEN_BUDGET):
    slug = file_slug(rel)
    led = load_ledger(slug, rel)
    out_path = _output_path_for(slug, {slug: rel})

    print(f"\n=== ORCHESTRATE {rel} ===")
    print(f"  target {target} | {chunk_size}/batch | max {concurrency} alive | "
          f"token budget {token_budget/1e6:.1f}M enqueued")
    print(f"  already completed {led['completed']} | "
          f"resume at record {led['next_index']} (byte {led['byte_offset']})")

    def collect(ch):
        """Download a finished batch, merge it, mark done — logging exactly what came back."""
        run_name = f"{slug}_{led['run_tag']}_c{ch['chunk']}"
        batch = client.batches.retrieve(ch['batch_id'])

        # A batch can reach status 'completed' while every request inside it
        # FAILED (e.g. 401 ip_not_authorized). Then output_file_id is None and
        # only error_file_id exists. Don't crash — mark the chunk failed so the
        # normal retry path re-sends it.
        if not batch.output_file_id:
            reason = ''
            try:
                if batch.error_file_id:
                    first = client.files.content(batch.error_file_id).content.decode(
                        'utf-8').splitlines()[0]
                    reason = json.loads(first)['response']['body']['error']['message']
            except Exception:
                pass
            print(f"\n  [chunk {ch['chunk']}] NO OUTPUT — all {batch.request_counts.failed} "
                  f"requests failed: {reason or 'unknown'}")
            print(f"    -> records {ch['start_index']}-"
                  f"{ch['start_index']+ch.get('n_read',0)-1} queued for retry")
            log_event({'event': 'all_requests_failed', 'run_name': run_name,
                       'batch_id': batch.id, 'file': rel, 'chunk': ch['chunk'],
                       'start_index': ch['start_index'], 'reason': reason})
            ch['status'] = 'failed'
            ch['tokens'] = 0
            save_ledger(led)
            return

        content = client.files.content(batch.output_file_id)
        text = content.content.decode('utf-8')
        results_path = BATCH_DIR / f"results_{run_name}.jsonl"
        results_path.write_text(text, encoding='utf-8')
        sidecar = json.loads((BATCH_DIR / f"sidecar_{run_name}.json").read_text(encoding='utf-8'))

        # Remember where the output ends BEFORE appending. If we die mid-merge,
        # the ledger still says 'merging' and the next run rewinds the file to
        # this mark before retrying — otherwise those rows land twice.
        ch['out_offset'] = out_path.stat().st_size if out_path.exists() else 0
        ch['status'] = 'merging'
        save_ledger(led)

        st = merge_append(text, sidecar, out_path)

        # PARTIAL failure: some requests in the batch failed, so their records are
        # simply absent from the output. The chunk still completes (we never resend
        # good records), but the missing ids are logged so they can be regenerated.
        got = {json.loads(l)['custom_id'] for l in text.splitlines() if l.strip()}
        missing = sorted(set(sidecar) - got)
        if missing:
            with open(BASE_DIR / 'MISSING_records.txt', 'a', encoding='utf-8') as fh:
                for cid in missing:
                    fh.write(f"{ch['chunk']}\t{cid}\n")
            print(f"    *** {len(missing)} record(s) MISSING (request-level failures) "
                  f"-> logged to MISSING_records.txt ***")

        ch['status'] = 'done'
        led['completed'] += st['written']
        save_ledger(led)

        rc = batch.request_counts
        secs = (batch.completed_at - batch.created_at) if (
            batch.completed_at and batch.created_at) else None
        u = st['usage']
        print(f"\n  [chunk {ch['chunk']}] RESULTS RECEIVED")
        print(f"    batch name : {run_name}")
        print(f"    batch id   : {batch.id}")
        print(f"    metadata   : {dict(batch.metadata or {})}")
        print(f"    endpoint   : {batch.endpoint} | model: {model} | window: {batch.completion_window}")
        print(f"    files      : in={batch.input_file_id} out={batch.output_file_id}"
              + (f" err={batch.error_file_id}" if batch.error_file_id else ""))
        print(f"    records    : {ch['start_index']}-{ch['start_index']+ch.get('n_read',0)-1} "
              f"({ch['count']} sent)")
        print(f"    counts     : {rc.completed} completed / {rc.total} total / {rc.failed} failed")
        if secs is not None:
            print(f"    duration   : {secs//60}m {secs%60}s")
        print(f"    tokens used: {u['prompt_tokens']:,} in + {u['completion_tokens']:,} out "
              f"= {u['prompt_tokens']+u['completion_tokens']:,}")
        print(f"    finish     : {st['finish'] or '-'}"
              + ("   <-- 'length' = output hit max_completion_tokens and was CUT OFF"
                 if st['finish'].get('length') else ""))
        print(f"    resp chars : avg {st['avg_chars']} (min {st['min_chars']}, max {st['max_chars']})")
        print(f"    merged     : {st['written']} -> {out_path.name}")
        if st['errors']:
            from collections import Counter
            print(f"    ERRORS     : {st['failed']} -> {dict(Counter(e[1] for e in st['errors']))}")
            for cid, code, msg in st['errors'][:3]:
                print(f"      - {cid}: {code}: {msg[:100]}")
        if st['missing']:
            print(f"    MISSING    : {len(st['missing'])} records returned nothing "
                  f"(e.g. {st['missing'][:3]})")
        print(f"    progress   : {led['completed']}/{target}")

        log_event({
            'event': 'results_received', 'run_name': run_name, 'batch_id': batch.id,
            'metadata': dict(batch.metadata or {}), 'file': rel, 'chunk': ch['chunk'],
            'model': model, 'endpoint': batch.endpoint,
            'input_file_id': batch.input_file_id, 'output_file_id': batch.output_file_id,
            'error_file_id': batch.error_file_id,
            'start_index': ch['start_index'], 'n_read': ch.get('n_read'),
            'sent': ch['count'], 'completed': rc.completed, 'total': rc.total,
            'failed_requests': rc.failed, 'duration_s': secs,
            'created_at': batch.created_at, 'completed_at': batch.completed_at,
            'prompt_tokens': u['prompt_tokens'], 'completion_tokens': u['completion_tokens'],
            'finish_reasons': st['finish'], 'merged': st['written'],
            'avg_chars': st['avg_chars'], 'min_chars': st['min_chars'],
            'max_chars': st['max_chars'],
            'errors': [{'custom_id': c, 'code': k, 'message': m} for c, k, m in st['errors'][:20]],
            'missing': st['missing'][:20],
            'results_file': str(results_path), 'progress': led['completed'],
        })
        return True

    def send(ch):
        """Submit a chunk. Returns 'ok', 'empty', or 'token_limit' (retry later)."""
        run_name = f"{slug}_{led['run_tag']}_c{ch['chunk']}"
        requests, sidecar, off_after, n_read, nbytes, ntokens = build_chunk(
            rel, slug, ch['start_index'], ch['start_offset'], ch['want'], model)
        if not requests:
            ch['status'] = 'empty'
            save_ledger(led)
            return 'empty'
        BATCH_DIR.mkdir(parents=True, exist_ok=True)
        (BATCH_DIR / f"sidecar_{run_name}.json").write_text(
            json.dumps(sidecar, ensure_ascii=False), encoding='utf-8')
        try:
            batch_id = submit(client, requests, run_name)
        except Exception as e:
            if 'token_limit_exceeded' in str(e) or 'enqueued' in str(e).lower():
                ch['status'] = 'pending_submit'   # untouched; retried when room frees
                save_ledger(led)
                return 'token_limit'
            raise
        ch.update(batch_id=batch_id, status='in_flight', count=len(requests),
                  offset_after=off_after, n_read=n_read, tokens=ntokens)
        # Only ever move the frontier forward: a retried old chunk must not drag
        # next_index backwards over records later chunks already covered.
        if ch['start_index'] + n_read > led['next_index']:
            led['next_index'] = ch['start_index'] + n_read
            led['byte_offset'] = off_after
        save_ledger(led)
        return 'ok'

    # 0. RECOVER interrupted merges: rows may have been appended without the
    #    ledger recording it. Rewind the output to the pre-merge mark so the
    #    retry re-appends them exactly once instead of duplicating them.
    for ch in led['chunks']:
        if ch['status'] == 'merging':
            mark = ch.get('out_offset', 0)
            size = out_path.stat().st_size if out_path.exists() else 0
            if size > mark:
                with open(out_path, 'r+b') as f:
                    f.truncate(mark)
                print(f"\n-- chunk {ch['chunk']}: merge was interrupted. rewound output "
                      f"{size} -> {mark} bytes ({size-mark} bytes of partial/duplicate "
                      f"rows dropped), will re-merge")
            ch['status'] = 'in_flight'   # batch is still on OpenAI; collect it again
            save_ledger(led)

    # 1. RECONCILE: settle every unfinished chunk against OpenAI before sending more.
    for ch in led['chunks']:
        if ch['status'] == 'pending_submit':
            # Crash happened around the create() call. Ask OpenAI what's true.
            run_name = f"{slug}_{led['run_tag']}_c{ch['chunk']}"
            print(f"\n-- chunk {ch['chunk']}: intent recorded but outcome unknown. "
                  f"asking OpenAI if it was already accepted...")
            b = find_batch_by_run_name(client, run_name)
            if b is not None and b.status not in ('failed', 'expired', 'cancelled'):
                print(f"  FOUND on OpenAI (batch {b.id}) — adopting it, not resending.")
                # The crash killed send() before it could advance the cursor, so
                # recompute this chunk's span (build_chunk is deterministic) and
                # move next_index past it — otherwise the next chunk restarts on
                # records this batch already covers and duplicates them.
                _r, _s, off_after, n_read, _b, _t = build_chunk(
                    rel, slug, ch['start_index'], ch['start_offset'], ch['want'], model)
                ch.update(batch_id=b.id, status='in_flight',
                          count=len(_r), offset_after=off_after, n_read=n_read, tokens=_t)
                if ch['start_index'] + n_read > led['next_index']:
                    led['next_index'] = ch['start_index'] + n_read
                    led['byte_offset'] = off_after
                save_ledger(led)
            else:
                print(f"  never landed on OpenAI — queued for retry.")
                ch['status'] = 'failed'    # picked up by the retry pass below
                save_ledger(led)

    # Anything already in_flight simply rejoins the pool below — no resend.
    pool = [ch for ch in led['chunks'] if ch['status'] == 'in_flight']
    if pool:
        print(f"\n-- rejoining {len(pool)} batch(es) already in flight: "
              f"{[c['chunk'] for c in pool]}")

    exhausted = False

    def enqueued():
        return sum(c.get('tokens', 0) for c in pool)

    def dispatch(ch, label):
        """Send an already-budgeted chunk. Returns 'ok'/'empty'/'token_limit'."""
        r = send(ch)
        if r == 'ok':
            pool.append(ch)
            run_name = f"{slug}_{led['run_tag']}_c{ch['chunk']}"
            print(f"  [chunk {ch['chunk']}] SENT{label}: {run_name} | batch {ch['batch_id']} | "
                  f"records {ch['start_index']}-{ch['start_index']+ch['n_read']-1} "
                  f"({ch['count']} reqs, ~{ch['tokens']/1000:.0f}k tok) | "
                  f"pool {len(pool)}/{concurrency}, enqueued ~{enqueued()/1e6:.2f}M/"
                  f"{token_budget/1e6:.1f}M")
            log_event({'event': 'sent', 'run_name': run_name, 'batch_id': ch['batch_id'],
                       'file': rel, 'chunk': ch['chunk'], 'model': model,
                       'start_index': ch['start_index'], 'n_read': ch['n_read'],
                       'requests': ch['count'], 'est_tokens': ch['tokens'],
                       'retry': bool(label.strip()), 'pool_size': len(pool),
                       'enqueued_tokens': enqueued()})
        elif r == 'token_limit':
            print(f"  [chunk {ch['chunk']}] enqueued-token limit hit — backing off, "
                  f"retrying when a batch completes")
        return r

    def fill():
        """Top the pool back up, retrying failed chunks FIRST so no records are lost.

        The token budget is checked BEFORE an intent is recorded: writing an intent
        we then decline to send would orphan it, and the next run's reconcile would
        resend records a later chunk had already covered.
        """
        nonlocal exhausted
        while len(pool) < concurrency:
            # 1. Retry a previously failed chunk before advancing the frontier.
            retry = next((c for c in led['chunks'] if c['status'] == 'failed'), None)
            if retry is not None:
                _r, _s, _o, _n, _b, est = build_chunk(
                    rel, slug, retry['start_index'], retry['start_offset'],
                    retry['want'], model)
                if pool and enqueued() + est > token_budget:
                    return
                if dispatch(retry, ' (retry)') != 'ok':
                    return
                continue

            if exhausted or led['next_index'] >= target:
                return

            # 2. New chunk: price it BEFORE recording intent.
            want = min(chunk_size, target - led['next_index'])
            probe, _s, _o, _n, _b, est = build_chunk(
                rel, slug, led['next_index'], led['byte_offset'], want, model)
            if not probe:
                exhausted = True
                print("  no more records in file.")
                return
            if pool and enqueued() + est > token_budget:
                return   # no intent written — nothing to orphan

            # INTENT FIRST (now that it's budgeted): recorded before OpenAI is
            # called, so a crash during create() is resolved by asking OpenAI.
            ch = {"chunk": len(led['chunks']), "start_index": led['next_index'],
                  "start_offset": led['byte_offset'], "want": want,
                  "batch_id": None, "status": "pending_submit"}
            led['chunks'].append(ch)
            save_ledger(led)
            if dispatch(ch, '') != 'ok':
                return

    # 2. Pool loop: keep the pool as full as the token budget allows; as each
    #    batch lands, merge it and send a replacement, until target is consumed.
    fill()
    while pool:
        time.sleep(interval)
        for ch in list(pool):
            b = client.batches.retrieve(ch['batch_id'])
            rc_ = b.request_counts
            ch['prog'] = (rc_.completed, rc_.total) if rc_ else (0, ch.get('count', 0))
            if b.status == 'completed':
                pool.remove(ch)
                collect(ch)
            elif b.status in ('failed', 'expired', 'cancelled'):
                errs = []
                try:
                    d = b.errors.data if (b.errors and hasattr(b.errors, 'data')) else None
                    errs = [{'code': getattr(e, 'code', None),
                             'message': getattr(e, 'message', str(e))} for e in (d or [])]
                except Exception:
                    pass
                run_name = f"{slug}_{led['run_tag']}_c{ch['chunk']}"
                print(f"\n  [chunk {ch['chunk']}] {b.status.upper()}")
                print(f"    batch name : {run_name}")
                print(f"    batch id   : {b.id}")
                print(f"    metadata   : {dict(b.metadata or {})}")
                for e in errs[:3]:
                    print(f"    reason     : {e['code']}: {e['message']}")
                print(f"    -> records {ch['start_index']}-"
                      f"{ch['start_index']+ch.get('n_read',0)-1} queued for retry")
                log_event({'event': b.status, 'run_name': run_name, 'batch_id': b.id,
                           'metadata': dict(b.metadata or {}), 'file': rel,
                           'chunk': ch['chunk'], 'model': model,
                           'start_index': ch['start_index'], 'n_read': ch.get('n_read'),
                           'requests': ch.get('count'), 'errors': errs})
                ch['status'] = 'failed'
                ch['tokens'] = 0
                save_ledger(led)
                pool.remove(ch)
        fill()   # refill the moment slots (and tokens) free up
        if pool:
            rc = [f"c{c['chunk']}({c['prog'][0]}/{c['prog'][1]})" if c.get('prog')
                  else f"c{c['chunk']}" for c in pool]
            print(f"  ... {led['completed']}/{target} done | {len(pool)} alive: {' '.join(rc)}")

    print(f"\n=== {rel}: {led['completed']} records done -> {out_path} ===")


def main():
    ap = argparse.ArgumentParser(description="Run prompts through OpenAI Batch API.")
    ap.add_argument('--files', nargs='*', default=DEFAULT_FILES,
                    help="Input files (relative to this folder). Default: all 5.")
    ap.add_argument('--limit', type=int, default=50,
                    help="Max records to take FROM EACH FILE (default 50).")
    ap.add_argument('--model', default=DEFAULT_MODEL,
                    help=f"OpenAI model (default {DEFAULT_MODEL}).")
    ap.add_argument('--run-name', default=None, help="Name for this run's files.")
    ap.add_argument('--wait-batch', default=None,
                    help="Resume: poll this batch id, then merge using the saved sidecar. "
                         "Requires --run-name of the original run.")
    ap.add_argument('--target', type=int, default=None,
                    help="Total records to COMPLETE per file. Chunks + resumes automatically; "
                         "never resends what's done or in flight.")
    ap.add_argument('--chunk', type=int, default=DEFAULT_CHUNK,
                    help=f"Records per batch (default {DEFAULT_CHUNK}). Auto-capped to "
                         f"OpenAI's limits.")
    ap.add_argument('--concurrency', type=int, default=DEFAULT_CONCURRENCY,
                    help=f"Max batches alive at once (default {DEFAULT_CONCURRENCY}). "
                         f"The token budget may allow fewer.")
    ap.add_argument('--token-budget', type=int, default=DEFAULT_TOKEN_BUDGET,
                    help=f"Max enqueued tokens across live batches (default "
                         f"{DEFAULT_TOKEN_BUDGET}). OpenAI's org limit is 2M for "
                         f"gpt-4.1-nano; batches over it fail.")
    ap.add_argument('--status', action='store_true',
                    help="Show ledger progress for the selected files and exit.")
    ap.add_argument('--submit', action='store_true', help="Actually submit to OpenAI.")
    ap.add_argument('--wait', action='store_true', help="Poll until done + download.")
    ap.add_argument('--interval', type=int, default=60, help="Poll interval seconds.")
    ap.add_argument('--dry-run', action='store_true', help="Build JSONL only, no API.")
    args = ap.parse_args()

    run_name = args.run_name or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Status: just read the ledgers and report.
    if args.status:
        for rel in args.files:
            slug = file_slug(rel)
            p = ledger_path(slug)
            if not p.exists():
                print(f"{rel}: nothing started")
                continue
            led = json.loads(p.read_text(encoding='utf-8'))
            inflight = sum(1 for c in led['chunks'] if c['status'] == 'in_flight')
            done = sum(1 for c in led['chunks'] if c['status'] == 'done')
            pend = sum(1 for c in led['chunks'] if c['status'] == 'pending_submit')
            bad = [c['chunk'] for c in led['chunks'] if c['status'] == 'failed']
            print(f"{rel}: {led['completed']} completed | next record {led['next_index']} | "
                  f"chunks {done} done, {inflight} in flight, {pend} unresolved, "
                  f"{len(bad)} failed{' -> retried on next run: '+str(bad) if bad else ''}")
        return

    # Target mode: chunked, resumable orchestration.
    if args.target:
        load_dotenv()
        key = os.getenv('OPENAI_API_KEY')
        if not key:
            raise RuntimeError(f"OPENAI_API_KEY not set (looked in {ENV_PATH}).")
        if not args.submit:
            print("--target requires --submit (it orchestrates real batches).")
            return
        client = openai.OpenAI(api_key=key)
        for rel in args.files:
            orchestrate(client, rel, args.target, args.chunk, args.model,
                        args.interval, args.concurrency, args.token_budget)
        return

    # Resume path: poll an already-submitted batch and merge from its saved sidecar.
    if args.wait_batch:
        load_dotenv()
        key = os.getenv('OPENAI_API_KEY')
        if not key:
            raise RuntimeError(f"OPENAI_API_KEY not set (looked in {ENV_PATH}).")
        client = openai.OpenAI(api_key=key)
        sidecar_path = BATCH_DIR / f"sidecar_{run_name}.json"
        if not sidecar_path.exists():
            raise RuntimeError(f"sidecar not found: {sidecar_path} (pass the original --run-name).")
        sidecar = json.loads(sidecar_path.read_text(encoding='utf-8'))
        manifest_path = BATCH_DIR / f"manifest_{run_name}.json"
        manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
        text = wait_and_download(client, args.wait_batch, run_name, args.interval)
        if text is None:
            return
        print(f"\n=== MERGE ===")
        merge_and_write(text, sidecar, run_name, manifest)
        return

    print(f"=== BUILD (limit {args.limit}/file, model {args.model}) ===")
    requests, sidecar, manifest = build_requests(args.files, args.limit, args.model)
    print(f"total requests: {len(requests)}")
    if not requests:
        print("nothing to do.")
        return

    # persist sidecar + manifest so a later --wait can merge (and mirror the
    # input tree) even in a fresh process
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    (BATCH_DIR / f"sidecar_{run_name}.json").write_text(
        json.dumps(sidecar, ensure_ascii=False), encoding='utf-8')
    (BATCH_DIR / f"manifest_{run_name}.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding='utf-8')

    if args.dry_run or not args.submit:
        BATCH_DIR.mkdir(parents=True, exist_ok=True)
        jsonl_path = BATCH_DIR / f"requests_{run_name}.jsonl"
        with open(jsonl_path, 'w', encoding='utf-8') as f:
            for req in requests:
                f.write(json.dumps(req, ensure_ascii=False) + '\n')
        print(f"\n[dry-run] wrote {jsonl_path}")
        print("[dry-run] no API call made. Re-run with --submit --wait to send.")
        return

    load_dotenv()
    key = os.getenv('OPENAI_API_KEY')
    if not key:
        raise RuntimeError(f"OPENAI_API_KEY not set (looked in {ENV_PATH}).")
    client = openai.OpenAI(api_key=key)

    print(f"\n=== SUBMIT ({run_name}) ===")
    batch_id = submit(client, requests, run_name)

    if not args.wait:
        print(f"\nsubmitted. Resume later with: --wait-batch {batch_id} --run-name {run_name}")
        return

    text = wait_and_download(client, batch_id, run_name, args.interval)
    if text is None:
        return
    print(f"\n=== MERGE ===")
    merge_and_write(text, sidecar, run_name, manifest)


if __name__ == '__main__':
    main()
