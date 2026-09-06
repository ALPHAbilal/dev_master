"""Transport-independent live-update contract for the journey projection.

The first implementation is short polling by projection revision; SSE/WebSocket can
replace it later without changing the UI contract. The transport contains no tutoring or
routing logic — it only asks the reader whether the projection advanced and forwards the
snapshot when it did (proposal §13).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .journey_reader import JourneyReader


@dataclass(frozen=True, slots=True)
class ProjectionUpdate:
    journey_id: int
    changed: bool
    revision: int
    snapshot: dict[str, Any] | None


class PollingProjectionFeed:
    """Revision-gated polling over ``JourneyReader``; returns a snapshot only on change."""

    def __init__(self, reader: JourneyReader) -> None:
        self.reader = reader

    def poll(self, journey_id: int, *, since_revision: int | None = None) -> ProjectionUpdate:
        snapshot = self.reader.read(journey_id, after_revision=since_revision)
        if snapshot is None:
            return ProjectionUpdate(journey_id, False, self.reader.current_revision(journey_id), None)
        return ProjectionUpdate(
            journey_id, True, int(snapshot["journey"]["projection_revision"]), snapshot
        )
