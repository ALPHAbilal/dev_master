# Archive: superseded designs

Archived 2026-10-09. The current design is `../learning_graph_orchestration_architecture.md`
(v1.1). Everything still useful from these files was merged into it. Folders here mirror where each
file used to live, so `agentic_tutor/docs/MAP.md` came from `dev_master/agentic_tutor/docs/MAP.md`.

| file | what it was | why archived |
|---|---|---|
| `root/new_complelty_desighned.md` | Agentic Layer Spec v0.2 (crafters, workspace, 4 knobs, orchestrator menu, examiner) | Superseded. Crafters, workspace, hard gates, parking and its open questions moved to spec §22–§26. Traps, the server sandbox and the examiner were dropped. |
| `new_completly_desighn/LOOPS.md` | First draft of the loops (2026-10-09) | Replaced by `../LEGO.md`, which carries all of it as pieces, plates and cards |
| `new_completly_desighn/learning_graph_orchestration_architecture.md` | The architecture spec v1.1: the original design and the review decisions | Archived 2026-10-12. LEGO.md, FRONTEND.md and BACKEND_SPEC.md now carry the design; LEGO.md still cites its sections (spec §2, §4, §5, §7C, §20) |
| `new_completly_desighn/t3-orchestrator-map.html`, `t3-tutor-loop.html` | The first T3 pages: the orchestrator map and the tutor loop | Archived 2026-10-12. Replaced by `../t3-agent-walkthrough.html`, built on LEGO.md |
| `agentic_tutor/frontend/*.html`, `scripts/reference-server.cjs` | The HTML prototypes of tutor_v2's screens, and the small server that showed them | Archived 2026-10-12. The real frontend replaced them (FRONTEND.md) |
| `new_completly_desighn/BACKEND_SPEC_v0.1.md` | Backend spec draft 0.1 (decision menu, tutor kit, park and resume, old names) | Replaced on 2026-10-12 by `../BACKEND_SPEC.md` draft 0.2, which builds LEGO.md behind the frontend's contract |
| `new_completly_desighn/t3-graph-variations.html` | Three alternative graph drawings | Rejected; replaced by `../t3-orchestrator-map.html` |
| `agentic_tutor/backend/tutor_v2/TASK_DRIVEN_TUTOR_SPEC.md` | Task-Driven Tutor Spec v0.1 (concepts, 4 rungs, CARTOGRAPHER, EXAMINER) | Superseded by v0.2, then by the current spec. The rungs are listed as open decision §26.6. |
| `agentic_tutor/backend/tutor_v2/TASK_LADDER_EXAMPLE.md` | v0.1 worked example (shortlink repo, concept bank table) | Superseded; its concept table is quoted as an example of concept size |
| `agentic_tutor/backend/tutor_v2/MAPPER_DESIGN.md`, `MAPPER_DESIGN copy.md`, `MAPPER_DESIGN_V2.md`, `MAPPER_SPEC.md` | Scanner designs for tutor_v2 (MAPPER, SLICER/DIMENSIONER) | Never built; replaced by the crafter pipeline |
| `agentic_tutor/docs/MAP.md` | An earlier M/L agent process with gates | Never built; superseded |
| `agentic_tutor/docs/BUILD_PLAN.md` | tutor_v2 completion plan | Done; its "PROPOSAL" status line is stale |
| `agentic_tutor/docs/DESIGN_BRIEF_conversation.md` | Design brief for conversation artifacts | Old design brief |
| `agentic_tutor/docs/outer_loop_gap.md` | Note: "api.py not yet read" | Resolved |

Kept in place because they describe the running tutor_v2, which the migration plan needs:
`agentic_tutor/docs/INTEGRATION_NOTES.md` and `agentic_tutor/docs/SPEC_*.md`.
