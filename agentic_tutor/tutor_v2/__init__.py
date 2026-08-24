"""Tutor v2 backend foundation: no frontend and no Claude SDK dependency."""
from .config import TutorConfig
from .contracts import (
    AXES, EVENT_KINDS, GRADE_CATEGORIES, WAKEUP_AGENTS, validate_action_event,
    validate_archive_manifest, validate_continuation, validate_return, validate_wakeup,
)
from .db import Database
from .domain import Axis, Event, Handoff, ReturnStamp, StackFrame, Unit, WakeupPacket, Workspace
from .errors import (
    CapabilityUnavailableError,
    InvariantError,
    StaleWorkspaceRevisionError,
    TutorV2Error,
    ValidationError,
)
from .routing import RouteDecision, Router
from .packets import CapabilityPolicy, WakeupBuilder
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
    "DEFAULT_MODEL", "AgentSdkUnavailableError", "RuntimeSettings", "LaunchSpec",
    "TutorToolGateway", "ClaudeAgentAdapter",
]
