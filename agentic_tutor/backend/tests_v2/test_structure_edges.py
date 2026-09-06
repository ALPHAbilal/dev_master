"""Step 4d tests: the parser emits ``calls`` and ``imports`` edges, not just ``contains``."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tutor_v2 import (
    Database, JourneyRecorder, Router, SemanticGraphService, StructureExtractor, TutorConfig,
    WorkspaceService,
)

# load() calls read() (same file → resolvable) and imports os (external → not a node).
_SAMPLE = (
    "import os\n"
    "\n"
    "def load(path):\n"
    "    os.stat(path)\n"
    "    return read(path)\n"
    "\n"
    "\n"
    "def read(path):\n"
    "    return {}\n"
)


def _extract():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "run.py").write_text(_SAMPLE, encoding="utf-8")
    extraction = StructureExtractor(root).extract("run.py")
    return temp, root, extraction


def test_extractor_emits_calls_and_imports_edges():
    temp, _root, extraction = _extract()
    try:
        rels = {(e.from_qualname, e.to_qualname, e.relationship) for e in extraction.edges}
        assert ("load", "read", "calls") in rels, "a same-file call must be wired"
        assert ("run.py", "os", "imports") in rels, "a module-scope import is attributed to the module"
        # contains still intact.
        assert ("run.py", "load", "contains") in rels
    finally:
        temp.cleanup()


def test_ingest_persists_resolvable_calls_and_drops_external_imports():
    temp, root, extraction = _extract()
    try:
        config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "s1",
                             codebase_root=root)
        db = Database(config.database_path)
        WorkspaceService(db, config).initialize(target="run.py", document_id="learner-main",
                                                display_name="solution.py", language="python")
        # A root unit spanning the whole file, so both defs reconcile into it.
        unit = {"slug": "loader", "file": "run.py", "lo": 1, "hi": 9, "depth": 0,
                "parent": None, "axes": ["COMPREHEND"]}
        pointed = Router(db, config).commit_map(json.loads(json.dumps({
            "kind": "return.map", "target": "run.py", "mode": "initial", "continues_after": None,
            "objective_covered": True, "units": [unit], "order": ["loader"]})))
        journey_id = JourneyRecorder(db, config).start(pointed.unit_id)
        graph = SemanticGraphService(db, config)
        graph.ingest_structure(journey_id=journey_id, unit_id=pointed.unit_id, extraction=extraction)

        rels = {e["relationship_type"] for e in graph.edges_for_journey(journey_id)}
        assert "calls" in rels, "the resolvable load->read call must persist"
        # The import target (os) has no structural node, so the ingester drops it — no crash.
        assert "imports" not in rels
    finally:
        db.close()
        temp.cleanup()
