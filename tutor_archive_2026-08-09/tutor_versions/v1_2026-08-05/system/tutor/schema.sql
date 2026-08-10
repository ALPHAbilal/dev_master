-- Tutor state. One database, one source of truth.
-- Anything gradeable is a concept. Anything that happened is a probe.

PRAGMA journal_mode = WAL;

-- ---- session counter -----------------------------------------------------
-- Every agent, on its FIRST interaction of a conversation, inserts one row.
-- COUNT(*) is therefore "how many past interactions has this learner had",
-- which any agent can read to know it is not the first one here.
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    agent       TEXT,              -- model / agent name
    dir         TEXT,              -- working directory
    note        TEXT               -- what this session was for
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- ---- the question bank / the map ----------------------------------------
-- Populated by `/tutor concepts <dir>` from the learner's OWN code.
-- The code enumerates the unknowns so the agent never has to guess them.
CREATE TABLE IF NOT EXISTS concepts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,     -- the INDUSTRY name; this is the point
    definition  TEXT NOT NULL,     -- one line, plain
    category    TEXT NOT NULL,     -- language|stdlib|pattern|failure|api|arch
    depth       INTEGER NOT NULL,  -- 1 primitive .. 5 architecture
    file        TEXT,              -- where it lives in HIS code
    line        INTEGER,
    snippet     TEXT,

    state       TEXT NOT NULL DEFAULT 'UNKNOWN',  -- UNKNOWN|SEEN|EXPLAINED|APPLIED
    evidence    TEXT NOT NULL DEFAULT 'none',     -- none|assisted|unaided|transferred
    source      TEXT NOT NULL DEFAULT 'code',     -- code|spine; spine = never in his code
    explanation TEXT,                             -- written ONCE by teach, reused forever
    taught_in   INTEGER REFERENCES sessions(id),
    attempts    INTEGER NOT NULL DEFAULT 0,
    fails       INTEGER NOT NULL DEFAULT 0,
    next_review TEXT,
    requires    TEXT,              -- comma-separated slugs
    gate        TEXT,              -- what unaided output proves APPLIED
    swept_in    INTEGER REFERENCES sessions(id),  -- NULL = never swept
    updated_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_concepts_state ON concepts(state);
CREATE INDEX IF NOT EXISTS idx_concepts_depth ON concepts(depth);
CREATE INDEX IF NOT EXISTS idx_concepts_review ON concepts(next_review);

-- ---- what was actually asked and answered --------------------------------
CREATE TABLE IF NOT EXISTS probes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    concept_id  INTEGER REFERENCES concepts(id),
    phase       TEXT NOT NULL,     -- SWEEP|DESCEND|DRILL|REBUILD|BUILD|TEACH|BREAK|TRANSFER
    faculty     TEXT NOT NULL DEFAULT 'write',
                                   -- write|read|debug|recall|design|vocabulary
                                   -- the axis under test. no faculty, no radar.
    depth_below INTEGER NOT NULL DEFAULT 0,  -- levels below the original miss
    question    TEXT NOT NULL,
    answer      TEXT,              -- what he actually said, verbatim-ish
    result      TEXT NOT NULL,     -- HIT|MISS|PARTIAL
    seconds     INTEGER,           -- time to answer. "short time" needs an instrument.
    asked_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_probes_session ON probes(session_id);
CREATE INDEX IF NOT EXISTS idx_probes_concept ON probes(concept_id);
CREATE INDEX IF NOT EXISTS idx_probes_faculty ON probes(faculty);
CREATE INDEX IF NOT EXISTS idx_concepts_source ON concepts(source);

-- ---- gates: the blank page, currently open --------------------------------
-- Hooks read this table. A rule that lives only in prose holds until the
-- context gets long; a rule that lives here is enforced by the harness.
-- While a row has closed_at IS NULL: Read of spec_path is blocked, and the
-- agent writing `target` is blocked. He produces, or it did not happen.
CREATE TABLE IF NOT EXISTS gates (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    concept_id INTEGER NOT NULL REFERENCES concepts(id),
    kind       TEXT NOT NULL,   -- rebuild|build|transfer
    spec_path  TEXT,            -- the file he must NOT read while this is open
    target     TEXT,            -- the file he writes
    opened_at  TEXT NOT NULL,
    closed_at  TEXT,
    result     TEXT             -- PASS|FAIL|ABANDONED
);

CREATE INDEX IF NOT EXISTS idx_gates_open ON gates(closed_at);

-- ---- learners: the operating rules, out of the prose ----------------------
-- SKILL.md is a router. How to treat THIS learner lives here and is injected
-- by the SessionStart hook, so no agent can start without it.
CREATE TABLE IF NOT EXISTS learners (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    rules      TEXT NOT NULL,
    active     INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- ---- floors: the bottom of a descent -------------------------------------
-- The concept he DID answer, below a cluster of misses. Teach up from here.
CREATE TABLE IF NOT EXISTS floors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    concept_id  INTEGER NOT NULL REFERENCES concepts(id),
    explains    TEXT,              -- comma-separated slugs this root explains
    descents    INTEGER,           -- how many levels it took
    found_at    TEXT NOT NULL
);

-- ---- ladder revisions, append-only ---------------------------------------
CREATE TABLE IF NOT EXISTS ladder_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,
    trigger  TEXT NOT NULL,        -- LADDER|BLIND_SPOT|TOO_WIDE|ALREADY_HAD|LEVERAGE
    evidence TEXT NOT NULL,
    change   TEXT NOT NULL
);
