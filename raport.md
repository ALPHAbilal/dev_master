G1 — The semantic node/branch graph (§4) has no backend producer. Biggest gap.
Your map shows nodes like CLASS·ConfigLoader, METHOD·load(), CONCEPT·Exceptions with typed edges (creates instances of, passes data to, revealed a gap in). The backend has none of this granularity. A unit is a flat code slice (file, lo, hi) — not a class/method/concept with typed relationships. MAPPER returns only top-level units (depth=0, parent=null); the only real edges the backend knows are parent→child dives and axes of one unit. So the map's granularity is finer than the backend's unit granularity. Nothing emits node-types or branch-labels. §8's lifecycle stream does not fix this — it records chronology, not a concept graph.

G2 — No conversation/message store (§5). There is no transcript or messages table. Agent prose from ClaudeAgentAdapter.run() returns list[str] and is thrown away (sdk_runtime.py:207). events has a message kind but nothing writes teaching text into it. "Conversation view" and every "message ID" reference have no backing store.

G3 — probes is read but never written. WakeupBuilder._recent_probes reads the table, but no INSERT into probes exists anywhere in tutor_v2 (the only writers are the old tutor/ package on a different schema). So "learner questions and answers" (§7) and answer_evaluated evidence are currently unbacked in the engine itself.

G4 — §8 lifecycle stream: correctly scoped, but understated. You flagged it, good. But note: route_grade returns a RouteDecision and writes no chronological record today. This is real net-new work inside the router's transactions — and it only yields transitions, still not G1's concept graph.

G5 — Missing node metadata fields. §4.2 wants confidence, attempts, hints. Backend has only shaky_count (a rough struggle proxy). No hints counter, no confidence field.

G6 — No snapshot/read projection (§9). StateReader exposes only session_summary + unit_axes. There's no method returning ladder + stack + evidence as one snapshot. The whole "UI receives the updated snapshot" contract needs this built.

What IS solidly backed (don't second-guess these): detours (stack push/pop = detour_started/parent_resumed), paused question (resume_q), queued siblings (pending_json), axis verdicts, source ranges + highlight, workspace revisions/hashes, sealed archives.

---

## Recommended production model

The semantic graph should be **hybrid**, not entirely agent-authored.

```text
Code/parser
├─ files, classes, functions, and methods
├─ source ranges
├─ containment/import relationships
└─ other relationships that can be established deterministically

Agent judgment
├─ concepts and learner-facing explanations
├─ why a relationship matters in this unit
├─ misconceptions and corrected beliefs
└─ key takeaways from the learner's journey

Validated backend
├─ checks the schema and permitted relationship types
├─ requires evidence/source references
├─ persists accepted graph changes
└─ remains authoritative for what the UI may display
```

Agent-authored semantic content is acceptable only when it passes a strict contract
and is anchored to real source code, conversation messages, probes, events, tests, or
workspace revisions. The UI must never display an uncommitted model interpretation as
an established fact.

## Recommended implementation tiers

### Tier 1 — Required foundation

Build the durable evidence and read model before the rich graph UI:

- persist tutor, learner, tool, test, and system conversation entries;
- deterministically record every probe and its evaluation;
- append lifecycle events inside the same transactions as router state changes;
- expose a complete current-unit UI snapshot/projection;
- assign stable IDs so map, conversation, code, tests, and evidence can cross-reference
  one another.

### Tier 2 — Reliable basic journey map

Render only concepts already backed by trustworthy core state:

- current unit and learner-facing learning goal;
- axis stages using learner-friendly names;
- probe, teaching, test, misconception, and proof moments;
- prerequisite detours, paused parent questions, and returns;
- workspace/source evidence;
- synchronized map selection, conversation focus, and right-side inspector.

This tier delivers the core interaction without pretending that a detailed semantic
code graph already exists.

### Tier 3 — Rich semantic map

Add fine-grained semantic elements after the evidence foundation is stable:

- deterministic extraction of files, classes, functions, methods, and source ranges;
- typed structural relationships such as contains, imports, and calls where reliable;
- agent-authored concepts, explanations, misconceptions, and "why it matters" edges;
- confidence, attempts, hints, and key-takeaway metadata;
- validation and evidence requirements for every agent-authored node or relationship.

## Additional boundary to define

"Current unit journey" needs one explicit product definition. The recommended model
is that the map belongs to the active **top-level/root unit** and includes temporary
child units as nested prerequisite detours. Completing a child does not replace the
map; it closes its branch and returns focus to the parent's paused question. The map
is sealed when the root unit becomes `OWNED`, and a parked root preserves the same map
for resumption.

## Settled product decisions

1. **Rich semantic graph in the first release.** The initial release must include a
   reliable class/method graph, not postpone it to a later version. Tier 1, Tier 2,
   and the structural portion of Tier 3 therefore form one launch scope. Classes,
   functions, methods, source ranges, and trustworthy structural relationships must
   be extracted deterministically where possible. Agent-authored concepts and
   explanations must remain contract-validated and evidence-anchored.
2. **Permanent conversation retention.** The complete unit conversation remains
   accessible after completion and is preserved in the sealed unit archive alongside
   its messages, evidence references, tests, and workspace revisions. A summary may
   be added for navigation, but it must not replace the original conversation.
3. **Child units remain inside the root journey.** Prerequisite child units appear as
   nested branches in the parent/root unit map. Completing a child closes that branch
   and visibly returns focus to the exact paused parent question; it does not create a
   disconnected learner-facing map.
4. **Learner notes are editable; system evidence is immutable.** Learners may attach,
   edit, and remove personal notes. Tutor-generated nodes, structural relationships,
   lifecycle history, verdicts, source anchors, and evidence remain immutable from the
   learner UI. Personal notes must be visually distinguished from verified system
   content.

## Launch consequence

The first release cannot be treated as a frontend-only milestone. Its minimum
end-to-end scope is:

```text
durable conversation + probes + lifecycle events
                         ↓
deterministic code-structure extraction
                         ↓
validated semantic graph persistence
                         ↓
current-root-unit snapshot and live update stream
                         ↓
synchronized Map / Conversation / Inspector UI
                         ↓
sealed archive containing the complete journey
```
