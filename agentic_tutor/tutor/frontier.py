"""frontier — the one active handoff M writes and L reads (docs/tutor-simulation.md Part C).

Stored as `frontier.json` (machine truth, schema-validated) rather than loose markdown:
M writes it, the schema rejects a partial fill (the empty-keys template IS the schema),
and a `.md` view can be rendered for humans later. The SLICE block is the objective and
is never edited mid-slice; the GAP/GATE/SUBHOLE blocks change under fixed keys.

`load()` reads + validates. `Frontier` is a thin typed view. Pure Python, no SDK.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Required keys enforced when a frontier is loaded (the "schema tool rejects malformed").
_SLICE_REQUIRED = ("slug", "target_file", "spec")
_GAP_REQUIRED = ("concept", "road", "opening_question", "done_when",
                 "justify", "mapping_seed")


class FrontierError(Exception):
    """A malformed / partially-filled frontier. M must fill every required key."""


@dataclass
class Frontier:
    data: dict

    # --- typed accessors ----------------------------------------------------
    @property
    def slice(self) -> dict:
        return self.data["slice"]

    @property
    def gap(self) -> dict | None:
        return self.data.get("gap")            # None = a skip-gap slice (all prereqs owned)

    @property
    def gate(self) -> dict:
        return self.data.get("gate", {})

    @property
    def subhole(self) -> dict:
        return self.data.get("subhole", {}) or {}

    @property
    def slice_slug(self) -> str:
        return self.slice["slug"]

    @property
    def target_file(self) -> str:
        return self.slice["target_file"]

    @property
    def spec_path(self) -> str | None:
        return self.slice.get("spec_path")

    @property
    def has_subhole(self) -> bool:
        return bool(self.subhole.get("concept"))


def load(path: str | Path) -> Frontier:
    raw = json.loads(Path(path).read_text())
    return validate(raw)


def validate(raw: dict) -> Frontier:
    if "slice" not in raw:
        raise FrontierError("frontier has no `slice` block")
    sl = raw["slice"]
    for k in _SLICE_REQUIRED:
        if not sl.get(k):
            raise FrontierError(f"slice.{k} is empty (fill every required key)")
    gap = raw.get("gap")
    if gap is not None:                        # gap optional (skip-gap slice); if present, full
        for k in _GAP_REQUIRED:
            if not gap.get(k):
                raise FrontierError(f"gap.{k} is empty (fill every required key)")
    return Frontier(raw)


def empty_template(slice_slug: str = "") -> dict:
    """The keys-only frontier written at gate PASS (Part C lifecycle: reset)."""
    return {
        "slice": {"slug": slice_slug, "title": "", "target_file": "", "spec": "",
                  "spec_path": "", "why_this_slice": "", "concept_prereqs": []},
        "gap": {"concept": "", "road": "", "zpd_note": "", "opening_question": "",
                "connect_to": [], "simplify_ladder": [], "worth_failing_at": [],
                "just_tell": "", "justify": "", "done_when": "", "mapping_seed": "",
                "vocab_ok": [], "vocab_hold": []},
        "gate": {"gate_when": "", "spec": ""},
        "subhole": {"concept": None, "evidence": None, "plan": None},
    }
