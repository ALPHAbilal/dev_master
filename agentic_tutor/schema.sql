-- Agentic Tutor — the 7-table schema (docs/tutor-simulation.md Part B).
-- The whole trajectory lives in the library (*.md); these tables hold only
-- evidence, the bank, the slices, and the gate. No global `phase` row.

PRAGMA foreign_keys = ON;

-- The codebase being built. The spine itself lives ONLY in `slices` (ordinal
-- order) — storing it twice was redundancy; the slices table IS the decomposition.
CREATE TABLE IF NOT EXISTS target (
    id             INTEGER PRIMARY KEY CHECK (id = 1),   -- single row
    codebase_path  TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Each real function/file the learner must write. THE UNIT OF PROGRESS.
CREATE TABLE IF NOT EXISTS slices (
    slug            TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    target_file     TEXT NOT NULL,
    spec_path       TEXT,                                -- library/slices/<slug>.md
    state           TEXT NOT NULL DEFAULT 'LOCKED'
                        CHECK (state IN ('LOCKED','READY','BUILT')),
    kind            TEXT NOT NULL DEFAULT 'function'
                        CHECK (kind IN ('function','capstone')),
    concept_prereqs TEXT,                                -- JSON: [concept_slug, ...]
    ordinal         INTEGER,                             -- position on the spine
    -- subhole handoff cells (F4): filled by L, cleared by M. Empty = no subhole.
    subhole_concept  TEXT,
    subhole_evidence TEXT,
    subhole_plan     TEXT,
    built_at        TEXT
);

-- The concept bank = DAG nodes + mastery overlay.
CREATE TABLE IF NOT EXISTS concepts (
    slug        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    definition  TEXT,
    aspect      TEXT,                                    -- lang/stdlib/design/...
    state       TEXT NOT NULL DEFAULT 'LOCKED'
                    CHECK (state IN ('OWNED','READY','LOCKED')),
    requires    TEXT                                     -- JSON: [concept_slug, ...] (DAG edges)
);

-- The blank-page wall. While OPEN: learner can't read spec, agent can't write target.
-- No copied paths: the wall JOINS to slices for target_file/spec_path, so it can
-- never enforce a stale copy of them.
CREATE TABLE IF NOT EXISTS gates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slice_slug  TEXT NOT NULL REFERENCES slices(slug),
    state       TEXT NOT NULL DEFAULT 'OPEN'
                    CHECK (state IN ('OPEN','PASSED','FAILED')),
    opened_at   TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at   TEXT
);

-- The evidence M reads. One row per judged answer. The ONLY L->M channel.
-- Absorbs old attempts/stalls/reviews as `kind`.
CREATE TABLE IF NOT EXISTS probes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    concept_slug   TEXT,                                 -- may be a slice slug for kind=build
    kind           TEXT NOT NULL
                       CHECK (kind IN ('predict','produce','build','stall','review')),
    result         TEXT NOT NULL CHECK (result IN ('HIT','PARTIAL','MISS')),
    pushes         INTEGER NOT NULL DEFAULT 0,
    self_corrected INTEGER NOT NULL DEFAULT 0,           -- 0/1
    error_class    TEXT,
    reveals        TEXT,                                 -- the worth-failing-at diagnosis label
    terms          TEXT,                                 -- JSON or csv
    note           TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- The intuition unit: trigger + solution + why. polarity=negative = a misconception.
CREATE TABLE IF NOT EXISTS mappings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    concept_slug TEXT NOT NULL,
    polarity     TEXT NOT NULL DEFAULT 'positive'
                     CHECK (polarity IN ('positive','negative')),
    trigger      TEXT NOT NULL,
    solution     TEXT NOT NULL,
    why          TEXT NOT NULL,
    provenance   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- The door: every term shown. A question may not use an unshown/held term.
CREATE TABLE IF NOT EXISTS vocab (
    term       TEXT PRIMARY KEY,
    state      TEXT NOT NULL DEFAULT 'unknown'
                   CHECK (state IN ('unknown','hold','shown','proved')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Tiny kv for identity + pointers (active slice, turn counters). NOT a phase row.
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
