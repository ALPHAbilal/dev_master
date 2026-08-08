#!/usr/bin/env python3
"""FR->EN translation runner.

Thin wrapper around run_prompts.py. It sets the three things that make a run a
TRANSLATION run rather than a generation run, then hands over to the same proven
orchestrator (ledger, resume, chunking, IP-failure guard, partial-failure
detection). Everything else -- batching, retries, progress -- is unchanged.

  1. the system prompt        -> translation instructions instead of generation
  2. the output folder        -> translations/ instead of responses/
  3. max output tokens        -> 4500, because the longest records translate to
                                 slightly over the 3000 used for generation and
                                 would otherwise be cut off SILENTLY (OpenAI
                                 reports a truncated answer as a success)

Usage is identical to run_prompts.py:

    python run_translation.py --files translate_src/marche/prompts_type1_pays_marche.json \
        --target 37 --submit --chunk 100 --concurrency 10 --token-budget 1900000
"""
import os

# Must be set BEFORE run_prompts is imported: it reads these at module load.
os.environ['PROMPT_SYSTEM'] = (
    "Translate this French recruitment content into US English.\n\n"
    "- Translate fully: never summarize, condense, or omit. "
    "Keep comparable length.\n"
    "- Natural, idiomatic US English and US spelling.\n"
    "- Keep place names and AfricaWork exactly as written.\n"
    "- Return the same JSON structure; translate values only, keep all keys."
)
os.environ['PROMPT_OUT_DIR'] = 'translations'
os.environ.setdefault('PROMPT_MAX_TOKENS', '4500')

import run_prompts  # noqa: E402  (import after env is set, on purpose)

if __name__ == '__main__':
    print('=== TRANSLATION RUN (FR -> US EN) ===')
    print(f'  output folder : {run_prompts.OUT_DIR.name}/')
    print(f'  max out tokens: {run_prompts.MAX_TOKENS}')
    print(f'  model         : {run_prompts.DEFAULT_MODEL}')
    run_prompts.main()
