"""Validated persistence for the semantic graph (nodes + edges).

The graph has three provenances: ``parser`` (deterministic structure), ``agent``
(concepts/explanations translated from validated agent outputs), and ``system``
(reconciliation links the application draws). This service is the only writer. It
enforces the node/edge schema, restricts the relationship vocabulary, requires evidence
for agent-authored claims, and validates source anchors. It never lays out the graph and
never calls an agent.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import TutorConfig
from .db import Database
from .errors import ValidationError
from .structure import StructureExtraction, reconcile_range

_NODE_KINDS = frozenset({
    "module", "file", "class", "function", "method", "concept", "mechanism",
    "decision", "explanation", "misconception", "failure", "test", "takeaway",
    "prerequisite", "return",
})
_STRUCTURAL_RELATIONSHIPS = frozenset({"contains", "imports", "calls"})
_RECONCILIATION_RELATIONSHIPS = frozenset({"contains", "overlaps", "focuses_on"})
_SEMANTIC_RELATIONSHIPS = frozenset({
    "requires_understanding", "creates", "passes_data_to", "depends_on", "fails_because",
    "disproved_by", "revealed_gap_in", "detoured_to", "returned_to", "proved_by",
    "improved_by",
})
_ALL_RELATIONSHIPS = _STRUCTURAL_RELATIONSHIPS | _RECONCILIATION_RELATIONSHIPS | _SEMANTIC_RELATIONSHIPS
_PROVENANCES = frozenset({"parser", "agent", "system"})


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class SemanticGraphService:
    """Deterministic, validated writer of semantic nodes and edges."""

    def __init__(self, db: Database, config: TutorConfig) -> None:
        self.db = db
        self.config = config

    # -- nodes --------------------------------------------------------------------

    def add_node(
        self,
        *,
        journey_id: int,
        kind: str,
        title: str,
        provenance: str,
        unit_id: int | None = None,
        summary: str | None = None,
        axis: str | None = None,
        source_ref: dict[str, Any] | None = None,
        evidence_refs: list[str] | None = None,
        status: str = "active",
    ) -> int:
        if kind not in _NODE_KINDS:
            raise ValidationError(f"unsupported node kind: {kind}")
        if provenance not in _PROVENANCES:
            raise ValidationError(f"unsupported provenance: {provenance}")
        if not title.strip():
            raise ValidationError("node title is required")
        evidence_refs = evidence_refs or []
        if provenance == "agent" and not evidence_refs:
            raise ValidationError("agent-authored nodes require evidence references")
        if source_ref is not None:
            self._validate_source_ref(source_ref)
        with self.db.transaction():
            cursor = self.db.connection.execute(
                "INSERT INTO semantic_nodes(journey_id,unit_id,kind,title,summary,axis,"
                "source_ref_json,status,provenance,evidence_refs_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (journey_id, unit_id, kind, title, summary, axis,
                 _json(source_ref) if source_ref is not None else None,
                 status, provenance, _json(evidence_refs)),
            )
        return int(cursor.lastrowid)

    def add_edge(
        self,
        *,
        journey_id: int,
        from_node_id: int,
        to_node_id: int,
        relationship_type: str,
        provenance: str,
        label: str | None = None,
        explanation: str | None = None,
        evidence_refs: list[str] | None = None,
    ) -> int:
        if relationship_type not in _ALL_RELATIONSHIPS:
            raise ValidationError(f"unsupported relationship: {relationship_type}")
        if provenance not in _PROVENANCES:
            raise ValidationError(f"unsupported provenance: {provenance}")
        if provenance == "agent" and relationship_type not in _SEMANTIC_RELATIONSHIPS:
            raise ValidationError("agent edges must use the semantic relationship vocabulary")
        if provenance == "parser" and relationship_type not in _STRUCTURAL_RELATIONSHIPS:
            raise ValidationError("parser edges must use the structural relationship vocabulary")
        evidence_refs = evidence_refs or []
        if provenance == "agent" and not evidence_refs:
            raise ValidationError("agent-authored edges require evidence references")
        self._require_node(journey_id, from_node_id)
        self._require_node(journey_id, to_node_id)
        with self.db.transaction():
            cursor = self.db.connection.execute(
                "INSERT INTO semantic_edges(journey_id,from_node_id,to_node_id,relationship_type,"
                "label,explanation,provenance,evidence_refs_json) VALUES(?,?,?,?,?,?,?,?)",
                (journey_id, from_node_id, to_node_id, relationship_type, label, explanation,
                 provenance, _json(evidence_refs)),
            )
        return int(cursor.lastrowid)

    def set_node_status(self, node_id: int, status: str) -> None:
        if status not in {"active", "disproved", "superseded"}:
            raise ValidationError(f"unsupported node status: {status}")
        with self.db.transaction():
            self.db.connection.execute(
                "UPDATE semantic_nodes SET status=?,updated_at=datetime('now') WHERE id=?",
                (status, node_id))

    # -- parser ingestion + reconciliation ---------------------------------------

    def ingest_structure(
        self, *, journey_id: int, unit_id: int, extraction: StructureExtraction
    ) -> dict[str, int]:
        """Persist parser nodes/edges and link each to the unit by range reconciliation.

        Returns a mapping of structural qualname → semantic_node id. The unit's own
        range comes from the ``units`` row; each structural node gets a system-provenance
        reconciliation edge (contains/overlaps/focuses_on) to the unit's anchor node.
        """
        unit = self.db.one(
            "SELECT slug,title,file,lo,hi FROM units WHERE id=? AND session_id=?",
            (unit_id, self.config.session_id),
        )
        if not unit:
            raise ValidationError("unit does not belong to this session")
        anchor_id = self.add_node(
            journey_id=journey_id, unit_id=unit_id, kind="concept",
            title=unit["title"], provenance="system",
            source_ref={"file": unit["file"], "lo": unit["lo"], "hi": unit["hi"]},
            summary=f"Learning unit anchor for {unit['slug']}",
        )
        by_qualname: dict[str, int] = {}
        with self.db.transaction():
            for node in extraction.nodes:
                node_id = self.add_node(
                    journey_id=journey_id, unit_id=unit_id, kind=node.kind, title=node.qualname,
                    provenance="parser",
                    source_ref={"file": node.file, "lo": node.lo, "hi": node.hi},
                )
                by_qualname[node.qualname] = node_id
                relationship = reconcile_range(int(unit["lo"]), int(unit["hi"]), node.lo, node.hi)
                if relationship is not None:
                    self.add_edge(
                        journey_id=journey_id, from_node_id=anchor_id, to_node_id=node_id,
                        relationship_type=relationship, provenance="system",
                    )
            for edge in extraction.edges:
                source = by_qualname.get(edge.from_qualname)
                target = by_qualname.get(edge.to_qualname)
                if source is not None and target is not None:
                    self.add_edge(journey_id=journey_id, from_node_id=source, to_node_id=target,
                                  relationship_type=edge.relationship, provenance="parser")
        by_qualname["__anchor__"] = anchor_id
        return by_qualname

    # -- reads --------------------------------------------------------------------

    def nodes_for_journey(self, journey_id: int) -> list[dict[str, Any]]:
        return self.db.query("SELECT * FROM semantic_nodes WHERE journey_id=? ORDER BY id", (journey_id,))

    def edges_for_journey(self, journey_id: int) -> list[dict[str, Any]]:
        return self.db.query("SELECT * FROM semantic_edges WHERE journey_id=? ORDER BY id", (journey_id,))

    # -- internals ----------------------------------------------------------------

    def _require_node(self, journey_id: int, node_id: int) -> None:
        row = self.db.one("SELECT journey_id FROM semantic_nodes WHERE id=?", (node_id,))
        if not row or int(row["journey_id"]) != journey_id:
            raise ValidationError("edge endpoints must be nodes in the same journey")

    def _validate_source_ref(self, source_ref: dict[str, Any]) -> None:
        if set(source_ref) != {"file", "lo", "hi"}:
            raise ValidationError("source_ref must have exactly file, lo, hi")
        lo, hi = source_ref["lo"], source_ref["hi"]
        if not isinstance(lo, int) or not isinstance(hi, int) or lo < 1 or hi < lo:
            raise ValidationError("source_ref lo/hi must be 1-based with hi >= lo")
        if self.config.codebase_root is not None:
            candidate = (self.config.codebase_root.resolve() / str(source_ref["file"])).resolve()
            root = self.config.codebase_root.resolve()
            if candidate != root and root not in candidate.parents:
                raise ValidationError("source_ref file escapes the codebase root")
