# TUTOR — THE INTERFACE (known facts; details later)

Status: STUB. The full interface behavior (how the AI talks, panel layout, etc.)
is defined later. This file captures only what's already decided, because it
changes how some steps work (notably POINT).

## What's decided
- The interface is **VS-Code-like**, with small enhancements for the tutor.
- The learner has **full access to the real codebase** — every file and folder,
  a real editor, not a snippet sandbox.
- **Highlighting is real.** When a unit (or a line/region) is "pointed at", it is
  highlighted **in the actual source file in the editor** — not pasted into chat.
  The learner reads the code where it truly lives.
- The AI's conversational surface (how it phrases things, where messages appear)
  is specified later.

## Consequence for the engine
- **POINT is a UI action, not an LLM call.** Highlighting the unit's real lines
  is done code-side (the interface), so POINT folds into the probe step: code
  highlights `file:lo-hi` in the editor, then TEACHER asks the question. (See
  agents/TEACHER.md.)
- Tools that "read code" still exist for the AGENTS (they must read to teach/
  grade), but the LEARNER reads the code directly in the editor.

## Owed later
- [ ] how the AI talks in the interface (tone, message placement, when it speaks).
- [ ] the "small enhancements" over plain VS Code (what they are).
- [ ] does highlighting support multiple regions / cross-file for INTEGRATION?
