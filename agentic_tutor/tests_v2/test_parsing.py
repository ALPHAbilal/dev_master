"""Stage 2 tests: the strict text-to-stamp bridge."""
from __future__ import annotations

import json

import pytest

from tutor_v2 import ReturnStampParser, ValidationError


def _grade(**over):
    stamp = {
        "kind": "return.grade", "axis": "COMPREHEND", "verdict": "SOLID",
        "category": "correct-deep", "evidence_ref": "events:1", "hidden_gap": None,
    }
    stamp.update(over)
    return stamp


def test_parses_single_bare_json_object():
    parser = ReturnStampParser()
    stamp = parser.parse([json.dumps(_grade())], expected_kind="return.grade")
    assert stamp["axis"] == "COMPREHEND" and stamp["verdict"] == "SOLID"


def test_extracts_one_object_embedded_in_prose():
    parser = ReturnStampParser()
    blocks = [f"Here is my judgment.\n{json.dumps(_grade())}\nThat is all."]
    stamp = parser.parse(blocks, expected_kind="return.grade")
    assert stamp["category"] == "correct-deep"


def test_rejects_multiple_objects_without_guessing():
    parser = ReturnStampParser()
    blocks = [json.dumps(_grade()), json.dumps(_grade(verdict="SHAKY", category="shaky"))]
    with pytest.raises(ValidationError, match="multiple"):
        parser.parse(blocks, expected_kind="return.grade")


def test_rejects_prose_only_output():
    parser = ReturnStampParser()
    with pytest.raises(ValidationError, match="no JSON"):
        parser.parse(["I think the learner understood it well."], expected_kind="return.grade")


def test_rejects_wrong_kind():
    parser = ReturnStampParser()
    with pytest.raises(ValidationError, match="expected return.grade"):
        parser.parse([json.dumps({"kind": "return.map"})], expected_kind="return.grade")


def test_does_not_repair_schema_violations():
    parser = ReturnStampParser()
    broken = _grade()
    del broken["evidence_ref"]
    with pytest.raises(ValidationError):
        parser.parse([json.dumps(broken)], expected_kind="return.grade")


def test_ignores_braces_inside_json_strings():
    parser = ReturnStampParser()
    stamp = parser.parse([json.dumps(_grade(evidence_ref="events:{1}"))], expected_kind="return.grade")
    assert stamp["evidence_ref"] == "events:{1}"
