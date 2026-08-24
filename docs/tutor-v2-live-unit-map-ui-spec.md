# Tutor v2 — Live Unit Journey Interface Specification

## 1. Purpose

This interface visualizes the learner's complete journey **inside the current unit**.
It is not a map of every unit in the curriculum and it is not a simple linear
timeline. It is a live, interactive concept map showing:

- what the learner encountered;
- how concepts, code elements, decisions, failures, and tests relate;
- what the learner understood or struggled with;
- which prerequisite detours occurred;
- the evidence behind each learning state;
- where the learner is now.

The map and the conversation are synchronized views of the same underlying learning
journey.

## 2. Product principle

```text
WHAT the learner encountered
             +
HOW the learner experienced it
             +
WHY each element is connected
             +
EVIDENCE of what was learned
```

The visualization must represent real `tutor_v2` state. It must never invent
progress, relationships, evidence, or mastery for visual effect.

## 3. Primary layout

```text
┌──────────────┬────────────────────────────────────┬────────────────────────┐
│ Unit Journey │       [ Map | Conversation ]       │ [Tutor | Code | Info] │
│              │                                    │                        │
│ ✓ Discovery  │                                    │ Context for the        │
│ ✓ Explanation│       Interactive central view     │ selected learning      │
│ ◐ Detour     │                                    │ moment                 │
│ ● Current    │                                    │                        │
│ ○ Upcoming   │                                    │                        │
│              │                                    │                        │
│ ⚙ Settings   │                                    │                        │
└──────────────┴────────────────────────────────────┴────────────────────────┘
```

### 3.1 Left rail — unit journey overview

The left rail summarizes the current unit from its beginning to the learner's
present position. It provides navigation anchors, not a second full map.

Each entry should use learner-facing labels such as:

- Explored the code
- Explained what it does
- Needed help with iteration
- Returned to the original question
- Found a failure case
- Proved the idea with a test
- Applying it independently

Selecting an entry selects the corresponding map element or conversation moment.

### 3.2 Center — synchronized views

The center has two modes:

```text
[ MAP ]  ⇄  [ CONVERSATION ]
```

Switching modes must preserve the selected learning element, viewport context, and
right-panel state.

### 3.3 Right panel — contextual inspector

The right panel has three synchronized tabs:

```text
[ TUTOR ]  [ CODE ]  [ INFO ]
```

- **Tutor:** the focused exchange and the learner/tutor evidence attached to it.
- **Code:** the relevant source range or learner workspace revision.
- **Info:** metadata, relationship meaning, status, attempts, tests, and takeaway.

The panel updates whenever a map element, branch, journey entry, conversation
message, or code reference is selected.

## 4. Live unit map

The map grows during the current unit. It begins with the unit's initial learning
goal and accumulates nodes and relationships as the learner interacts with the
tutor.

```text
╭──────────────────── CURRENT UNIT ─────────────────────╮
│ Build a safe configuration loader                     │
│ 64% explored · 4 discoveries · 2 detours · 1 open gap│
╰──────────────────────────┬─────────────────────────────╯
                           │ requires understanding
                           ▼
╭───────────────────────────────────────────────────────╮
│ CLASS · ConfigLoader                            ✓ SOLID│
│ Role: Reads and validates application settings        │
│ Source: config.py · lines 14–48                        │
│ Learned through: explanation + successful test        │
│ Key insight: validation belongs at the boundary       │
╰───────────────┬───────────────────────┬───────────────╯
                │ creates instances of  │ can fail when
                ▼                       ▼
╭────────────────────────╮   ╭──────────────────────────╮
│ METHOD · load()       ✓│   │ FAILURE · Missing key  ◐│
│ Input: file path       │   │ Previous belief:        │
│ Output: Config         │   │ defaults always exist   │
│ Why: centralizes I/O   │   │ Evidence: failed test #2│
╰───────────┬────────────╯   ╰────────────┬─────────────╯
            │ passes data to              │ revealed a gap in
            ▼                             ▼
╭────────────────────────╮   ╭──────────────────────────╮
│ METHOD · validate()  ● │   │ CONCEPT · Exceptions   ✓│
│ YOU ARE HERE            │   │ Detour completed        │
│ Goal: explain ordering  │   │ Returned to parent      │
│ Attempts: 2 · Hints: 1  │   │ Key insight: catch only │
│ Current task: justify   │   │ errors you can handle   │
╰────────────────────────╯   ╰──────────────────────────╯
```

### 4.1 Node types

Supported semantic node types include:

- unit goal;
- file, class, function, or method;
- concept or mechanism;
- design decision or tradeoff;
- learner explanation;
- misconception;
- failure or edge case;
- test or proof;
- prerequisite detour;
- return to a paused question;
- key takeaway.

The initial implementation can render a smaller subset while preserving an
extensible node-type contract.

### 4.2 Node metadata

Every node may contain:

```text
identity
├─ id
├─ type
├─ learner-facing title
└─ concise description

learning state
├─ status
├─ active axis
├─ learner confidence
├─ attempts and hints
└─ first seen / last updated

meaning
├─ role in the current unit
├─ what the learner understood
├─ previous misconception
└─ key takeaway

evidence references
├─ conversation message IDs
├─ probe IDs
├─ event IDs
├─ test result IDs
├─ source file and line range
└─ workspace revision/hash
```

Metadata should be progressively disclosed. The node card shows the most useful
summary; the full detail appears in the right-side Info tab.

### 4.3 Branch metadata

Branches are meaningful relationships, not decorative connector lines.

Examples:

- calls;
- creates;
- passes data to;
- depends on;
- requires understanding;
- fails because;
- disproved by;
- revealed a gap in;
- detoured to;
- returned to;
- proved by;
- improved by.

Every branch may contain:

```text
relationship type
├─ learner-facing label
├─ why this connection matters
├─ when it was discovered
├─ evidence references
├─ confidence
└─ active / completed / unresolved state
```

Selecting a branch focuses both connected nodes and updates the conversation and
right panel to the evidence that established the relationship.

### 4.4 Learner-facing axis names

Backend axis names should not be displayed as the primary UI copy.

| Core axis | Learner-facing wording |
|---|---|
| `COMPREHEND` | What it does |
| `MECHANISM` | How it works |
| `RATIONALE` | Why it was designed this way |
| `JUDGMENT` | When to use it |
| `ROBUSTNESS` | What can break |
| `INTEGRATION` | How it connects |
| `EVOLUTION` | How to improve it |

### 4.5 Visual states

```text
✓  Understood / completed
●  Active — learner is here
◐  Developing / needed guidance
○  Unresolved or not yet explored
↳  Prerequisite detour
↩  Returned to paused question
```

Status must never rely on color alone. Use shape, icon, label, and contrast together.

## 5. Conversation view

Conversation mode displays the complete conversation for the current unit. Selecting
a learning element does not hide unrelated messages; it changes their visual
emphasis.

```text
Earlier conversation…                              DIMMED
─────────────────────────────────────────────────────────

Tutor: What happens if the key is absent?          FOCUSED
Learner: The default value is used.                 FOCUSED
Tutor: Run the missing-key test.                    FOCUSED
Test: KeyError                                      FOCUSED

─────────────────────────────────────────────────────────
Later conversation…                                DIMMED
```

### 5.1 Focus behavior

When an element is selected:

- its relevant message range scrolls into view;
- directly referenced messages stand out;
- supporting context remains moderately visible;
- unrelated history above and below is dimmed, never removed;
- the learner can scroll through the entire conversation;
- a clear action returns to the unfiltered full-history emphasis.

The dimming level must retain readability and accessibility. It should communicate
focus, not make the rest of the history unusable.

### 5.2 Conversation-to-map navigation

Selecting a message or evidence block:

- selects the matching map node or branch;
- preserves the conversation scroll location;
- updates the right-side panel;
- shows all related evidence references;
- offers a one-click switch to the Map view with the same element centered.

## 6. Synchronized selection model

All three regions share one canonical selection state.

```text
Map node selected
      ├─ emphasize node and connected branches
      ├─ dim unrelated map content
      ├─ focus relevant conversation messages
      └─ update Tutor / Code / Info panel

Conversation selected
      ├─ emphasize matching map element
      ├─ update Tutor / Code / Info panel
      └─ preserve conversation scroll position

Code evidence selected
      ├─ emphasize matching node or branch
      ├─ focus the establishing conversation
      └─ show the relevant workspace revision
```

Selection state should have this conceptual shape:

```text
selection
├─ entity kind: node | edge | message | event | source
├─ entity ID
├─ related node IDs
├─ related edge IDs
├─ message IDs
├─ evidence/event IDs
├─ source reference
└─ workspace revision reference
```

## 7. Core product mapping

The interface maps onto the existing `tutor_v2` backend as follows:

| Interface concept | Existing core source |
|---|---|
| Current unit | `meta.current_unit_id` + `units` |
| Unit state | `units.state` |
| Active prerequisite depth | `stack.depth`, `stack.is_top` |
| Paused parent question | `stack.resume_q` |
| Queued related gaps | `stack.pending_json` |
| Learning dimensions | `axes` |
| Axis state and evidence | `axes.verdict`, `shaky_count`, `evidence_ref` |
| Learner questions and answers | `probes` |
| Edits, commands, tests, errors, UI activity | `events` |
| Source reference | `units.file`, `lo`, `hi`, `anchor_kind` |
| Learner workspace version | `meta.workspace_revision`, `workspace_hash` |
| Exact tested versions | event revision hashes + workspace checkpoints |
| Completed proof | sealed archive manifest and event log |

## 8. Required backend addition

The current tables provide most state and evidence, but they do not preserve every
router transition as a first-class chronological record. An append-only lifecycle
event stream should be added so the UI can reconstruct the exact unit journey from
its beginning.

Conceptual event shape:

```text
lifecycle_event
├─ id
├─ session_id
├─ unit_id
├─ parent_unit_id, optional
├─ axis, optional
├─ event_type
├─ learner-facing title
├─ metadata JSON
├─ related message IDs
├─ related probe IDs
├─ related event IDs
├─ source reference, optional
├─ workspace revision/hash, optional
└─ created_at
```

Candidate event types:

- `unit_started`;
- `axis_started`;
- `question_asked`;
- `answer_evaluated`;
- `concept_discovered`;
- `relationship_discovered`;
- `misconception_found`;
- `test_run`;
- `gap_opened`;
- `detour_started`;
- `detour_completed`;
- `parent_resumed`;
- `axis_solidified`;
- `unit_parked`;
- `unit_owned`.

This stream should record deterministic facts emitted by the router and services. It
must not require the UI to infer important history from the latest mutable state.

## 9. Live update behavior

```text
Learner action
      ↓
Tutor evaluates and Router selects the next step
      ↓
State and lifecycle event commit in one transaction
      ↓
UI receives the updated snapshot/event
      ↓
Map animates the precise change
```

Expected updates include:

- add or update a node;
- add a relationship;
- change a node's learning state;
- open a prerequisite branch;
- mark a detour completed;
- animate the return to the parent question;
- attach new evidence;
- move the “You are here” indicator;
- update the focused conversation and right panel.

The transport may initially use short polling and later move to Server-Sent Events or
WebSockets. The UI contract should remain transport-independent.

## 10. Interaction details

### Selecting a node

```text
Click node
  → node stands out
  → direct branches and neighbors remain emphasized
  → unrelated map content dims
  → associated conversation exchange is focused
  → right panel opens the most relevant tab
```

### Selecting a branch

```text
Click branch
  → both endpoint nodes stand out
  → relationship label and explanation appear
  → establishing conversation/evidence is focused
  → source or test evidence is available on the right
```

### Switching center views

```text
Map → Conversation
  → keep selected entity
  → scroll to its primary exchange

Conversation → Map
  → keep selected entity
  → center and emphasize its map representation
```

### Clearing focus

Click empty space, press Escape, or choose “Show full journey” to restore normal
emphasis without losing the learner's position in either view.

## 11. Visual direction

The interface should feel like a focused engineering workbench rather than a generic
course dashboard.

- dark, calm workspace with high-contrast content;
- semantic cards instead of anonymous circles;
- clear typography and concise learner-facing language;
- restrained motion that explains changes;
- smooth pan and zoom for the map;
- glowing or pulsing treatment only for the active location;
- visible relationship labels;
- expandable metadata rather than overloaded cards;
- Monaco/VS Code-style code viewing where appropriate;
- stable layout during live updates to preserve spatial memory.

## 12. Accessibility and usability requirements

- Keyboard navigation between nodes, branches, messages, and panel tabs.
- Visible focus indicators.
- Status communicated through text/icons as well as color.
- Reduced-motion support.
- Dimming that maintains readable contrast.
- Screen-reader labels describing node type, state, and relationships.
- A list-based journey fallback containing the same information as the map.
- No automatic viewport movement while the learner is manually inspecting history;
  instead show a “New activity” affordance.

## 13. Scope boundaries

This interface visualizes the lifecycle of the **current unit**.

It does not initially attempt to:

- render the full curriculum as one giant graph;
- expose internal agent prompts or hidden reasoning;
- replace evidence with AI-generated summaries;
- treat working code alone as mastery;
- allow the UI to mutate router or axis state directly;
- infer historical transitions only from current mutable rows.

## 14. Acceptance criteria

The first complete version is successful when:

1. The learner can see the current unit's journey from its start to the present.
2. Nodes and branches communicate meaning through learner-friendly metadata.
3. The active learning location is immediately understandable.
4. Prerequisite detours and returns are visually explicit.
5. Clicking a map element focuses the exact supporting conversation without hiding
   the rest of the history.
6. Clicking conversation evidence selects the corresponding map element.
7. The right panel updates consistently from any selection source.
8. Switching Map/Conversation preserves the same selection.
9. Live backend changes update the map without a full page refresh.
10. Every visible state and relationship is traceable to real `tutor_v2` data or a
    recorded lifecycle event.

