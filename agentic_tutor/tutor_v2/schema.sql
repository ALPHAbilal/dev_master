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

-- Journey layer (additive): the durable, learner-facing root-unit journey and its
-- conversation, lifecycle facts, semantic graph, and learner notes. The engine above
-- is unchanged; these tables are written only by orchestrator-owned recorders.

CREATE TABLE IF NOT EXISTS journeys (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    root_unit_id  INTEGER NOT NULL REFERENCES units(id),
    state         TEXT NOT NULL DEFAULT 'LIVE'
                      CHECK (state IN ('LIVE','PARKED','OWNED')),
    projection_revision INTEGER NOT NULL DEFAULT 0 CHECK (projection_revision >= 0),
    started_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at  TEXT,
    UNIQUE(session_id, root_unit_id)
);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id     INTEGER NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    unit_id        INTEGER NOT NULL REFERENCES units(id),
    axis           TEXT,
    role           TEXT NOT NULL CHECK (role IN ('learner','tutor','tool','system')),
    message_kind   TEXT NOT NULL,
    content        TEXT NOT NULL,
    turn_id        TEXT NOT NULL,
    sequence       INTEGER NOT NULL,
    status         TEXT NOT NULL DEFAULT 'RECORDED'
                       CHECK (status IN ('RECORDED','AWAITING_EVALUATION','EVALUATED')),
    source_wakeup_step    TEXT,
    archived_artifact_ref TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(journey_id, sequence)
);

CREATE TABLE IF NOT EXISTS journey_events (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id             INTEGER NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    unit_id                INTEGER NOT NULL REFERENCES units(id),
    parent_unit_id         INTEGER REFERENCES units(id),
    axis                   TEXT,
    event_type             TEXT NOT NULL,
    payload_json           TEXT NOT NULL DEFAULT '{}',
    message_refs_json      TEXT NOT NULL DEFAULT '[]',
    probe_refs_json        TEXT NOT NULL DEFAULT '[]',
    action_event_refs_json TEXT NOT NULL DEFAULT '[]',
    source_ref_json        TEXT,
    workspace_revision     INTEGER,
    workspace_hash         TEXT,
    created_at             TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS semantic_nodes (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id         INTEGER NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    unit_id            INTEGER REFERENCES units(id),
    kind               TEXT NOT NULL,
    title              TEXT NOT NULL,
    summary            TEXT,
    axis               TEXT,
    source_ref_json    TEXT,
    status             TEXT NOT NULL DEFAULT 'active',
    provenance         TEXT NOT NULL CHECK (provenance IN ('parser','agent','system')),
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS semantic_edges (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id         INTEGER NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    from_node_id       INTEGER NOT NULL REFERENCES semantic_nodes(id) ON DELETE CASCADE,
    to_node_id         INTEGER NOT NULL REFERENCES semantic_nodes(id) ON DELETE CASCADE,
    relationship_type  TEXT NOT NULL,
    label              TEXT,
    explanation        TEXT,
    provenance         TEXT NOT NULL CHECK (provenance IN ('parser','agent','system')),
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS learner_notes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id   INTEGER NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    target_kind  TEXT NOT NULL CHECK (target_kind IN ('node','edge','message','journey')),
    target_id    TEXT NOT NULL,
    content      TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_units_session_state ON units(session_id, state);
CREATE INDEX IF NOT EXISTS idx_axes_unit ON axes(unit_id);
CREATE INDEX IF NOT EXISTS idx_events_session_unit ON events(session_id, unit_id, id);
CREATE INDEX IF NOT EXISTS idx_probes_session_unit ON probes(session_id, unit_id, id);
CREATE INDEX IF NOT EXISTS idx_journeys_session ON journeys(session_id, root_unit_id);
CREATE INDEX IF NOT EXISTS idx_messages_journey ON conversation_messages(journey_id, sequence);
CREATE INDEX IF NOT EXISTS idx_messages_turn ON conversation_messages(journey_id, turn_id);
-- Idempotency backstop: one learner answer per (journey, turn). A replayed grade turn
-- reuses the existing answer instead of inserting a duplicate.
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_learner_answer_per_turn
    ON conversation_messages(journey_id, turn_id) WHERE role='learner';
CREATE INDEX IF NOT EXISTS idx_journey_events_journey ON journey_events(journey_id, id);
CREATE INDEX IF NOT EXISTS idx_semantic_nodes_journey ON semantic_nodes(journey_id, id);
CREATE INDEX IF NOT EXISTS idx_semantic_edges_journey ON semantic_edges(journey_id, id);
CREATE INDEX IF NOT EXISTS idx_learner_notes_journey ON learner_notes(journey_id, id);
