"""Agentic tutor — the two-agent (M planner / L teacher) tutoring core.

See docs/tutor-simulation.md (pedagogy trace) and docs/tutor-sdk-mapping.md (build spec).
Steps 1-2 built: the 7-table DB, the db() gateway, and the ContextManager.
"""
from .db import DB
from .context_manager import ContextManager, Turn
from .gateway import dispatch, Disclosure, make_db_tool
from .operations import REGISTRY, OpError, menu_for
from .frontier import Frontier, load as load_frontier, validate as validate_frontier, FrontierError
from .routing import build_l_block, gate_wall_decision
from .routing_m import M_CORE, pick_m_turn, build_m_block, tools_for_turn, mark_probes_seen
from .hooks import pretooluse_decision, make_hooks

__all__ = [
    "DB", "ContextManager", "Turn",
    "dispatch", "Disclosure", "make_db_tool",
    "REGISTRY", "OpError", "menu_for",
    "Frontier", "load_frontier", "validate_frontier", "FrontierError",
    "build_l_block", "gate_wall_decision",
    "M_CORE", "pick_m_turn", "build_m_block", "tools_for_turn", "mark_probes_seen",
    "pretooluse_decision", "make_hooks",
]
