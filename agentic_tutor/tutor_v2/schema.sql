-- Tutor v2: authoritative SQLite state for the 12-stone architecture.
-- Mutable stones live here. Workspace content and sealed archive artifacts are files.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS units (
    id          INTEGER PRIMARY KEY,
    session_id  TEXT NOT NULL,
    slug        TEXT NOT NULL,
    title       TEXT NOT NULL,
    file        TEXT NOT NULL,
    lo          INTEGER NOT NULL CHECK (lo > 0),
    hi          INTEGER NOT NULL CHECK (hi >= lo),
    ordinal     INTEGER NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
    depth       INTEGER NOT NULL DEFAULT 0 CHECK (depth >= 0),
    parent_id   INTEGER REFERENCES units(id),
    anchor_kind TEXT NOT NULL DEFAULT 'code' CHECK (anchor_kind IN ('code','conceptual')),
    state       TEXT NOT NULL DEFAULT 'NEW'
                    CHECK (state IN ('NEW','POINTED','PROBED','TAUGHT','TESTED',
                                     'JUDGED','OWNED','PARKED')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(session_id, slug)
);

CREATE TABLE IF NOT EXISTS axes (
    id            INTEGER PRIMARY KEY,
    unit_id       INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    axis          TEXT NOT NULL CHECK (axis IN ('COMPREHEND','MECHANISM','RATIONALE',
                                                'JUDGMENT','ROBUSTNESS','INTEGRATION',
                                                'EVOLUTION')),
    verdict       TEXT NOT NULL DEFAULT 'UNGRADED'
                      CHECK (verdict IN ('UNGRADED','SOLID','SHAKY','MISSING')),
    shaky_count   INTEGER NOT NULL DEFAULT 0 CHECK (shaky_count >= 0),
    evidence_ref  TEXT,
    ordinal       INTEGER NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(unit_id, axis)
);

CREATE TABLE IF NOT EXISTS stack (
    id           INTEGER PRIMARY KEY,
    session_id   TEXT NOT NULL,
    unit_id      INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    depth        INTEGER NOT NULL CHECK (depth >= 0),
    resume_q     TEXT,
    pending_json TEXT NOT NULL DEFAULT '[]',
    hop_budget   INTEGER NOT NULL DEFAULT 0 CHECK (hop_budget >= 0),
    is_top       INTEGER NOT NULL DEFAULT 1 CHECK (is_top IN (0, 1)),
    UNIQUE(session_id, unit_id),
    UNIQUE(session_id, depth)
);

CREATE TABLE IF NOT EXISTS meta (
    session_id         TEXT PRIMARY KEY,
    current_unit_id    INTEGER REFERENCES units(id),
    phase              TEXT NOT NULL DEFAULT 'SCAN'
                           CHECK (phase IN ('SCAN','LOOP','GRADUATION')),
    target             TEXT NOT NULL,
    document_id        TEXT,
    display_name       TEXT,
    language           TEXT,
    workspace_path     TEXT,
    workspace_revision INTEGER NOT NULL DEFAULT 0 CHECK (workspace_revision >= 0),
    workspace_hash     TEXT,
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS probes (
    id             INTEGER PRIMARY KEY,
    session_id     TEXT NOT NULL,
    turn           INTEGER NOT NULL CHECK (turn > 0),
    unit_id        INTEGER NOT NULL REFERENCES units(id),
    axis           TEXT NOT NULL,
    step           TEXT NOT NULL CHECK (step IN ('probe','test')),
    question       TEXT NOT NULL,
    learner_answer TEXT NOT NULL,
    verdict        TEXT NOT NULL CHECK (verdict IN ('SOLID','SHAKY','MISSING')),
    category       TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS learner (
    learner_id    TEXT PRIMARY KEY,
    profile_json  TEXT NOT NULL DEFAULT '{"can":[],"cant":[],"misconceptions":[]}',
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS handoff (
    session_id    TEXT PRIMARY KEY,
    payload_json  TEXT NOT NULL,
    parked_stack  INTEGER NOT NULL DEFAULT 0 CHECK (parked_stack IN (0, 1)),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    unit_id       INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    axis          TEXT,
    document_id   TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('edit','command','test','error','ui',
                                                'feedback','block','message')),
    payload_json  TEXT NOT NULL,
    result_json   TEXT,
    revision_hash TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_units_session_state ON units(session_id, state);
CREATE INDEX IF NOT EXISTS idx_axes_unit ON axes(unit_id);
CREATE INDEX IF NOT EXISTS idx_events_session_unit ON events(session_id, unit_id, id);
CREATE INDEX IF NOT EXISTS idx_probes_session_unit ON probes(session_id, unit_id, id);
