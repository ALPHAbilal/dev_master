"""TurnOrchestrator: deterministic workflow glue over the existing engine.

It owns turn identity, the text-to-stamp bridge, the outer atomic boundary, and the
additive recorders. It never interprets learner prose, chooses a verdict, or selects a
route: those remain with the agents, the contracts, and the Router. Model calls happen
outside any database transaction; only the validated state transition and its evidence
share one outer transaction, which nests the Router's own transaction as a savepoint.

The agent invocation itself is a seam. Callers pass already-produced model text
(``list[str]``) into these methods, so the orchestrator is fully testable without the
Claude SDK; a thin production layer runs ``ClaudeAgentAdapter.run`` and forwards blocks.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .config import TutorConfig
from .db import Database
from .errors import InvariantError, ValidationError
from .graph_projection import GraphProjection
from .journey_archive import JourneyArchiveService
from .learner_model import LearnerModelService
from .parsing import ReturnStampParser
from .recorders import ConversationRecorder, JourneyRecorder, ProbeRecorder
from .routing import RouteDecision, Router
from .semantics import SemanticGraphService
from .services import ArchiveService
from .structure import StructureExtractor


@dataclass(frozen=True, slots=True)
class TurnResult:
    """What one orchestration procedure produced for the transport/UI layer."""

    journey_id: int
    decision: RouteDecision | None
    projection_revision: int


class TurnOrchestrator:
    """Composes engine operations with additive recorders under one atomic boundary."""

    def __init__(
        self,
        db: Database,
        config: TutorConfig,
        router: Router,
        *,
        parser: ReturnStampParser | None = None,
        conversation: ConversationRecorder | None = None,
        probes: ProbeRecorder | None = None,
        journeys: JourneyRecorder | None = None,
        graph: SemanticGraphService | None = None,
        archive: JourneyArchiveService | None = None,
        unit_archive: ArchiveService | None = None,
        learner_model: LearnerModelService | None = None,
        graph_projection: GraphProjection | None = None,
    ) -> None:
        self.db = db
        self.config = config
        self.router = router
        self.parser = parser or ReturnStampParser()
        self.conversation = conversation or ConversationRecorder(db, config)
        self.probes = probes or ProbeRecorder(db, config)
        self.journeys = journeys or JourneyRecorder(db, config)
        # Optional additive wiring. When present, the orchestrator auto-attaches the
        # parser structure graph for newly pointed units and checkpoints/finalizes the
        # journey archive. When omitted, behavior is byte-for-byte the prior version.
        self.graph = graph
        self.archive = archive
        # DISTILL wiring (Stage 10). ``unit_archive`` seals the per-unit proof artifact;
        # ``learner_model`` applies the distill learner_diff. Both optional: when omitted,
        # commit_distill only records the lifecycle fact, changing no prior behavior.
        self.unit_archive = unit_archive
        self.learner_model = learner_model
        # LIVE map (Step 4a). When present, each teach/grade turn additionally mirrors its
        # validated result into agent-provenance semantic nodes/edges, inside the same
        # transaction as the tutoring write. When omitted, no graph rows are produced and
        # behavior is byte-for-byte the prior version.
        self.graph_projection = graph_projection

    # -- Stage 9: initial map + journey start -------------------------------------

    def commit_map(self, map_blocks: list[str]) -> TurnResult:
        """Parse a MAPPER return, then commit the map and start the first journey atomically."""
        stamp = self.parser.parse(map_blocks, expected_kind="return.map")
        with self.db.transaction():
            decision = self.router.commit_map(stamp)
            if decision.unit_id is None:
                raise InvariantError("commit_map produced no pointed root unit")
            journey_id = self.journeys.start(decision.unit_id)
            self.journeys.record_event(journey_id=journey_id, unit_id=decision.unit_id,
                                       event_type="journey_started")
            if decision.axis is not None:
                self.journeys.record_event(journey_id=journey_id, unit_id=decision.unit_id,
                                           event_type="axis_started", axis=decision.axis)
            revision = self.journeys.bump_revision(journey_id)
        # Additive, post-commit: attach the parser graph for the newly pointed root.
        self.attach_unit_structure(journey_id=journey_id, unit_id=decision.unit_id)
        return TurnResult(journey_id, decision, revision)

    # -- Stage 7 (probe/test) + Stage 8 (teach): non-graded turns -----------------

    def present_question(
        self,
        *,
        journey_id: int,
        unit_id: int,
        axis: str,
        turn_id: str,
        question: str,
        step: str = "wakeup.probe",
        save_resume_question: bool = False,
    ) -> int:
        """Persist a tutor question and, if a child dive may follow, bookmark it exactly."""
        if step not in {"wakeup.probe", "wakeup.test"}:
            raise ValidationError("present_question is for probe/test steps only")
        message_id = self.conversation.record(
            journey_id=journey_id, unit_id=unit_id, role="tutor", message_kind="question",
            content=question, turn_id=turn_id, axis=axis, source_wakeup_step=step,
        )
        if save_resume_question:
            # The engine keeps the parent's exact question; never rewritten here.
            self.router.record_resume_question(unit_id=unit_id, question=question)
        return message_id

    def present_teaching(
        self, *, journey_id: int, unit_id: int, axis: str, turn_id: str, blocks: list[str]
    ) -> list[int]:
        """Persist teaching text in order; record teaching_presented; no verdict is created."""
        message_ids: list[int] = []
        for block in [text for text in blocks if text.strip()]:
            message_ids.append(self.conversation.record(
                journey_id=journey_id, unit_id=unit_id, role="tutor", message_kind="teaching",
                content=block, turn_id=turn_id, axis=axis, source_wakeup_step="wakeup.teach",
            ))
        with self.db.transaction():
            self.journeys.record_event(journey_id=journey_id, unit_id=unit_id,
                                       event_type="teaching_presented", axis=axis,
                                       message_refs=message_ids)
            if self.graph_projection is not None:
                self.graph_projection.on_teaching(
                    journey_id=journey_id, unit_id=unit_id, axis=axis, message_ids=message_ids)
            self.journeys.bump_revision(journey_id)
        return message_ids

    # -- Stage 5 + 6: the atomic graded turn --------------------------------------

    def submit_answer(
        self,
        *,
        journey_id: int,
        unit_id: int,
        axis: str,
        turn_id: str,
        question: str,
        answer: str,
        grade_blocks: list[str],
        step: str = "probe",
    ) -> TurnResult:
        """Persist the learner answer, then commit route + probe + lifecycle atomically.

        The learner message is durable and marked AWAITING_EVALUATION before the Judge
        runs. Parsing and validation happen outside the transaction; only once a valid
        ``return.grade`` exists do the route, probe row, journey facts, and EVALUATED
        status commit together. A failure inside the boundary rolls all of them back and
        leaves the answer recoverable.
        """
        # Idempotency: a replayed grade turn must never route twice. If this turn's
        # answer is already EVALUATED, return the decision committed the first time.
        existing = self.conversation.find_learner_answer(journey_id=journey_id, turn_id=turn_id)
        if existing is not None and existing["status"] == "EVALUATED":
            return TurnResult(journey_id, self._replay_decision(journey_id, turn_id),
                              self.journeys.get(journey_id)["projection_revision"])

        # 1-4: durable learner answer, outside the atomic route boundary. On a recovery
        # replay the answer is already present (AWAITING_EVALUATION); do not duplicate it.
        if existing is None:
            self.conversation.record(
                journey_id=journey_id, unit_id=unit_id, role="learner", message_kind="answer",
                content=answer, turn_id=turn_id, axis=axis, status="AWAITING_EVALUATION",
            )
        # 5-7: parse + validate the Judge stamp with no route claimed yet.
        stamp = self.parser.parse(grade_blocks, expected_kind="return.grade")

        # 8-9: one outer transaction; route_grade's own transaction becomes a savepoint.
        with self.db.transaction():
            graded_before = self._unit_depth(unit_id)
            decision = self.router.route_grade(unit_id=unit_id, stamp=stamp)
            turn = self.probes.next_turn(unit_id)
            probe_id = self.probes.record(
                turn=turn, unit_id=unit_id, axis=axis, step=step, question=question,
                learner_answer=answer, verdict=stamp["verdict"], category=stamp["category"],
            )
            self.journeys.record_event(
                journey_id=journey_id, unit_id=unit_id, event_type="answer_evaluated", axis=axis,
                payload={"verdict": stamp["verdict"], "category": stamp["category"],
                         "turn_id": turn_id, "decision": self._decision_payload(decision)},
                probe_refs=[probe_id],
            )
            self._record_route_transition(journey_id, unit_id, graded_before, decision, stamp)
            if self.graph_projection is not None:
                self.graph_projection.on_grade(
                    journey_id=journey_id, unit_id=unit_id, axis=axis, turn_id=turn_id,
                    category=stamp["category"], hidden_gap=stamp["hidden_gap"], probe_id=probe_id)
            self.conversation.set_turn_status(journey_id=journey_id, turn_id=turn_id, status="EVALUATED")
            revision = self.journeys.bump_revision(journey_id)
        # Additive, post-commit: if the route opened a child detour, graph that child.
        if decision.unit_id is not None and decision.unit_id != unit_id:
            self.attach_unit_structure(journey_id=journey_id, unit_id=decision.unit_id)
        return TurnResult(journey_id, decision, revision)

    # -- Stage 10: distill a finished unit (seal proof + apply learner diff) -------

    def commit_distill(self, distill_blocks: list[str], *, unit_id: int) -> TurnResult:
        """Parse a DISTILLER return, seal the unit's proof, and apply the learner diff.

        Runs only for a unit the Router already finished: OWNED (all firing axes solid) or
        PARKED (fatigue-switch). Parsing happens outside the transaction; the seal, the
        learner-model merge, and the lifecycle fact then commit together. It does NOT change
        the unit's engine state — the existing ``finish_*``/``park`` steps still pop the stack.

        Idempotent: a second distill for the same unit is a no-op that returns the current
        revision, so a replay never double-records or double-applies the diff. (``seal`` and
        ``apply_diff`` are themselves idempotent; the guard avoids a duplicate event.)
        """
        stamp = self.parser.parse(distill_blocks, expected_kind="return.distill")
        journey_id = self.journeys.journey_for_unit(unit_id)
        already = self.db.one(
            "SELECT id FROM journey_events WHERE journey_id=? AND unit_id=? AND event_type='unit_distilled'",
            (journey_id, unit_id),
        )
        if already:
            return TurnResult(journey_id, None, self.journeys.get(journey_id)["projection_revision"])
        with self.db.transaction():
            unit = self.db.one(
                "SELECT slug,state FROM units WHERE id=? AND session_id=?",
                (unit_id, self.config.session_id),
            )
            if not unit:
                raise ValidationError("unit does not belong to this session")
            if unit["state"] not in {"OWNED", "PARKED"}:
                raise InvariantError("only an OWNED or PARKED unit may be distilled")
            if stamp["unit"] != unit["slug"]:
                raise ValidationError("distill unit slug does not match the target unit")
            expected_verdict = "OWNED" if unit["state"] == "OWNED" else "PARKED"
            if stamp["final_verdict"] != expected_verdict:
                raise ValidationError("distill final_verdict does not match the unit state")
            if self.unit_archive is not None:
                self.unit_archive.seal(
                    unit_id=unit_id, unit_slug=stamp["unit"], title=stamp["title"],
                    final_verdict=stamp["final_verdict"], axes_tested=stamp["axes_tested"],
                    tests=stamp["tests"], evidence=stamp["evidence"], resume_at=stamp["resume_at"],
                )
            if self.learner_model is not None:
                self.learner_model.apply_diff(stamp["learner_diff"])
            self.journeys.record_event(
                journey_id=journey_id, unit_id=unit_id, event_type="unit_distilled",
                payload={"final_verdict": stamp["final_verdict"], "unit": stamp["unit"],
                         "axes_tested": stamp["axes_tested"]},
            )
            revision = self.journeys.bump_revision(journey_id)
        return TurnResult(journey_id, None, revision)

    # -- Stage 11: child completion / parent return -------------------------------

    def finish_child(self, *, child_unit_id: int) -> TurnResult:
        """Pop an OWNED child back to its parent, recording detour completion + resume."""
        journey_id = self.journeys.journey_for_unit(child_unit_id)
        with self.db.transaction():
            decision = self.router.finish_owned_unit(unit_id=child_unit_id)
            self.journeys.record_event(journey_id=journey_id, unit_id=child_unit_id,
                                       event_type="detour_completed")
            if decision.unit_id is not None and decision.resume_question is not None:
                self.journeys.record_event(
                    journey_id=journey_id, unit_id=decision.unit_id, event_type="parent_resumed",
                    axis=decision.axis, payload={"resume_question": decision.resume_question},
                )
            revision = self.journeys.bump_revision(journey_id)
        return TurnResult(journey_id, decision, revision)

    # -- Stage 11: root completion + next root ------------------------------------

    def finish_root(self, *, root_unit_id: int) -> TurnResult:
        """Complete an OWNED root journey and, if another root is pointed, start its journey."""
        journey_id = self.journeys.journey_for_unit(root_unit_id)
        with self.db.transaction():
            decision = self.router.finish_owned_unit(unit_id=root_unit_id)
            self.journeys.record_event(journey_id=journey_id, unit_id=root_unit_id,
                                       event_type="journey_completed")
            self.journeys.set_state(journey_id, "OWNED", completed=True)
            self.journeys.bump_revision(journey_id)
            next_revision = 0
            if decision.next_step is not None and decision.unit_id is not None:
                next_journey = self.journeys.start(decision.unit_id)
                self.journeys.record_event(journey_id=next_journey, unit_id=decision.unit_id,
                                           event_type="journey_started")
                if decision.axis is not None:
                    self.journeys.record_event(journey_id=next_journey, unit_id=decision.unit_id,
                                               event_type="axis_started", axis=decision.axis)
                next_revision = self.journeys.bump_revision(next_journey)
        # Additive, post-commit: seal the owned journey episode and its composite index.
        if self.archive is not None:
            episode = self.archive.next_episode_number(journey_id)
            self.archive.checkpoint_episode(journey_id=journey_id, episode_number=episode, kind="owned")
            self.archive.finalize(journey_id)
        # Auto-graph the next pointed root (independent of archiving).
        if decision.next_step is not None and decision.unit_id is not None:
            self.attach_unit_structure(journey_id=next_journey, unit_id=decision.unit_id)
        return TurnResult(journey_id, decision, next_revision if decision.next_step else 0)

    # -- Stage 11: park / resume --------------------------------------------------

    def park(self, *, unit_id: int) -> TurnResult:
        """Park the live journey: move the stack to handoff and mark the journey PARKED."""
        journey_id = self.journeys.journey_for_unit(unit_id)
        with self.db.transaction():
            self.router.park_current_stack()
            self.journeys.set_state(journey_id, "PARKED")
            self.journeys.record_event(journey_id=journey_id, unit_id=unit_id,
                                       event_type="journey_parked")
            revision = self.journeys.bump_revision(journey_id)
        # Additive, post-commit: immutable episode checkpoint for this park episode.
        if self.archive is not None:
            episode = self.archive.next_episode_number(journey_id)
            self.archive.checkpoint_episode(journey_id=journey_id, episode_number=episode, kind="parked")
        return TurnResult(journey_id, None, revision)

    def resume(self) -> TurnResult:
        """Restore a parked stack and mark the same journey LIVE again."""
        with self.db.transaction():
            decision = self.router.restore_parked_stack()
            if decision.unit_id is None:
                raise InvariantError("resume produced no live unit")
            journey_id = self.journeys.journey_for_unit(decision.unit_id)
            self.journeys.set_state(journey_id, "LIVE")
            self.journeys.record_event(journey_id=journey_id, unit_id=decision.unit_id,
                                       event_type="journey_resumed", axis=decision.axis)
            revision = self.journeys.bump_revision(journey_id)
        return TurnResult(journey_id, decision, revision)

    # -- internals ----------------------------------------------------------------

    def attach_unit_structure(self, *, journey_id: int, unit_id: int) -> None:
        """Auto-attach the deterministic parser graph for a unit, once, if wired.

        Runs outside any route transaction so a parse issue can never roll back a
        tutoring decision. Idempotent (skips units that already have parser nodes) and
        limited to parseable Python sources; other files are simply left ungraphed.
        """
        if self.graph is None or self.config.codebase_root is None:
            return
        unit = self.db.one(
            "SELECT file FROM units WHERE id=? AND session_id=?", (unit_id, self.config.session_id))
        if not unit or not str(unit["file"]).endswith(".py"):
            return
        already = self.db.one(
            "SELECT 1 AS present FROM semantic_nodes WHERE journey_id=? AND unit_id=? AND provenance='parser' LIMIT 1",
            (journey_id, unit_id))
        if already:
            return
        extraction = StructureExtractor(self.config.codebase_root).extract(str(unit["file"]))
        self.graph.ingest_structure(journey_id=journey_id, unit_id=unit_id, extraction=extraction)

    @staticmethod
    def _decision_payload(decision: RouteDecision) -> dict[str, Any]:
        return {
            "next_step": decision.next_step, "unit_id": decision.unit_id, "axis": decision.axis,
            "reason": decision.reason, "highlight": decision.highlight,
            "resume_question": decision.resume_question,
        }

    def _replay_decision(self, journey_id: int, turn_id: str) -> RouteDecision:
        """Reconstruct the committed RouteDecision from the recorded answer_evaluated fact."""
        rows = self.db.query(
            "SELECT payload_json FROM journey_events WHERE journey_id=? AND event_type='answer_evaluated' "
            "ORDER BY id DESC",
            (journey_id,),
        )
        for row in rows:
            payload = json.loads(row["payload_json"])
            decision = payload.get("decision")
            if decision is not None and payload.get("turn_id") == turn_id:
                return RouteDecision(
                    decision["next_step"], decision["unit_id"], decision["axis"],
                    decision["reason"], decision["highlight"], decision["resume_question"],
                )
        raise InvariantError("evaluated turn has no recorded decision to replay")

    def _unit_depth(self, unit_id: int) -> int:
        row = self.db.one("SELECT depth FROM units WHERE id=? AND session_id=?",
                          (unit_id, self.config.session_id))
        if not row:
            raise ValidationError("unit does not belong to this session")
        return int(row["depth"])

    def _record_route_transition(
        self, journey_id: int, graded_unit_id: int, graded_depth: int,
        decision: RouteDecision, stamp: dict[str, Any],
    ) -> None:
        """Emit a typed lifecycle fact for the route the Router just chose."""
        if decision.unit_id is None:
            return
        target = self.db.one("SELECT parent_id,depth FROM units WHERE id=?", (decision.unit_id,))
        if target and target["parent_id"] == graded_unit_id and int(target["depth"]) > graded_depth:
            self.journeys.record_event(
                journey_id=journey_id, unit_id=decision.unit_id, parent_unit_id=graded_unit_id,
                event_type="detour_started", axis=decision.axis,
                payload={"reason": decision.reason},
            )
        elif stamp["category"] == "sibling-hole":
            self.journeys.record_event(
                journey_id=journey_id, unit_id=graded_unit_id, event_type="gap_opened",
                axis=stamp["axis"], payload={"reason": decision.reason},
            )
