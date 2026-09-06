import demo from "./demo.json";
import type {
  Api,
  DriverState,
  Snapshot,
  Message,
  AsideAck,
  Handlers,
  StreamEvents,
  ScanEvents,
  Unit,
} from "./types";
export const demoFiles: Record<string, string> = Object.fromEntries(
  Object.entries(demo.FILES).map(([path, f]) => [path, f.code.join("\n")]),
);
export function createStubApi(): Api {
  let revision = 1,
    workspaceRevision = 0,
    content = "",
    counter = 100,
    selected = "demo";
  const codebases = [
    {
      id: "demo",
      name: "run_prompts.py",
      session_id: "demo-session",
      unit_count: 6,
    },
  ];
  const units: Unit[] = demo.CODEBASES[0].units.map((u, i) => ({
    ...u,
    id: i + 1,
    title: u.slug,
    file: "run_prompts.py",
    lo:
      demo.FILES["run_prompts.py"].units.find((v) => v.slug === u.slug)?.lo ||
      0,
    hi:
      demo.FILES["run_prompts.py"].units.find((v) => v.slug === u.slug)?.hi ||
      0,
    ordinal: i,
    depth: 0,
    parent_id: null,
    anchor_kind: "code",
  }));
  let state: DriverState = {
    status: "awaiting_learner",
    journey_id: 1,
    projection_revision: revision,
    turn_id: "stub-turn-1",
    unit_id: 3,
    axis: "ROBUSTNESS",
    question:
      "Now trace one input where a pinned id also appears unpinned. What comes out?",
    step: "wakeup.probe",
    highlight: true,
    resume_question: null,
    reason: "",
  };
  const snapshot: Snapshot = {
    snapshot_version: 2,
    journey: {
      id: 1,
      root_unit_id: 3,
      state: "ACTIVE",
      projection_revision: revision,
    },
    units,
    axes: units.flatMap((unit) =>
      ["COMPREHEND", "MECHANISM", "ROBUSTNESS"].map((axis, ordinal) => ({
        unit_id: unit.id,
        axis,
        ordinal,
        verdict: unit.state === "OWNED" ? "SOLID" : "UNGRADED",
      })),
    ),
    semantic_nodes: [],
    semantic_edges: [],
    lifecycle: [],
    conversation: [],
    aside_threads: [],
    aside_turns: [],
    tool_calls: [],
    axis_wording: {
      COMPREHEND: "What it does",
      MECHANISM: "How it works",
      RATIONALE: "Why it's built this way",
      ROBUSTNESS: "What can break",
    },
  };
  const streams = new Set<Handlers<StreamEvents>>(),
    scans = new Set<Handlers<ScanEvents>>();
  function add(
    role: string,
    text: string,
    thread: string | null = null,
    refs: Message["refs"] = [],
  ): Message {
    const message: Message = {
      id: ++counter,
      role,
      content: text,
      message_kind: "text",
      turn_id: state.turn_id,
      sequence: snapshot.conversation.length + 1,
      status: "COMPLETE",
      axis: state.axis,
      thread_kind: thread ? "aside" : "main",
      thread_id: thread,
      refs,
    };
    snapshot.conversation.push(message);
    return message;
  }
  // Small fixture from the source demo. All subsequent writes use the real contract.
  add(
    "tutor",
    "Before you write it — what does the caller expect back? Shape and order.",
  );
  add(
    "learner",
    "A list of question dicts, pinned first, preserving the passed order.",
  );
  add("tutor", state.question!);
  const codeSample = demo.STREAM.find((item) => item.t === "code");
  if (codeSample && "code" in codeSample)
    add(
      "tutor",
      "Here’s the shape once you dedupe by the value you care about — collapse it if it’s in the way.\n\n```py\n" +
        codeSample.code +
        "```",
    );
  for (const [slug, value] of Object.entries(demo.UNITS)) {
    const unit = units.find((u) => u.slug === slug);
    if (!unit) continue;
    for (const row of value.story)
      snapshot.lifecycle.push({
        id: ++counter,
        unit_id: unit.id,
        event_type: String(row[0]),
        payload: {
          text: row[2],
          axis: row[3],
          depth: row[1],
          resume_question: row[4],
        },
      });
  }
  snapshot.lifecycle = snapshot.lifecycle.filter(
    (e) => e.event_type !== "aside",
  );
  const thread = "demo-aside";
  snapshot.aside_threads.push({
    id: thread,
    journey_id: 1,
    unit_id: 3,
    origin_message_id: snapshot.conversation[0].id,
    title: "How does list.append differ from +?",
  });
  add(
    "learner",
    "Quick one — why out.append(q) and not out = out + [q]?",
    thread,
  );
  add(
    "tutor",
    "append mutates the same list in place; + builds a new list each time.",
    thread,
  );
  snapshot.lifecycle.splice(
    snapshot.lifecycle.findIndex((e) => e.unit_id === 3) + 4,
    0,
    {
      id: ++counter,
      unit_id: 3,
      event_type: "aside",
      payload: {
        thread_id: thread,
        title: snapshot.aside_threads[0].title,
        origin_message_id: snapshot.conversation[0].id,
      },
    },
  );
  const copy = <T>(value: T): T => structuredClone(value);
  function changed() {
    revision++;
    state.projection_revision = revision;
    snapshot.journey.projection_revision = revision;
    streams.forEach((h) => h.revision?.({ revision }));
  }
  async function tokens(text: string, thread_id?: string) {
    streams.forEach((h) =>
      h.tool?.({
        turn_id: state.turn_id!,
        capability: "read_workspace",
        agent: "TEACHER",
        step: state.step!,
      }),
    );
    for (const word of text.match(/\S+\s*/g) || []) {
      await new Promise((r) => setTimeout(r, 12));
      streams.forEach((h) =>
        h.token?.({
          turn_id: state.turn_id!,
          text: word,
          ...(thread_id ? { thread_id } : {}),
        }),
      );
    }
  }
  const acks = new Map<string, AsideAck>();
  return {
    codebases: async () => copy(codebases),
    register: async (body) => {
      const id = `codebase-${++counter}`;
      codebases.push({
        id,
        name: body.name,
        session_id: `${id}-session`,
        unit_count: units.length,
      });
      return { codebase_id: id, name: body.name };
    },
    open: async (id) => {
      const cb = codebases.find((c) => c.id === id);
      if (!cb) throw new Error("Codebase not found");
      selected = cb.id;
      return { session_id: cb.session_id };
    },
    init: async (body) => {
      workspaceRevision = 0;
      return {
        document_id: body.document_id,
        display_name: body.display_name,
        workspace_revision: workspaceRevision,
      };
    },
    map: async () => {
      for (const text of [
        "Reading " +
          (codebases.find((c) => c.id === selected)?.name || "codebase"),
        "Tracing dependencies",
        "Ordering the ladder",
      ]) {
        scans.forEach((h) => h.thinking?.({ text }));
        await new Promise((r) => setTimeout(r, 260));
      }
      for (const u of units) {
        scans.forEach((h) =>
          h.unit?.({ slug: u.slug, file: u.file, lo: u.lo, hi: u.hi }),
        );
        await new Promise((r) => setTimeout(r, 170));
      }
      changed();
      scans.forEach((h) => h.done?.({ journey_id: state.journey_id }));
      return copy(state);
    },
    resume: async () => {
      state.status = "awaiting_learner";
      snapshot.journey.state = "ACTIVE";
      changed();
      return copy(state);
    },
    park: async () => {
      state.status = "parked";
      snapshot.journey.state = "PARKED";
      changed();
      return {
        status: "parked",
        journey_id: state.journey_id,
        projection_revision: revision,
      };
    },
    snapshot: async (id, since) => ({
      journey_id: id,
      changed: since !== revision,
      revision,
      snapshot: since === revision ? null : copy(snapshot),
    }),
    answer: async (_id, body) => {
      if (body.turn_id !== state.turn_id)
        throw new Error("This question has changed. Refresh before answering.");
      add("learner", body.answer, null, body.refs);
      const reply =
        "Stub response: trace the output for two questions with the same id.";
      await tokens(reply);
      state.turn_id = `stub-turn-${++counter}`;
      state.question = reply;
      add("tutor", reply);
      changed();
      return copy(state);
    },
    aside: async (_id, body) => {
      if (acks.has(body.request_id)) return copy(acks.get(body.request_id)!);
      const thread_id = body.thread_id || `aside-${++counter}`;
      if (!body.thread_id) {
        snapshot.aside_threads.push({
          id: thread_id,
          journey_id: state.journey_id,
          unit_id: body.unit_id,
          origin_message_id: body.origin_message_id ?? null,
          title: body.question || "Side question",
        });
        snapshot.lifecycle.push({
          id: ++counter,
          unit_id: body.unit_id,
          event_type: "aside",
          payload: {
            thread_id,
            title: body.question || "Side question",
            origin_message_id: body.origin_message_id,
          },
        });
      }
      const learner = add("learner", body.question, thread_id, body.refs);
      const reply =
        "Stub response: this side question leaves your lesson question unchanged.";
      await tokens(reply, thread_id);
      const tutor = add("tutor", reply, thread_id);
      changed();
      const ack: AsideAck = {
        operation: "aside",
        journey_id: state.journey_id,
        thread_id,
        request_id: body.request_id,
        status: "complete",
        learner_message_id: learner.id,
        reply_message_id: tutor.id,
        projection_revision: revision,
      };
      snapshot.aside_turns.push({
        id: body.request_id,
        thread_id,
        status: "COMPLETE",
        learner_message_id: learner.id,
        reply_message_id: tutor.id,
      });
      acks.set(body.request_id, ack);
      return copy(ack);
    },
    workspace: async (body) => {
      if (body.expected_revision !== workspaceRevision)
        throw new Error("Workspace changed. Reload before submitting.");
      const changed = body.content !== content;
      content = body.content;
      if (changed) workspaceRevision++;
      return {
        changed,
        workspace_revision: workspaceRevision,
        revision_hash: `stub-${workspaceRevision}`,
      };
    },
    stream: (_id, handlers) => {
      streams.add(handlers);
      return () => {
        streams.delete(handlers);
      };
    },
    scan: (handlers) => {
      scans.add(handlers);
      return () => {
        scans.delete(handlers);
      };
    },
  };
}
