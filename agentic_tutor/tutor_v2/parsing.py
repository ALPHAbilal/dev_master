"""The strict text-to-stamp bridge at the SDK boundary.

``ClaudeAgentAdapter.run()`` returns ``list[str]`` text blocks; the engine validators
accept dictionaries. ``ReturnStampParser`` owns the explicit, side-effect-free bridge:
it locates exactly one JSON object across the blocks, decodes it, requires the expected
``kind``, and hands it to the existing ``validate_return``. It performs no schema
repair, field inference, verdict normalization, or heuristic retry.
"""
from __future__ import annotations

import json
from typing import Any

from .contracts import validate_return
from .errors import ValidationError

_EXPECTED_KIND = {
    "wakeup.map": "return.map",
    "wakeup.grade": "return.grade",
    "wakeup.distill": "return.distill",
}


class ReturnStampParser:
    """Parse and validate exactly one return stamp from raw model text blocks."""

    def parse(self, blocks: list[str], *, expected_kind: str) -> dict[str, Any]:
        if expected_kind not in set(_EXPECTED_KIND.values()):
            raise ValidationError(f"unsupported expected return kind: {expected_kind}")
        objects = self._json_objects(blocks)
        if not objects:
            raise ValidationError("no JSON return object found in model output")
        if len(objects) > 1:
            raise ValidationError("model output contains multiple JSON objects; refusing to guess")
        candidate = objects[0]
        if not isinstance(candidate, dict):
            raise ValidationError("return stamp must be a JSON object")
        if candidate.get("kind") != expected_kind:
            raise ValidationError(f"expected {expected_kind}, got {candidate.get('kind')!r}")
        return validate_return(candidate)

    def parse_for_step(self, blocks: list[str], *, step: str) -> dict[str, Any]:
        if step not in _EXPECTED_KIND:
            raise ValidationError(f"{step} does not return a parsed stamp")
        return self.parse(blocks, expected_kind=_EXPECTED_KIND[step])

    def _json_objects(self, blocks: list[str]) -> list[Any]:
        """Return every top-level JSON object found across the text blocks.

        A block may be a bare JSON object, or prose containing exactly one fenced or
        inline object. We scan for balanced top-level ``{...}`` spans and decode each;
        ambiguity (more than one) is reported by the caller, never resolved here.
        """
        found: list[Any] = []
        for block in blocks:
            for span in self._balanced_spans(block):
                try:
                    found.append(json.loads(span))
                except json.JSONDecodeError:
                    continue
        return found

    @staticmethod
    def _balanced_spans(text: str) -> list[str]:
        spans: list[str] = []
        depth = 0
        start = -1
        in_string = False
        escape = False
        for index, char in enumerate(text):
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                if depth == 0:
                    start = index
                depth += 1
            elif char == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start >= 0:
                        spans.append(text[start:index + 1])
                        start = -1
        return spans
