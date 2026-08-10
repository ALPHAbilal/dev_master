# CONCEPT BANK — built from soufiane_prompts/prompts/ (10 .py files, 2185 lines)

153 concepts. 96 on the ladder (depth 1-2). 57 parked (depth 3+).
Every row points at real code you already have. state=CANT means NOT YET MEASURED.

## THE LADDER — 96, routable

### depth 1  (49)

| slug | name | where it lives | what it is |
|---|---|---|---|
| `print-call` | Function call | prompts/hello.py:1 | Invoking a callable with arguments; print() writes to stdout |
| `string-literal` | String literal and quoting | prompts/hello.py:2 | Text between matching quotes; an unbalanced quote is a SyntaxError |
| `variable-assignment` | Assignment / name binding | prompts/run_prompts.py:676 | `name = value` binds a name to an object; also `a, b = [], {}` |
| `tuple-unpacking` | Tuple unpacking | prompts/run_prompts.py:52 | Splitting a sequence across several names in one statement |
| `augmented-assignment` | Augmented assignment | prompts/run_prompts.py:399 | `x += n` rebinds x to x + n |
| `function-def` | Function definition | prompts/run_prompts.py:44 | `def name(params):` creates a callable |
| `function-return` | return | prompts/run_prompts.py:466 | Hands a value back and ends the call; falling off the end returns None |
| `default-arguments` | Default parameter values | prompts/run_prompts.py:820 | A parameter with a fallback used when the caller omits it |
| `keyword-arguments` | Keyword arguments | prompts/run_prompts.py:560 | Passing arguments by name at the call site |
| `import-module` | import | prompts/run_prompts.py:27 | Loads another module and binds its name |
| `from-import` | from X import Y | prompts/run_prompts.py:34 | Binds one name out of a module directly |
| `if-else` | if / elif / else | prompts/run_prompts.py:311 | Branching on a condition |
| `comparison-operators` | Comparison operators | prompts/run_prompts.py:209 | ==, !=, <, >=, and chained comparisons like 1 <= i <= 5 |
| `boolean-operators` | and / or / not | prompts/run_prompts.py:49 | Boolean logic with short-circuit evaluation |
| `truthiness` | Truthiness | prompts/run_prompts.py:519 | '' [] {} 0 None are false; `if not prompt` tests emptiness |
| `none-identity` | None and `is` | prompts/run_prompts.py:224 | The null object, tested with `is` rather than `==` |
| `ternary-expression` | Conditional expression | prompts/build_translation_sources.py:71 | `a if cond else b` used as a value |
| `for-loop` | for over an iterable | prompts/run_prompts.py:48 | Runs a block once per item |
| `while-loop` | while loop | prompts/run_prompts.py:363 | Repeats while a condition holds |
| `break-continue` | break / continue | prompts/run_prompts.py:378 | Leave the loop entirely / skip to the next iteration |
| `range` | range() | prompts/run_prompts.py:106 | A lazy sequence of integers; range(1, 6) is 1..5 |
| `list-basics` | Lists: literal, append, len | prompts/run_prompts.py:714 | Ordered mutable sequence |
| `indexing` | Indexing, including negative | prompts/run_prompts.py:812 | seq[0], seq[-1] |
| `slicing` | Slicing | prompts/run_prompts.py:245 | seq[a:b], seq[:1], seq[5:] — half-open ranges |
| `dict-basics` | Dicts: literal and [key] | prompts/run_prompts.py:114 | Key to value mapping; missing key raises KeyError |
| `dict-get-default` | dict.get(key, default) | prompts/run_prompts.py:519 | Lookup that returns None (or a default) instead of raising |
| `dict-setdefault` | setdefault | prompts/run_prompts.py:652 | Insert-if-absent, then return the value |
| `dict-items` | Iterating .items() | prompts/run_prompts.py:645 | Walking keys and values together |
| `set-basics` | Sets and set difference | prompts/run_prompts.py:880 | Unique membership; `set(a) - set(b)` finds what is absent |
| `tuple-basics` | Tuples | prompts/run_prompts.py:718 | Immutable sequence; how a function returns several values |
| `fstring` | f-strings | prompts/run_prompts.py:466 | Expression interpolation inside a string literal |
| `format-spec` | Format specs in f-strings | prompts/check_content_quality.py:210 | {v:>9,} {pct:5.2f} — width, thousands separator, precision |
| `string-methods` | str methods | prompts/run_prompts.py:53 | strip, split, replace, startswith, lower, join |
| `len-builtin` | len() | prompts/run_prompts.py:203 | Number of items in a sequence |
| `min-max-sum` | min / max / sum | prompts/run_prompts.py:779 | Aggregates over an iterable |
| `type-casting` | int() float() str() | prompts/run_prompts.py:62 | Converting between types; env vars arrive as strings |
| `int-division-modulo` | // and % | prompts/run_prompts.py:585 | Floor division and remainder |
| `enumerate` | enumerate() | prompts/run_prompts.py:518 | Index and item together |
| `zip` | zip() | prompts/sample_translations.py:103 | Walks two sequences in step |
| `any-all` | any() / all() | prompts/run_prompts.py:224 | Is any / is every element true |
| `sorted-key` | sorted(..., key=) | prompts/check_content_quality.py:219 | Sorting by a computed value |
| `lambda` | lambda | prompts/check_quality.py:35 | An anonymous single-expression function |
| `list-comprehension` | List comprehension | prompts/run_prompts.py:233 | Builds a list from an iterable in one expression |
| `comprehension-filter` | Comprehension with a condition | prompts/run_prompts.py:774 | `[x for x in xs if cond]` |
| `generator-expression` | Generator expression | prompts/build_translation_sources.py:84 | The lazy form; `sum(f(x) for x in xs)` |
| `set-comprehension` | Set comprehension | prompts/run_prompts.py:879 | `{f(x) for x in ...}` building a set |
| `comment-docstring` | Comments and docstrings | prompts/run_prompts.py:2 | `#` and the triple-quoted string at the top of a module or function |
| `main-guard` | if __name__ == '__main__' | prompts/run_prompts.py:1276 | Runs only when executed directly, not when imported |
| `sys-argv` | sys.argv | prompts/test_egress_ips.py:24 | The raw command-line arguments list |

### depth 2  (47)

| slug | name | where it lives | what it is |
|---|---|---|---|
| `try-except` | try / except | prompts/run_prompts.py:387 | Catching an exception instead of crashing |
| `except-tuple-as` | except (A, B) as e | prompts/run_prompts.py:749 | Catching several classes and binding the exception object |
| `raise-exception` | raise | prompts/run_prompts.py:1201 | Raising an error deliberately, with a message |
| `swallowed-exception` | except Exception: pass | prompts/run_prompts.py:847 | Deliberately ignoring an error — and what it costs |
| `optional-import` | try: import / except ImportError | prompts/run_prompts.py:341 | An optional dependency with a working fallback |
| `context-manager` | with statement | prompts/run_prompts.py:360 | Scoped acquire and release; the file closes even on an error |
| `open-modes` | open() modes and encoding | prompts/run_prompts.py:758 | 'r' 'w' 'a' 'rb' 'r+b', and why encoding='utf-8' is written explicitly |
| `file-iteration` | Iterating a file by line | prompts/check_content_quality.py:136 | `for line in f` streams without loading the file |
| `file-read-chunks` | f.read(n) | prompts/run_prompts.py:365 | Reading a fixed number of characters or bytes |
| `file-seek-offsets` | seek() and byte offsets | prompts/run_prompts.py:423 | Positioning inside a binary file; text-mode tell() is not a byte count |
| `file-truncate` | truncate() | prompts/run_prompts.py:984 | Cutting a file back to a given length |
| `generator-function` | yield / generator function | prompts/run_prompts.py:398 | A function that produces values lazily, one at a time |
| `yield-tuple` | Yielding several values | prompts/run_prompts.py:460 | `yield obj, base` — each step hands back a pair |
| `nested-function` | Nested function | prompts/run_prompts.py:417 | A def inside a def, using the outer function's variables |
| `nonlocal` | nonlocal | prompts/run_prompts.py:419 | Rebinding a variable owned by the enclosing function |
| `module-constants` | Module-level constants | prompts/run_prompts.py:326 | Uppercase names set once at import and read everywhere |
| `isinstance` | isinstance() | prompts/check_content_quality.py:151 | Runtime type test |
| `getattr-default` | getattr(obj, name, default) | prompts/run_prompts.py:813 | Attribute access that cannot raise |
| `implicit-concatenation` | Implicit string concatenation | prompts/run_prompts.py:70 | Adjacent string literals across lines join into one |
| `raw-strings` | Raw strings r'...' | prompts/run_prompts.py:174 | Backslashes taken literally — why regexes use them |
| `bytes-vs-str` | encode() / decode() | prompts/run_prompts.py:594 | Bytes and text are different types; the boundary is explicit |
| `import-own-module` | Importing your own module | prompts/check_content_quality_gen.py:22 | `import run_prompts as rp` to reuse its functions instead of copying them |
| `pathlib-path` | pathlib.Path | prompts/run_prompts.py:39 | Filesystem paths as objects instead of strings |
| `path-operator` | Path / 'sub' | prompts/run_prompts.py:41 | Building paths with the division operator |
| `path-parts` | stem / parent / parts / name | prompts/run_prompts.py:613 | Decomposing a path into its pieces |
| `path-mkdir` | mkdir(parents=True, exist_ok=True) | prompts/run_prompts.py:616 | Creating a directory tree idempotently |
| `path-text-io` | read_text / write_text | prompts/run_prompts.py:492 | Whole-file text IO in one call |
| `path-exists-stat` | exists() and stat().st_size | prompts/run_prompts.py:870 | Testing for a file and measuring its size |
| `os-environ` | os.environ / os.getenv | prompts/run_prompts.py:61 | Reading and writing environment variables |
| `environ-setdefault` | os.environ.setdefault | prompts/run_prompts.py:53 | Set only if unset — 'the real environment wins' |
| `json-dumps-loads` | json.dumps / json.loads | prompts/run_prompts.py:553 | Python object to JSON text and back |
| `json-options` | ensure_ascii and indent | prompts/run_prompts.py:492 | Keeping accents literal; pretty-printing |
| `jsonl-format` | JSON Lines | prompts/run_prompts.py:790 | One complete JSON object per line — appendable, streamable |
| `re-compile-findall` | re.compile / findall | prompts/run_prompts.py:174 | A compiled pattern and every match in a string |
| `regex-groups` | Capture groups | prompts/run_prompts.py:202 | Parentheses, so findall returns tuples of the captured parts |
| `regex-search-group` | re.search().group(n) | prompts/check_quality.py:35 | Pulling one value out of a string that mostly matches |
| `argparse-basics` | argparse | prompts/run_prompts.py:1144 | Declaring command-line flags and parsing them |
| `argparse-options` | type= default= action='store_true' nargs='*' | prompts/run_prompts.py:1147 | The shapes a flag can take |
| `counter` | collections.Counter | prompts/run_prompts.py:916 | Counting occurrences of things |
| `hashlib-md5` | hashlib.md5(...).hexdigest() | prompts/check_content_quality.py:120 | A short fingerprint standing in for a long value |
| `uuid4` | uuid.uuid4().hex | prompts/run_prompts.py:481 | A random unique identifier |
| `time-module` | time.time / time.sleep / strftime | prompts/run_prompts.py:583 | Elapsed time, waiting, and clock formatting |
| `datetime-now` | datetime.now().isoformat() | prompts/run_prompts.py:1176 | Timestamps for logs and filenames |
| `random-sample` | random.sample / random.seed | prompts/sample_translations.py:67 | Sampling without replacement, reproducibly |
| `glob` | glob.glob | prompts/check_quality.py:34 | Finding files by wildcard pattern |
| `sys-exit` | sys.exit / SystemExit | prompts/check_quality.py:101 | Ending the program with a status and a message |
| `print-flush` | print(..., flush=True) | prompts/check_content_quality.py:108 | Forcing output out during a long-running pass |

## PARKED — 57, off the ladder, the rebuild checklist

### depth 3  (23)

| slug | name | where it lives | what it is |
|---|---|---|---|
| `batch-api` | OpenAI Batch API | prompts/run_prompts.py:560 | Upload a JSONL of requests, create a batch, poll, download results |
| `poll-and-download` | Poll then download | prompts/run_prompts.py:576 | Retrieve status on an interval, then fetch the output file |
| `json-object-fallback` | json_object fallback mode | prompts/run_prompts.py:313 | Guarantees valid JSON but not the key layout, for unknown files |
| `determinism-params` | Determinism parameters | prompts/run_prompts.py:62 | temperature=0, top_p=1, seed — reproducibility, not creativity |
| `max-completion-tokens` | max_completion_tokens | prompts/run_prompts.py:536 | The output cap; too low truncates silently |
| `token-counting` | Token counting with tiktoken | prompts/run_prompts.py:343 | Measuring input size before sending, to price a batch |
| `system-vs-user-message` | System vs user message | prompts/run_prompts.py:531 | Role separation: standing rules vs the record's own content |
| `staging-directory` | Staging directory | prompts/run_prompts.py:611 | translate_src/ is how the input was prepared and is stripped from the output |
| `module-as-library` | Script as importable library | prompts/check_quality.py:14 | check_quality imports run_prompts to reuse its extractor |
| `dotenv-loading` | Loading a .env by hand | prompts/run_prompts.py:44 | Parsing KEY=value out of a file into the environment |
| `cli-modes` | Multiple modes in one CLI | prompts/run_prompts.py:1179 | --status, --target, --wait-batch and the default build path |
| `error-classification` | Error classification in reports | prompts/run_prompts.py:917 | Group failures by code rather than printing a count |
| `exception-string-matching` | Matching on an error string | prompts/run_prompts.py:960 | Branching on 'token_limit_exceeded' in str(e) — and why that is fragile |
| `correlation-id` | Correlation ID | prompts/run_prompts.py:523 | A custom_id carried through so a response can be matched to its request |
| `sidecar-store` | Sidecar record store | prompts/run_prompts.py:955 | The original records saved beside the request file, for the merge |
| `manifest` | Manifest | prompts/run_prompts.py:516 | slug to original path, so the output tree mirrors the input tree |
| `structured-event-log` | Structured event log | prompts/run_prompts.py:785 | One JSON line per event, permanent, queryable after the fact |
| `output-tree-mirroring` | Output tree mirroring | prompts/run_prompts.py:602 | Output paths derived from input paths, same folders plus a suffix |
| `fingerprint-compare` | Fingerprint comparison | prompts/check_content_quality.py:182 | Compare md5 of the joined questions instead of ten string compares |
| `normalize-before-compare` | Normalize before comparing | prompts/check_content_quality.py:51 | Strip escape artifacts and collapse whitespace, or every compare is a false alarm |
| `sampling-for-review` | Sampling for human review | prompts/sample_translations.py:90 | Random pairs written to a readable txt so a person can judge quality |
| `concurrent-probing` | ThreadPoolExecutor for IO probes | prompts/test_egress_ips.py:42 | Running many blocking network calls at once to sample a distribution |
| `raw-https-client` | Raw HTTPS without a library | prompts/test_egress_ips.py:33 | http.client + ssl, to control the connection instead of reusing a pool |

### depth 4  (26)

| slug | name | where it lives | what it is |
|---|---|---|---|
| `structured-outputs` | Structured Outputs (json_schema) | prompts/run_prompts.py:308 | A response_format that forces the model to emit an exact structure |
| `strict-schema-mode` | strict mode / additionalProperties | prompts/run_prompts.py:112 | required on every key and no extra keys permitted |
| `enqueued-token-cap` | Enqueued-token org limit | prompts/run_prompts.py:336 | A per-org cap on tokens in flight; exceeding it fails batches outright |
| `config-injection-wrapper` | Config injection via a wrapper | prompts/run_translation.py:24 | Set env vars, then import the module that reads them at load time |
| `load-order-dependency` | Load-order dependency | prompts/run_prompts.py:56 | Config read at import time must be set before the import happens |
| `pipeline-stages` | Named pipeline stages | prompts/run_prompts.py:10 | LOADER, BUILDER, SUBMIT, POLL, DOWNLOAD, MERGER, OUTPUT |
| `retry-queue` | Retry-before-advance | prompts/run_prompts.py:1061 | Failed work is re-sent before any new work is started |
| `stale-artifact-guard` | Stale-artifact guard | prompts/check_quality.py:28 | Only grade chunks the ledger marks done; a resent chunk leaves old results on disk |
| `counter-drift-check` | Counter-drift check | prompts/check_quality.py:125 | The ledger's count must agree with the rows actually on disk |
| `fail-safe-default` | Fail-safe default | prompts/run_prompts.py:197 | The extractor returns None on anything unexpected; the caller falls back |
| `partial-failure-accounting` | Partial-failure accounting | prompts/run_prompts.py:877 | Some requests in a batch fail; the good ones are kept and the rest logged |
| `poison-record-isolation` | Poison-record isolation | prompts/run_prompts.py:882 | Failing records are written to MISSING_records.txt, not retried forever |
| `silent-truncation-detection` | Silent-truncation detection | prompts/run_prompts.py:910 | finish_reason='length' means the answer was cut off and reported as success |
| `empty-output-guard` | Completed-but-empty guard | prompts/run_prompts.py:840 | A batch can be 'completed' with every request failed and no output file |
| `source-data-artifact` | Working around a source-data artifact | prompts/run_prompts.py:216 | A SQL escape backslash silently truncates constrained decoding, so it is stripped |
| `ip-allowlist-egress` | IP allowlist and unstable egress | prompts/test_egress_ips.py:27 | Batches rejected at random because the machine leaves from more than one public IP |
| `streaming-json-array` | Streaming a JSON array | prompts/run_prompts.py:350 | Decoding one object at a time so a 2.3 GB file never enters memory |
| `buffer-refill-loop` | Buffer refill on partial parse | prompts/run_prompts.py:389 | On JSONDecodeError, read more bytes and retry rather than fail |
| `byte-offset-checkpoint` | Byte-offset checkpointing | prompts/run_prompts.py:402 | Saving the exact byte position so the next run resumes without rescanning |
| `ledger` | Ledger / durable run state | prompts/run_prompts.py:469 | A JSON file recording what is done, in flight, and where to resume |
| `idempotent-append` | Idempotent append | prompts/run_prompts.py:758 | Re-running must not duplicate rows |
| `run-tag-namespacing` | Run-tag namespacing | prompts/run_prompts.py:481 | A random tag in every name so a fresh run cannot collide with a discarded one |
| `chunk-sizing` | Chunk sizing against API limits | prompts/run_prompts.py:667 | Building a batch that stops before the request-count and byte limits |
| `natural-key-upsert` | Upsert by natural key | prompts/splice_regen.py:21 | Match on (type, job_id, country_id, region_id), never on line position |
| `two-pass-grading` | Two-pass index-then-grade | prompts/check_content_quality.py:107 | Pass 1 indexes the source, pass 2 grades the output against it |
| `incremental-utf8-decode` | Incremental UTF-8 decoding | prompts/run_prompts.py:413 | Decoding text that arrives split mid-character across reads |

### depth 5  (8)

| slug | name | where it lives | what it is |
|---|---|---|---|
| `enum-pinning` | Enum pinning a generated value | prompts/run_prompts.py:258 | A single-value enum makes any other text impossible for the decoder to emit |
| `orchestrator` | Orchestrator | prompts/run_prompts.py:819 | One function owning chunk -> submit -> wait -> merge -> next chunk |
| `crash-recovery-rewind` | Rewind-on-restart recovery | prompts/run_prompts.py:978 | Truncate the output back to a pre-merge mark so rows cannot land twice |
| `intent-before-action` | Write the intent before the action | prompts/run_prompts.py:1088 | Record 'about to send' before calling the API so a crash is resolvable |
| `reconciliation` | Reconciliation against the remote | prompts/run_prompts.py:998 | Ask the provider what actually happened rather than guessing |
| `bounded-worker-pool` | Bounded worker pool | prompts/run_prompts.py:1099 | A fixed number of jobs alive at once, refilled as each lands |
| `admission-control` | Admission control on a token budget | prompts/run_prompts.py:1066 | Pricing a job before recording it, so the org token cap is never exceeded |
| `monotonic-frontier` | Monotonic cursor | prompts/run_prompts.py:969 | A retried old chunk must never drag the frontier backwards |
