Confirmed — zero content diff in those four files (CRLF-only, pre-existing working-tree noise). I did not modify them.

Done. Spec applied and verified.

I read the existing logic across packets.py, contracts.py, semantics.py, graph_projection.py, orchestrator.py, session.py, and the schemas/tests before touching anything, then applied all six steps:

Source changes
- A semantics.py — added set_node_status (only-writer, validated statuses; updated_at column confirmed to exist, so no schema.sql change).
- B contracts.py — added MAP_NODE_CATEGORIES, made map_text required in _validate_grade, and validated it conditionally (object with title/summary for emitting categories, else must be null).
- C schemas/return.grade.json — mirrored map_text into required/properties.
- D graph_projection.py — flipped working-code-wrong-reasoning → ("mechanism", …); rewired on_grade to use the agent's verbatim map_text; deleted _grade_node_text; added on_distill, on_detour, on_parent_resume.
- E orchestrator.py — passed map_text into on_grade; added the on_detour call in the post-commit child-detour branch; added on_distill inside the distill txn; added on_parent_resume in finish_child — all gated on graph_projection is not None.
- F session.py — extended the fallback JUDGE instruction to fill map_text.

Tests — updated every existing grade-stamp fixture (10 files) to carry map_text, fixed the misconception assertion (title now agent-authored), and added the new tests from §3: contract emit/non-emit pairs, mechanism emission, verbatim on_grade text, on_distill disprove+seal, and cross-turn detoured_to/returned_to edges plus replay-idempotency.

Definition of done
- .venv/bin/python -m pytest tests_v2/ -q → 81 passed.
- grep _grade_node_text graph_projection.py → nothing (removed).
- No content diff in routing.py, packets.py, schema.sql, journey_reader.py.

One deviation worth flagging: the spec's §3 asked for the working-code-wrong-reasoning mechan, but that category's Router path requires a firing MECHANISM axis that the sample unitdoesn't have — routing, not map, territory. I tested the emission by calling on_grade directly instead, which keeps the test to what the spec actually changed.