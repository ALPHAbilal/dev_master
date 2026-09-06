"""Composition root: assemble the whole service graph for one session in one place.

Every test hand-wires the same object graph in its ``_setup`` — Database, WorkspaceService,
Router, WakeupBuilder, the recorders, SemanticGraphService, the archives, the learner model,
the live-map projector, the orchestrator, the session runner, the driver, and the read-side
feed. That wiring is the *only* thing an entrypoint (the API) needs before it can serve a
session, so it lives here once. This module contains no learning logic and makes no decisions:
it constructs objects and hands back the bundle. All behavior stays in the pieces it wires.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import TutorConfig
from .db import Database
from .driver import TurnDriver
from .graph_projection import GraphProjection
from .journey_archive import JourneyArchiveService
from .journey_reader import JourneyReader
from .learner_model import LearnerModelService
from .orchestrator import TurnOrchestrator
from .packets import WakeupBuilder
from .recorders import ToolCallRecorder
from .routing import Router
from .semantics import SemanticGraphService
from .services import ArchiveService, EventRecorder, WorkspaceService
from .session import AgentRun, SessionRunner
from .transport import PollingProjectionFeed


@dataclass(frozen=True, slots=True)
class AppContext:
    """The fully-wired service graph for one session; the API holds one of these."""

    config: TutorConfig
    db: Database
    workspace: WorkspaceService
    orchestrator: TurnOrchestrator
    session: SessionRunner
    driver: TurnDriver
    reader: JourneyReader
    feed: PollingProjectionFeed


def build_session(config: TutorConfig, agent_run: AgentRun) -> AppContext:
    """Construct every service for ``config`` and return them bundled. Pure wiring."""
    db = Database(config.database_path)
    workspace = WorkspaceService(db, config)
    events = EventRecorder(db, config, workspace)
    graph = SemanticGraphService(db, config)

    orchestrator = TurnOrchestrator(
        db, config, Router(db, config),
        graph=graph,
        archive=JourneyArchiveService(db, config),
        unit_archive=ArchiveService(db, config, workspace, events),
        learner_model=LearnerModelService(db, config),
        graph_projection=GraphProjection(graph),
        tool_calls_recorder=ToolCallRecorder(db, config),
    )
    session = SessionRunner(config, WakeupBuilder(db, config), orchestrator, agent_run)
    reader = JourneyReader(db, config)
    return AppContext(
        config=config, db=db, workspace=workspace, orchestrator=orchestrator,
        session=session, driver=TurnDriver(session), reader=reader,
        feed=PollingProjectionFeed(reader),
    )
