"""library tests: vocab seeding (frontier = seed, table = truth) and the
generated target.md (a render, never a source)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tutor import DB, dispatch
from tutor.frontier import load
from tutor.library import seed_vocab, render_target_md

FIX = Path(__file__).resolve().parent / "fixtures" / "frontier_pinned_qa.json"


def test_seed_vocab_plants_frontier_lists():
    db = DB()
    seeded = seed_vocab(db, load(FIX))
    assert "enumerate" in seeded
    assert db.one("SELECT status FROM vocab WHERE term='enumerate'")["status"] == "hold"
    assert db.one("SELECT status FROM vocab WHERE term='index'")["status"] == "shown"


def test_seed_vocab_never_downgrades():
    db = DB()
    dispatch(db, "L", "promote_vocab", {"term": "enumerate", "status": "proved"})
    seed_vocab(db, load(FIX))                  # fixture holds 'enumerate' at hold
    assert db.one("SELECT status FROM vocab WHERE term='enumerate'")["status"] == "proved"


def test_render_target_md_reflects_spine():
    db = DB()
    dispatch(db, "M", "set_target", {"codebase_path": "/repo/soufiane_prompts"})
    dispatch(db, "M", "upsert_slice",
             {"slug": "pinned-qa-group", "title": "pinned QA grouping",
              "target_file": "run_prompts.py",
              "concept_prereqs": ["enumerate-index"], "ordinal": 1})
    md = render_target_md(db)
    assert "GENERATED" in md and "/repo/soufiane_prompts" in md
    assert "pinned-qa-group" in md and "enumerate-index" in md
