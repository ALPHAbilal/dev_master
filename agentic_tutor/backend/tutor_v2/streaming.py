"""Phase-one SSE: committed projections, never model-token streaming."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from fastapi import Request
from starlette.concurrency import run_in_threadpool

from .factory import AppContext

SSE_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}


def event(name: str, payload: dict[str, Any], identifier: str | None = None) -> str:
    prefix = f"id: {identifier}\n" if identifier else ""
    return f"{prefix}event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@dataclass
class ScanLog:
    # Subscribers have independent cursors; reconnects may replay the latest scan.
    # Retain the complete latest scan so a large map cannot silently lose unit events.
    records: list[tuple[int, str, dict[str, Any]]] = field(default_factory=list)
    sequence: int = 0
    running: bool = False

    def publish(self, name: str, payload: dict[str, Any]) -> None:
        self.sequence += 1
        self.records.append((self.sequence, name, payload))

    def begin(self) -> None:
        self.records.clear()
        self.running = True
        self.publish("thinking", {"text": "Reading codebase…"})


async def journey_events(request: Request, ctx: AppContext, journey_id: int,
                         interval: float) -> AsyncIterator[str]:
    revision, tool_id = -1, 0
    # Reconnects resume the tool cursor. Revision is always sent initially so missed
    # changes are recovered by the client's revision-gated snapshot read.
    last = request.headers.get("last-event-id", "")
    if last.startswith("tool:"):
        try:
            tool_id = max(0, int(last[5:]))
        except ValueError:
            pass
    yield ": connected\n\n"
    heartbeat = 0
    while not await request.is_disconnected():
        current = await run_in_threadpool(ctx.reader.current_revision, journey_id)
        if current > revision:
            revision = current
            yield event("revision", {"revision": revision})
        rows = await run_in_threadpool(
            ctx.db.query,
            "SELECT id,turn_id,capability,agent,step FROM tool_calls WHERE journey_id=? AND id>? ORDER BY id",
            (journey_id, tool_id))
        for row in rows:
            tool_id = row.pop("id")
            yield event("tool", row, f"tool:{tool_id}")
        heartbeat += interval
        if heartbeat >= 15:
            yield ": keepalive\n\n"
            heartbeat = 0
        await asyncio.sleep(interval)


async def scan_events(request: Request, log: ScanLog, interval: float) -> AsyncIterator[str]:
    cursor = 0
    try:
        cursor = max(0, int(request.headers.get("last-event-id", "0")))
    except ValueError:
        pass
    # A server restart resets this in-memory log. Do not let a cursor from the
    # previous process suppress all events in its replacement.
    if cursor > log.sequence:
        cursor = 0
    yield ": connected\n\n"
    heartbeat = 0
    while not await request.is_disconnected():
        for sequence, name, payload in list(log.records):
            if sequence <= cursor:
                continue
            cursor = sequence
            yield event(name, payload, str(sequence))
            if name == "done" or (name == "thinking" and payload.get("text") == "Scan failed; retry the request."):
                return
        heartbeat += interval
        if heartbeat >= 15:
            yield ": keepalive\n\n"
            heartbeat = 0
        await asyncio.sleep(interval)
