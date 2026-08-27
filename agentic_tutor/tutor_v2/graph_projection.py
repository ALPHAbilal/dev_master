"""Live semantic-map producer: mirror each validated turn into agent-provenance graph rows.

This is the observability surface. On every meaningful turn (teach, grade, distill) it emits
the nodes/edges that make the center map rich — concepts taught, misconceptions revealed,
prerequisites uncovered, takeaways proved — each carrying ``evidence_refs`` back to the exact
probe/message that caused it, so a map node can be clicked to its conversation.

Contract (why atomic emission is safe): this translator is called INSIDE each turn's existing
transaction, so a map row and its tutoring fact commit together. It is built so it cannot throw:

- **Total.** ``_GRADE_EMISSION`` has one entry for every ``GRADE_CATEGORIES`` value; an
  exhaustiveness test asserts the key sets are equal, so an unmapped category is impossible.
- **Pure over validated input.** It runs only on an already-validated stamp plus ids the turn
  just wrote. No raw text, JSON, filesystem, network, or clock.
- **Validated writer only.** Every write goes through ``SemanticGraphService.add_node/add_edge``,
  which enforce the vocabulary and evidence rules — it cannot construct an invalid row.
- **Idempotent.** Anchors, per-axis concepts, and edges are find-or-create; grade turns cannot
  replay (``submit_answer`` guards that upstream). Re-running is a no-op, never a duplicate.
- **No judgment.** It chooses no verdict, category, or route; it is a projection, not a decision.
"""
from __future__ import annotations

from typing import Any

from .contracts import GRADE_CATEGORIES
from .semantics import SemanticGraphService

# per-axis "state" dots: exactly one per (unit, axis). prerequisite is intentionally excluded.
_SINGLETON_KINDS = frozenset({"takeaway", "misconception", "mechanism"})

# category -> (node_kind, relationship) or None for "this turn adds no concept".
# Every GRADE_CATEGORIES member appears exactly once (enforced by test).
_GRADE_EMISSION: dict[str, tuple[str, str] | None] = {
    "correct-deep": ("takeaway", "proved_by"),
    "misconception": ("misconception", "revealed_gap_in"),
    "working-code-wrong-reasoning": ("mechanism", "revealed_gap_in"),
    "different-prereq": ("prerequisite", "depends_on"),
    "sibling-hole": ("prerequisite", "revealed_gap_in"),
    "pattern-matched": None,
    "shaky": None,
    "confused-question": None,
    "different-axis": None,
    "off-topic": None,
    "gives-up": None,
    "silent-stuck": None,
    "disputes-verdict": None,
    "skip-request": None,
    "fatigue-switch": None,
}


class GraphProjection:
    """Deterministic, idempotent mirror of validated agent turns into the semantic graph."""

    def __init__(self, graph: SemanticGraphService) -> None:
        self.graph = graph

    # -- teach --------------------------------------------------------------------

    def on_teaching(self, *, journey_id: int, unit_id: int, axis: str, message_ids: list[int]) -> None:
        """Record the concept taught for an axis, linked to the unit anchor."""
        if not message_ids:
            return
        evidence = [f"message:{message_id}" for message_id in message_ids]
        anchor = self._anchor(journey_id, unit_id)
        concept = self._concept_for_axis(journey_id, unit_id, axis, evidence)
        self._link(journey_id, anchor, concept, "requires_understanding", evidence)

    # -- grade --------------------------------------------------------------------

    def on_grade(
        self, *, journey_id: int, unit_id: int, axis: str, turn_id: str, category: str,
        hidden_gap: dict[str, Any] | None, probe_id: int, map_text: dict[str, Any] | None,
    ) -> None:
        """Emit the node the graded turn revealed, using the agent-authored map_text."""
        spec = _GRADE_EMISSION[category]  # KeyError impossible: category is validated + total
        if spec is None:
            return
        node_kind, relationship = spec
        evidence = [f"probe:{probe_id}", f"turn:{turn_id}"]
        anchor = self._anchor(journey_id, unit_id)
        node_id = self._agent_node(
            journey_id=journey_id, unit_id=unit_id, axis=axis, kind=node_kind,
            title=map_text["title"], summary=map_text["summary"], evidence=evidence)
        self._link(journey_id, anchor, node_id, relationship, evidence)
        if node_kind == "takeaway":                      # a proof — resolve prior gaps on this axis
            self._disprove_axis_gaps(journey_id, unit_id, axis, node_id, evidence)

    # -- distill ------------------------------------------------------------------

    def on_distill(
        self, *, journey_id: int, unit_id: int, axes_tested: list[str], event_ref: str,
    ) -> None:
        """Seal each tested axis as a takeaway (find-or-create: no second dot for an axis)."""
        evidence = [event_ref]
        anchor = self._anchor(journey_id, unit_id)
        for axis in axes_tested:
            node_id = self._agent_node(
                journey_id=journey_id, unit_id=unit_id, axis=axis, kind="takeaway",
                title=f"Owned: {axis}", summary=f"Sealed the {axis} axis", evidence=evidence)
            self._link(journey_id, anchor, node_id, "proved_by", evidence)

    # -- code-owned disproval --------------------------------------------------------

    def _disprove_axis_gaps(self, journey_id: int, unit_id: int, axis: str,
                            proof_node_id: int, evidence: list[str]) -> None:
        """Proving an axis disproves any still-active gap dot on that same axis."""
        gaps = self.graph.db.query(
            "SELECT id FROM semantic_nodes WHERE journey_id=? AND unit_id=? AND axis=? "
            "AND kind IN ('misconception','mechanism') AND provenance='agent' AND status='active'",
            (journey_id, unit_id, axis))
        for g in gaps:
            self.graph.set_node_status(int(g["id"]), "disproved")
            # the gap was disproved BY the proof
            self._link(journey_id, int(g["id"]), proof_node_id, "disproved_by", evidence)

    # -- cross-turn edges (code-owned topology) -----------------------------------

    def on_detour(
        self, *, journey_id: int, parent_unit_id: int, child_unit_id: int, probe_id: int, turn_id: str,
    ) -> None:
        evidence = [f"probe:{probe_id}", f"turn:{turn_id}"]
        parent = self._anchor(journey_id, parent_unit_id)
        child = self._anchor(journey_id, child_unit_id)
        self._link(journey_id, parent, child, "detoured_to", evidence)

    def on_parent_resume(
        self, *, journey_id: int, child_unit_id: int, parent_unit_id: int, event_ref: str,
    ) -> None:
        evidence = [event_ref]
        child = self._anchor(journey_id, child_unit_id)
        parent = self._anchor(journey_id, parent_unit_id)
        self._link(journey_id, child, parent, "returned_to", evidence)

    # -- graph helpers (all find-or-create / idempotent) --------------------------

    def _anchor(self, journey_id: int, unit_id: int) -> int:
        row = self.graph.db.one(
            "SELECT id FROM semantic_nodes WHERE journey_id=? AND unit_id=? AND provenance='system' "
            "AND kind='concept' ORDER BY id LIMIT 1",
            (journey_id, unit_id),
        )
        if row:
            return int(row["id"])
        unit = self.graph.db.one(
            "SELECT slug,title,file,lo,hi FROM units WHERE id=?", (unit_id,)
        )
        return self.graph.add_node(
            journey_id=journey_id, unit_id=unit_id, kind="concept",
            title=unit["title"] or unit["slug"], provenance="system",
            source_ref={"file": unit["file"], "lo": int(unit["lo"]), "hi": int(unit["hi"])},
            summary=f"Learning unit anchor for {unit['slug']}",
        )

    def _concept_for_axis(self, journey_id: int, unit_id: int, axis: str, evidence: list[str]) -> int:
        title = f"{axis}: understanding"
        row = self.graph.db.one(
            "SELECT id FROM semantic_nodes WHERE journey_id=? AND unit_id=? AND kind='concept' "
            "AND provenance='agent' AND title=? LIMIT 1",
            (journey_id, unit_id, title),
        )
        if row:
            return int(row["id"])
        return self.graph.add_node(
            journey_id=journey_id, unit_id=unit_id, kind="concept", title=title,
            provenance="agent", evidence_refs=evidence, summary=f"Concept taught for the {axis} axis",
        )

    def _agent_node(self, *, journey_id: int, unit_id: int, axis: str, kind: str,
                    title: str, summary: str, evidence: list[str]) -> int:
        """Find-or-create an agent state-dot; singleton kinds are unique per (unit, axis)."""
        if kind in _SINGLETON_KINDS:
            row = self.graph.db.one(
                "SELECT id FROM semantic_nodes WHERE journey_id=? AND unit_id=? AND axis=? "
                "AND kind=? AND provenance='agent' ORDER BY id LIMIT 1",
                (journey_id, unit_id, axis, kind))
            if row:
                return int(row["id"])
        return self.graph.add_node(
            journey_id=journey_id, unit_id=unit_id, axis=axis, kind=kind, title=title,
            provenance="agent", summary=summary, evidence_refs=evidence)

    def _link(self, journey_id: int, from_id: int, to_id: int, relationship: str, evidence: list[str]) -> None:
        exists = self.graph.db.one(
            "SELECT id FROM semantic_edges WHERE journey_id=? AND from_node_id=? AND to_node_id=? "
            "AND relationship_type=? LIMIT 1",
            (journey_id, from_id, to_id, relationship),
        )
        if exists:
            return
        self.graph.add_edge(
            journey_id=journey_id, from_node_id=from_id, to_node_id=to_id,
            relationship_type=relationship, provenance="agent", evidence_refs=evidence,
        )
