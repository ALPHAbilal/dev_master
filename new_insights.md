This version is much stronger — the tiering and the hybrid code/agent/validated split resolve G1 cleanly, and you correctly made it a full-stack launch, not a frontend milestone. G1–G6 are now addressed. But the settled decisions introduce new gaps where they collide with how the backend actually seals and deletes state. Five real ones:

N1 — Journey boundary ≠ archival boundary. Sharpest gap.
Decision #3 says the map belongs to the root and keeps completed children as nested detour branches with their evidence. But the backend archives per unit: when a child becomes OWNED, it gets its own distill → its own ArchiveService.seal() → and seal() deletes that unit's live events from SQLite (services.py:349-355). So the moment a detour completes mid-session, its evidence leaves the live tables. A current-unit snapshot (Tier 1) reading live state cannot render the completed detour branch the way Decision #3 requires. You must pick one: defer child archival until the root seals, or make the snapshot/reader merge already-sealed child artifacts back in. Undefined today.

N2 — The sealed archive has no conversation slot.
Decision #2 says messages live "in the sealed unit archive." But validate_archive_manifest has a closed key set (contracts.py:268) with no conversation/messages field, and seal() writes only events.jsonl + workspace snapshots. Retaining conversation requires: a messages store (G2), a new manifest key + contract change, and the archive-writer capturing it. None exist. And since messages would live in events(kind='message'), they're subject to the same seal-delete — fine only if the archive file preserves them.

N3 — No code-structure extractor, and range reconciliation is undefined.
Decision #1 mandates deterministic class/method/function extraction in v1. The backend has zero structural extraction — only search_repository (grep-like, sdk_runtime.py:114). That's entirely net-new (AST/tree-sitter). Worse: a unit is an arbitrary line range (lo..hi) that may cut across a class or span several functions. Extracted AST-node ranges won't align 1:1 with unit ranges. Who owns the source anchor when they disagree — the unit slice or the structural node? Unspecified.

N4 — No archive read API.
Decision #2 ("accessible after completion") and the sealed-map boundary both require reading a completed journey back. Post-seal, the journey lives only in archive_root/<slug>/ files. G6's snapshot covers live units; there is no reader over sealed artifacts. Needs a separate archive-reader that reconstructs a journey from manifest.json + events.jsonl.

N5 — Parked resumption also reads from archive, not live state.
The boundary says "a parked root preserves the same map for resumption." But fatigue-switch routes to distill, and seal() deletes events regardless of verdict (OWNED or PARKED). So a parked-then-sealed root loses its live events too; resumption must reconstruct from the archive + handoff payload, not live tables — same dependency as N1/N4. If you don't seal on park, then parked units accumulate live events indefinitely. Either way, needs an explicit rule.

---

What the raport got right that I'll defend: the hybrid producer model (code-extract / agent-judge / backend-validate), retention as a launch requirement not an afterthought, and immutable-evidence-vs-editable-notes (#4, cleanly additive — just a new notes table, no collision).

The through-line of all five gaps is one unmade decision: ArchiveService seals and deletes per unit, but your journey/map is scoped to the root-plus-children. Until that mismatch is resolved — defer-archival vs. merge-on-read — Tier 1's snapshot contract can't actually reconstruct a multi-detour journey. That's the next thing to pin, before any UI.