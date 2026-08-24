"""Stage 7/8 tests: structure extraction, range reconciliation, validated graph."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tutor_v2 import (
    Database, JourneyRecorder, Router, SemanticGraphService, StructureExtractor,
    TutorConfig, ValidationError, WorkspaceService, reconcile_range,
)

_SAMPLE = '''\
class ConfigLoader:
    def load(self, path):
        return self._read(path)

    def _read(self, path):
        return {}


def helper():
    return 1
'''


def _setup():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "run.py").write_text(_SAMPLE, encoding="utf-8")
    config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "s1",
                         codebase_root=root)
    db = Database(config.database_path)
    WorkspaceService(db, config).initialize(
        target="run.py", document_id="learner-main", display_name="solution.py", language="python"
    )
    return temp, db, config, Router(db, config)


def _map(lo, hi):
    unit = {"slug": "main", "file": "run.py", "lo": lo, "hi": hi, "depth": 0, "parent": None, "axes": ["COMPREHEND"]}
    return {"kind": "return.map", "target": "run.py", "mode": "initial", "continues_after": None,
            "objective_covered": True, "units": [unit], "order": ["main"]}


def test_extractor_finds_class_methods_and_functions_with_ranges():
    temp, db, config, router = _setup()
    try:
        extraction = StructureExtractor(config.codebase_root).extract("run.py")
        kinds = {n.qualname: n.kind for n in extraction.nodes}
        assert kinds["run.py"] == "module"
        assert kinds["ConfigLoader"] == "class"
        assert kinds["ConfigLoader.load"] == "method"
        assert kinds["helper"] == "function"
        load = next(n for n in extraction.nodes if n.qualname == "ConfigLoader.load")
        assert load.lo == 2 and load.hi == 3
        contains = {(e.from_qualname, e.to_qualname) for e in extraction.edges}
        assert ("ConfigLoader", "ConfigLoader.load") in contains
        assert ("run.py", "helper") in contains
    finally:
        db.close()
        temp.cleanup()


def test_reconcile_range_classifies_relationships():
    assert reconcile_range(1, 10, 2, 5) == "contains"
    assert reconcile_range(3, 4, 2, 8) == "focuses_on"
    assert reconcile_range(1, 5, 4, 9) == "overlaps"
    assert reconcile_range(1, 3, 5, 9) is None


def test_ingest_structure_persists_parser_nodes_and_reconciliation_edges():
    temp, db, config, router = _setup()
    try:
        pointed = router.commit_map(_map(1, 6))  # unit covers the whole class
        journey_id = JourneyRecorder(db, config).start(pointed.unit_id)
        graph = SemanticGraphService(db, config)
        extraction = StructureExtractor(config.codebase_root).extract("run.py")
        mapping = graph.ingest_structure(journey_id=journey_id, unit_id=pointed.unit_id, extraction=extraction)
        assert "ConfigLoader.load" in mapping and "__anchor__" in mapping
        nodes = graph.nodes_for_journey(journey_id)
        provenances = {n["provenance"] for n in nodes}
        assert provenances == {"system", "parser"}
        edges = graph.edges_for_journey(journey_id)
        rels = {e["relationship_type"] for e in edges}
        assert "contains" in rels  # both structural contains and unit-reconciliation
    finally:
        db.close()
        temp.cleanup()


def test_agent_nodes_require_evidence():
    temp, db, config, router = _setup()
    try:
        pointed = router.commit_map(_map(1, 6))
        journey_id = JourneyRecorder(db, config).start(pointed.unit_id)
        graph = SemanticGraphService(db, config)
        with pytest.raises(ValidationError, match="evidence"):
            graph.add_node(journey_id=journey_id, kind="concept", title="Boundary validation",
                           provenance="agent")
        node = graph.add_node(journey_id=journey_id, kind="concept", title="Boundary validation",
                              provenance="agent", evidence_refs=["probe:3"])
        assert node > 0
    finally:
        db.close()
        temp.cleanup()


def test_relationship_vocabulary_is_restricted_by_provenance():
    temp, db, config, router = _setup()
    try:
        pointed = router.commit_map(_map(1, 6))
        journey_id = JourneyRecorder(db, config).start(pointed.unit_id)
        graph = SemanticGraphService(db, config)
        a = graph.add_node(journey_id=journey_id, kind="concept", title="A", provenance="system")
        b = graph.add_node(journey_id=journey_id, kind="concept", title="B", provenance="system")
        with pytest.raises(ValidationError, match="unsupported relationship"):
            graph.add_edge(journey_id=journey_id, from_node_id=a, to_node_id=b,
                           relationship_type="teleports_to", provenance="system")
        with pytest.raises(ValidationError, match="structural relationship"):
            graph.add_edge(journey_id=journey_id, from_node_id=a, to_node_id=b,
                           relationship_type="requires_understanding", provenance="parser")
    finally:
        db.close()
        temp.cleanup()
