"""ContextManager tests: F7 debris collapse, F2 opening-vs-continue, F1 wipe."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tutor import ContextManager, Turn


def test_f2_first_turn_uses_opening_block():
    cm = ContextManager("L")
    assert cm.is_first_turn
    prompt = cm.render(opening_block="OPEN THE GAP", continue_block="CONTINUE")
    assert "OPEN THE GAP" in prompt and "CONTINUE" not in prompt


def test_f2_later_turn_uses_continue_block():
    cm = ContextManager("L")
    cm.append_learner("for i in range(len(questions)):")
    cm.append_assistant("is there a way to get item and position in one step?")
    assert not cm.is_first_turn
    prompt = cm.render(opening_block="OPEN THE GAP", continue_block="CONTINUE")
    assert "CONTINUE" in prompt and "OPEN THE GAP" not in prompt


def test_f7_collapse_replaces_procedure_with_receipt():
    cm = ContextManager("L")
    cm.append_learner("enumerate pairs them")
    # a db() procedure: menu -> describe -> commit (3 tool turns, one procedure)
    cm.append_tool("[menu: record_probe, ...]", procedure_id="p1")
    cm.append_tool("[schema for record_probe]", procedure_id="p1")
    cm.append_tool("OK. Probe stored (HIT, 1 pushes).", procedure_id="p1",
                   receipt="probe: enumerate-index HIT pushes=1")
    assert cm.tool_turn_count() == 3

    cm.collapse()
    assert cm.tool_turn_count() == 0                      # debris gone
    assert cm.receipts() == ["✓ probe: enumerate-index HIT pushes=1"]
    # the learner turn survives untouched
    assert any(t.kind == "learner" for t in cm.turns)


def test_f7_leaves_incomplete_procedure_alone():
    cm = ContextManager("M")
    cm.append_tool("[menu]", procedure_id="p9")           # no receipt yet -> not complete
    cm.collapse()
    assert cm.tool_turn_count() == 1                      # still there


def test_f7_collapse_only_completed_of_two_procedures():
    cm = ContextManager("L")
    cm.append_tool("[menu]", procedure_id="p1")
    cm.append_tool("done p1", procedure_id="p1", receipt="probe: a HIT")
    cm.append_tool("[menu]", procedure_id="p2")           # p2 not yet committed
    cm.collapse()
    assert "✓ probe: a HIT" in cm.receipts()
    assert cm.tool_turn_count() == 1                      # only p2's open turn remains


def test_f1_wipe_is_a_fresh_manager():
    cm = ContextManager("L")
    cm.append_learner("...")
    cm.append_assistant("...")
    # F1: at slice boundary the orchestrator simply drops cm and makes a new one
    fresh = ContextManager("L")
    assert fresh.turns == [] and fresh.is_first_turn
