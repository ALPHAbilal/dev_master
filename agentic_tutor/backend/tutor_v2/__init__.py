"""Tutor v2 backend foundation: no frontend and no Claude SDK dependency."""
from .config import TutorConfig
from .contracts import (
    AXES, EVENT_KINDS, GRADE_CATEGORIES, WAKEUP_AGENTS, validate_action_event,
    validate_archive_manifest, validate_continuation, validate_return, validate_wakeup,
)
from .db import Database
from .domain import (AgentOutput, Axis, Event, Handoff, ReturnStamp, StackFrame, ToolCall,
                     Unit, WakeupPacket, Workspace)
from .errors import (
    CapabilityUnavailableError,
    InvariantError,
    StaleWorkspaceRevisionError,
    TutorV2Error,
    ValidationError,
)
from .routing import RouteDecision, Router
from .packets import CapabilityPolicy, WakeupBuilder
from .parsing import ReturnStampParser
from .recorders import ConversationRecorder, JourneyRecorder, ProbeRecorder, ToolCallRecorder
from .graph_projection import GraphProjection
from .learner_model import LearnerModelService
from .orchestrator import TurnOrchestrator, TurnResult
from .driver import DriverState, TurnDriver
from .factory import AppContext, build_session
from .api import ApiHandlers
from .structure import StructuralEdge, StructuralNode, StructureExtraction, StructureExtractor, reconcile_range
from .semantics import SemanticGraphService
from .journey_reader import AXIS_WORDING, JourneyReader, SNAPSHOT_VERSION
from .journey_archive import (
    ARCHIVE_FORMAT_VERSION, ArchiveReader, EpisodeReceipt, JourneyArchiveReceipt, JourneyArchiveService,
)
from .transport import PollingProjectionFeed, ProjectionUpdate
from .session import DEFAULT_INSTRUCTIONS, SessionRunner, agent_run_from_adapter
from .services import ArchiveReceipt, ArchiveService, EventRecorder, HandoffService, StateReader, WorkspaceService, WorkspaceWrite
from .sdk_runtime import (
    DEFAULT_MODEL, AgentSdkUnavailableError, ClaudeAgentAdapter, LaunchSpec,
    RuntimeSettings, TutorToolGateway,
)

__all__ = [
    "TutorConfig", "Database", "Unit", "Axis", "StackFrame", "Event", "Workspace",
    "Handoff", "WakeupPacket", "ReturnStamp", "TutorV2Error", "ValidationError",
    "InvariantError", "CapabilityUnavailableError", "StaleWorkspaceRevisionError",
    "WorkspaceService", "WorkspaceWrite", "EventRecorder", "ArchiveService",
    "ArchiveReceipt", "HandoffService", "StateReader",
    "AXES", "EVENT_KINDS", "GRADE_CATEGORIES", "WAKEUP_AGENTS", "validate_wakeup",
    "validate_return", "validate_action_event", "validate_continuation",
    "validate_archive_manifest",
    "Router", "RouteDecision",
    "CapabilityPolicy", "WakeupBuilder",
    "ReturnStampParser",
    "ConversationRecorder", "JourneyRecorder", "ProbeRecorder",
    "LearnerModelService", "GraphProjection",
    "TurnOrchestrator", "TurnResult",
    "TurnDriver", "DriverState",
    "AppContext", "build_session", "ApiHandlers",
    "StructuralEdge", "StructuralNode", "StructureExtraction", "StructureExtractor", "reconcile_range",
    "SemanticGraphService",
    "JourneyReader", "AXIS_WORDING", "SNAPSHOT_VERSION",
    "JourneyArchiveService", "ArchiveReader", "EpisodeReceipt", "JourneyArchiveReceipt",
    "ARCHIVE_FORMAT_VERSION",
    "PollingProjectionFeed", "ProjectionUpdate",
    "SessionRunner", "DEFAULT_INSTRUCTIONS", "agent_run_from_adapter",
    "DEFAULT_MODEL", "AgentSdkUnavailableError", "RuntimeSettings", "LaunchSpec",
    "TutorToolGateway", "ClaudeAgentAdapter",
]
