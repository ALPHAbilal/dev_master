"""Stable domain shapes. Later stages add behavior without changing ownership."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Unit:
    id: int
    slug: str
    file: str
    lo: int
    hi: int
    state: str


@dataclass(frozen=True, slots=True)
class Axis:
    unit_id: int
    name: str
    verdict: str
    shaky_count: int


@dataclass(frozen=True, slots=True)
class StackFrame:
    unit_id: int
    depth: int
    resume_q: str | None
    pending: tuple[dict[str, Any], ...] = ()
    hop_budget: int = 0


@dataclass(frozen=True, slots=True)
class Event:
    id: int
    unit_id: int
    kind: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Workspace:
    document_id: str
    display_name: str
    revision: int
    revision_hash: str | None


@dataclass(frozen=True, slots=True)
class Handoff:
    payload: dict[str, Any]
    parked_stack: bool


@dataclass(frozen=True, slots=True)
class WakeupPacket:
    step: str
    agent: str
    context: dict[str, Any] = field(default_factory=dict)
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReturnStamp:
    kind: str
    payload: dict[str, Any]
