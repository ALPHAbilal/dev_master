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

    state       TEXT NOT NULL DEFAULT 'CANT',    -- v2: CANT|CAN. Two states only:
                                                  -- SEEN/EXPLAINED triggered no
                                                  -- decision in 12 sessions.
    state_v1    TEXT,              -- v1's four-state value, preserved, never rewritten
    parked      INTEGER NOT NULL DEFAULT 0,       -- 1 = off the ladder (depth 3+),
                                                  -- still in the bank, invisible to routing
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
    error_class TEXT,              -- gap|syntax|typo|bleed|fatigue. Required on any
                                   -- non-HIT: a typo and a missing concept are not
                                   -- the same event and must not demote alike.
    seconds     INTEGER,           -- elapsed. MEANING DEPENDS ON `clock`, below.
    clock       TEXT NOT NULL DEFAULT 'unmeasured',
                                   -- HOW seconds was obtained. The clock is a
                                   -- SUBTRACTION, never a question put to him.
                                   --   measured    t_answer - t_ask, one live
                                   --               question. Trustworthy.
                                   --   batch       one `ask` covered N questions;
                                   --               seconds is the WHOLE span,
                                   --               repeated. NEVER divide it.
                                   --   away        measured but over the cap --
                                   --               he left the desk. Not recall.
                                   --   unmeasured  nobody stamped it. seconds is
                                   --               NULL, and that is CORRECT.
                                   -- v1 left seconds NULL in all 73 rows and knew
                                   -- it was blind. v2 forced a number, so the agent
                                   -- asked him and he said "around 30 minitues" for
                                   -- fifteen questions and it divided. Fiction that
                                   -- looks like data is worse than a known hole.
    asked_at    TEXT NOT NULL
);

-- ---- asks: a clock that is running -----------------------------------------
-- Opened when the agent puts a question on screen, consumed by the matching
-- probe. One row may cover many slugs (a sweep worksheet is ONE clock).
CREATE TABLE IF NOT EXISTS asks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    slugs      TEXT NOT NULL,      -- comma separated; >1 means batch
    phase      TEXT,
    faculty    TEXT,
    asked_at   TEXT NOT NULL,
    closed_at  TEXT                -- set when the last slug has been probed
);
CREATE INDEX IF NOT EXISTS idx_asks_open ON asks(closed_at);

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

-- ---- v2: the learner's artifacts, kept ------------------------------------
-- He edits one file. Copying, numbering and diffing it is the AGENT's job.
-- v1 graded log.md in place; it was overwritten ~21 times and 252 bytes
-- survived six days. The diff between attempt 1 and attempt 4 IS the learning.
CREATE TABLE IF NOT EXISTS attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    concept_id  INTEGER REFERENCES concepts(id),
    phase       TEXT NOT NULL,          -- FLOOR|READ|BUILD_V1|BUILD_V2
    slug        TEXT NOT NULL,
    n           INTEGER NOT NULL,       -- 1,2,3... per (phase, slug)
    src_path    TEXT NOT NULL,          -- the file he edits
    stored_path TEXT NOT NULL,          -- the immutable copy
    sha         TEXT NOT NULL,
    bytes       INTEGER NOT NULL,
    lines       INTEGER NOT NULL,
    diff_prev   TEXT,
    added       INTEGER,
    removed     INTEGER,
    result      TEXT,
    seconds     INTEGER,                -- wall clock since the previous attempt
    taken_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attempts_slug ON attempts(phase, slug, n);
CREATE UNIQUE INDEX IF NOT EXISTS idx_attempts_sha ON attempts(phase, slug, n);

-- ---- v2: stated prerequisites, and the vetoes ------------------------------
-- All three v1 ladder repairs trace to an assumption the agent never said out
-- loud. The third surfaced only because the learner asked why it had not been
-- detected. Catching that must not depend on him noticing.
CREATE TABLE IF NOT EXISTS assumptions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    teaching    TEXT NOT NULL,
    assumed     TEXT NOT NULL,
    vetoed      TEXT,
    declared_at TEXT NOT NULL
);

-- ---- v2.1: misconceptions -- the shape of how he is wrong ------------------
-- A floor says WHERE on the ladder to teach. A misconception says WHAT FALSE
-- THING he believes, and it is not tied to one rung: it resurfaces in concepts
-- that share no prerequisite.
--
-- Evidenced by his own reading of log.md, 2026-08-06: the agent wrote "this is
-- the None idea again, in different clothes" -- a correct cross-concept
-- observation that no table could hold, so it survived only because he happened
-- to paste the transcript into the repo. He asked why the system does not
-- detect this itself. It is the same failure the assumptions table was built
-- for: catching it must not depend on him noticing.
--
-- A misconception is NOT a concept. It never enters the bank, is never
-- promoted, and cannot be "taught" -- it is disproved by production that does
-- not exhibit it.
CREATE TABLE IF NOT EXISTS misconceptions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    belief      TEXT NOT NULL,     -- the false sentence he behaves as if true
    correction  TEXT NOT NULL,     -- the true one, in the same words
    aspect      TEXT NOT NULL,     -- language|engineering|data|api|process
    opened_in   INTEGER NOT NULL REFERENCES sessions(id),
    opened_at   TEXT NOT NULL,
    state       TEXT NOT NULL DEFAULT 'OPEN',   -- OPEN|RETIRED
    retired_at  TEXT,
    retired_evidence TEXT          -- the unaided artifact that did NOT exhibit it
);

-- Every resurfacing. Two hits on unrelated concepts is what makes it a pattern
-- rather than a miss; the count is the evidence that it is still alive.
CREATE TABLE IF NOT EXISTS misconception_hits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    misconception_id INTEGER NOT NULL REFERENCES misconceptions(id),
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    probe_id    INTEGER REFERENCES probes(id),
    concept     TEXT,              -- slug it surfaced under, if any
    note        TEXT NOT NULL,     -- what he actually wrote, verbatim-ish
    ts          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mis_hits ON misconception_hits(misconception_id);

-- ---- v2.2: lookups -- the agent's own uncertainty, in the open --------------
-- An engineer is not someone who knows; it is someone who knows what they do
-- not know and has a procedure for it. A tutor that is always fluent teaches
-- the opposite lesson silently, every session.
--
-- So uncertainty is not hidden and not hedged: it is named, searched in front
-- of him with the strategy said out loud, and the correction is stated as a
-- correction. `corrected` holds the thing the agent had said that was WRONG --
-- the most valuable row in this table, and the one an agent will be tempted to
-- leave NULL.
CREATE TABLE IF NOT EXISTS lookups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    claim       TEXT NOT NULL,     -- what was uncertain, as a question
    strategy    TEXT NOT NULL,     -- why THIS source before searching it
    source      TEXT NOT NULL,     -- url / man page / file -- primary beats blog
    found       TEXT NOT NULL,     -- what the source actually says
    corrected   TEXT,              -- the false thing the agent had already said
    concept     TEXT,              -- slug it came up under, if any
    ts          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lookups_session ON lookups(session_id);

-- ---- v2.2: the studio -- code review as the unit of feedback ----------------
-- Lab-heavy pedagogy: he does not get one verdict per artifact, he gets
-- findings, fixes them, and is reviewed again. A round is one pass over one
-- attempt. `blocker` and `correctness` findings BLOCK promotion -- reviewing
-- something and then crediting it anyway is how a review becomes theatre.
CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    attempt_id  INTEGER REFERENCES attempts(id),
    slug        TEXT NOT NULL,
    round       INTEGER NOT NULL,     -- 1,2,3... per (slug)
    file        TEXT,
    line        INTEGER,
    severity    TEXT NOT NULL,        -- blocker|correctness|robustness|clarity|naming
    finding     TEXT NOT NULL,        -- the concrete failure, with the input
    state       TEXT NOT NULL DEFAULT 'OPEN',   -- OPEN|FIXED|WAIVED
    fixed_in    INTEGER REFERENCES attempts(id),
    resolution  TEXT,
    opened_at   TEXT NOT NULL,
    closed_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_reviews_open ON reviews(state, slug);

-- ---- v2.2: capstone -- open-ended work with no spec to diff against ---------
-- Every gate so far has a right answer sitting in a file. That measures
-- reconstruction. It cannot measure design, because design only exists where
-- the requirements underdetermine the program. `decisions` is the list of
-- forks HE must resolve; fewer than two and it is a gate wearing a costume.
CREATE TABLE IF NOT EXISTS capstones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT UNIQUE NOT NULL,
    title       TEXT NOT NULL,
    brief       TEXT NOT NULL,        -- what must be true when it works
    decisions   TEXT NOT NULL,        -- the forks HE resolves, one per line
    constraints TEXT,                 -- budget, scale, what may not be used
    proposed_by TEXT NOT NULL,        -- learner|agent
    state       TEXT NOT NULL DEFAULT 'PROPOSED',  -- PROPOSED|ACTIVE|SHIPPED
    opened_at   TEXT NOT NULL,
    shipped_at  TEXT,
    artifact    TEXT,                 -- the thing that RUNS, not a description
    defense     TEXT                  -- why he chose each fork, in his words
);

-- ---- v2.3: stalls -- the freeze, the push, and what the freeze MEANT --------
-- He freezes at the blank page and needs a small push to move. Refusing the
-- push is not discipline: he sits there, the session dies, and nothing is
-- measured. Giving it freely is worse -- it is v1, where ten agents explained
-- and he produced nothing.
--
-- So a push is metered. Six levels, no skipping, and NO ESCALATION WITHOUT AN
-- EDIT: `file_sha` is the target as it stood at the push, and the next level
-- refuses while it is unchanged. A bigger hint is not something you get for
-- not trying.
--
-- `hypothesis` is required on every push, because a freeze is data. The push
-- unblocks the hour; the hypothesis is the only thing that survives the week.
-- It is NEVER a fact until tested: state goes OPEN -> CONFIRMED|FALSE, and a
-- confirmation carried only by his self-report is stamped as such, because his
-- self-report is a hint and his code is evidence.
CREATE TABLE IF NOT EXISTS stalls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    gate_id     INTEGER REFERENCES gates(id),
    slug        TEXT NOT NULL,
    level_n     INTEGER NOT NULL,   -- 0..5
    level       TEXT NOT NULL,      -- RESTATE|LOCATE|QUESTION|SHAPE|SKELETON|LINE
    kind        TEXT NOT NULL,      -- blank|form|recall|commit
    hypothesis  TEXT NOT NULL,      -- what hole this freeze suggests
    text        TEXT,               -- what was actually put in his file
    target      TEXT,
    anchor      INTEGER,            -- line it was inserted at
    file_sha    TEXT,               -- his file AT the moment of the push
    ts          TEXT NOT NULL,
    hyp_state   TEXT NOT NULL DEFAULT 'OPEN',   -- OPEN|CONFIRMED|FALSE
    hyp_by      TEXT,               -- probe|learner  (probe outranks learner)
    hyp_evidence TEXT,
    hyp_closed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_stalls_gate ON stalls(gate_id);
CREATE INDEX IF NOT EXISTS idx_stalls_hyp ON stalls(hyp_state);

-- ---- discovery chains: logged when bucket resolves ------
-- Permanent record of discovery chains (fstring -> str-methods -> json-dumps)
CREATE TABLE IF NOT EXISTS discovery_chains (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL,
    primary_concept TEXT NOT NULL,
    chain_json  TEXT NOT NULL,       -- JSON array of discovery chain
    status      TEXT NOT NULL,       -- in_progress|archived
    started_at  TEXT,
    archived_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_discovery_chains_project ON discovery_chains(project_id);

-- ---- v2: the phase pointer -------------------------------------------------
-- FLOOR -> READ -> BUILD_V1 -> BUILD_V2 -> CAPSTONE. The learner's ONLY choice.
INSERT OR IGNORE INTO meta(key, value) VALUES ('phase', 'FLOOR');
INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '2');

-- ---- v3: context router registry -------------------------------------------
-- The master mind lives HERE, in data, never fully in the AI's context.
-- Adding a gap type / angle / key / question is a row, not a prompt edit.
-- `applies_when` is a JSON condition evaluated by router.py (pure code):
--   {"always": true} | {"phase_in": [...]} | {"has_context": true}
--   {"open_gaps_min": 1} | {"open_misconceptions_min": 1}
--   {"current_angle": true} | {"angles_unexplored_min": 1}
-- Every present field must match (AND semantics).

CREATE TABLE IF NOT EXISTS gap_types (
    slug        TEXT PRIMARY KEY,   -- model|reason|application|tradeoff (+ future rows)
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS angles (
    slug        TEXT PRIMARY KEY,   -- mechanical|practical|reasoning (+ future rows)
    description TEXT NOT NULL,
    ord         INTEGER NOT NULL    -- default teaching order
);

CREATE TABLE IF NOT EXISTS bucket_keys (
    name         TEXT PRIMARY KEY,  -- dotted path inside bucket / context files
    description  TEXT NOT NULL,     -- one line: what it is, when to write it
    value_type   TEXT NOT NULL,     -- string|array|object|timestamp
    applies_when TEXT NOT NULL DEFAULT '{"always": true}'
);

CREATE TABLE IF NOT EXISTS form_questions (
    slug         TEXT PRIMARY KEY,
    question     TEXT NOT NULL,     -- what the AGENT must answer about the learner's answer
    answers      TEXT,              -- comma-separated valid answers; NULL = free text
    applies_when TEXT NOT NULL DEFAULT '{"always": true}',
    ord          INTEGER NOT NULL DEFAULT 0
);

-- Every answered form. This is the gap-detection audit trail: what the agent
-- concluded from each learner answer, with the evidence quoted.
CREATE TABLE IF NOT EXISTS assessments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER REFERENCES sessions(id),
    slug         TEXT NOT NULL,     -- concept under teaching
    hole         TEXT NOT NULL,     -- none|explicit|implicit
    gap_type     TEXT,              -- REQUIRED when hole != none; FK-checked in code
    demonstrated INTEGER,           -- REQUIRED when hole == none: 1 demonstrated, 0 claimed
    angle        TEXT,              -- angle being taught when this answer happened
    angle_result TEXT,              -- pass|partial|fail
    evidence     TEXT NOT NULL,     -- the learner's words, verbatim-ish
    ts           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assessments_slug ON assessments(slug);
