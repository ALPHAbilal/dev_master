// Demo mode: the same contract as live.ts, in memory, playing the task 3 scenario.
import {
  FILES,
  HISTORY,
  TASK_3_START,
  TASK_3_STEPS,
  TASKS,
  WORKSPACE_NAME,
  type CraftedTask,
  type Line,
  type Step,
} from "./demo";
import type {
  Api,
  Attachment,
  Handlers,
  LadderIssue,
  LadderTask,
  Message,
  PreparingEvents,
  StoryLine,
  StreamEvents,
  TaskSheet,
  Where,
  Workspace,
} from "./types";

interface State {
  workspace: Workspace;
  status: Record<string, LadderTask["status"]>;
  ticks: Record<string, Record<number, number>>; // task → box number → turn
  issues: Record<string, LadderIssue[]>;
  story: StoryLine[];
  conversation: Message[];
  where: Where | null;
  turns: Record<string, number>; // task → its last turn
  script: Step[]; // what the current task still has to play
  revision: number;
  sent: Map<string, number>; // client_message_id → turn
  streams: Set<Handlers<StreamEvents>>;
  stopping: boolean;
}

const PLACEHOLDER: Step = {
  learner: null,
  tutor:
    "Demo mode: the scripted turns end here, so this reply is a placeholder.",
  story: [],
};

export function createStubApi(options: { delay?: number } = {}): Api {
  const delay = options.delay ?? 12;
  const sleep = (ms: number) =>
    ms ? new Promise((r) => setTimeout(r, ms)) : Promise.resolve();
  let counter = 0;
  const next = () => String(++counter);
  const copy = <T>(value: T): T => structuredClone(value);
  const crafted = (id: string) => TASKS.find((t) => t.id === id)!;
  const states = new Map<string, State>();

  function fresh(id: string, name: string, preparing: Workspace["preparing"]) {
    const state: State = {
      workspace: { id, name, preparing, tasks_done: 0, tasks_total: TASKS.length },
      status: Object.fromEntries(TASKS.map((t) => [t.id, "later" as const])),
      ticks: Object.fromEntries(TASKS.map((t) => [t.id, {}])),
      issues: Object.fromEntries(TASKS.map((t) => [t.id, []])),
      story: [],
      conversation: [],
      where: null,
      turns: Object.fromEntries(TASKS.map((t) => [t.id, 0])),
      script: [],
      revision: 1,
      sent: new Map(),
      streams: new Set(),
      stopping: false,
    };
    states.set(id, state);
    return state;
  }
  function get(id: string) {
    const state = states.get(id);
    if (!state) throw new Error("Workspace not found");
    return state;
  }
  function commit(s: State) {
    s.revision++;
    s.streams.forEach((h) => h.revision?.({ revision: s.revision }));
  }
  function line(s: State, task_id: string, turn: number, value: Line) {
    const [kind, text, depth, issue_id, picking_up] = value;
    s.story.push({
      id: next(),
      task_id,
      issue_id,
      turn,
      depth,
      kind,
      text,
      picking_up: picking_up ?? null,
    });
  }
  function say(
    s: State,
    task_id: string,
    turn: number,
    role: Message["role"],
    text: string,
    attachments: Attachment[] = [],
  ) {
    s.conversation.push({ id: next(), task_id, turn, role, text, attachments });
  }
  // Card A: a fresh task sheet, the story's first line, the tutor speaks first.
  function open(s: State, task: CraftedTask, step?: Step) {
    s.status[task.id] = "current";
    s.turns[task.id] = 0;
    s.where = {
      task_id: task.id,
      issue_id: null,
      depth: 0,
      you_are_here: task.title,
      tutor: "waiting_for_you",
    };
    const opening = step ?? {
      learner: null,
      tutor: task.opening,
      story: [["started", task.title, 0, null] as Line],
    };
    say(s, task.id, 0, "tutor", opening.tutor);
    apply(s, task.id, 0, opening);
  }
  // Code applies a turn's effects: ticks, issues, story lines, the focus.
  function apply(s: State, task_id: string, turn: number, step: Step) {
    for (const box of step.ticks ?? []) s.ticks[task_id][box] = turn;
    if (step.open_issue) s.issues[task_id].push({ ...step.open_issue });
    for (const [id, status] of step.issue_status ?? []) {
      const issue = s.issues[task_id].find((i) => i.id === id);
      if (issue) issue.status = status;
    }
    for (const value of step.story) line(s, task_id, turn, value);
    if (step.where) s.where = { task_id, ...step.where, tutor: "waiting_for_you" };
    if (step.close_task) {
      s.status[task_id] = "done";
      s.workspace.tasks_done = Object.values(s.status).filter((v) => v === "done").length;
      s.where = null;
    }
  }
  // Replays finished turns without streaming them.
  function replay(s: State, task: CraftedTask, steps: Step[]) {
    open(s, task, steps[0]);
    steps.slice(1).forEach((step, i) => {
      const turn = i + 1;
      s.turns[task.id] = turn;
      if (step.learner) say(s, task.id, turn, "learner", step.learner);
      say(s, task.id, turn, "tutor", step.tutor);
      apply(s, task.id, turn, step);
    });
  }
  function sheet(s: State, task: CraftedTask): TaskSheet {
    const ticks = s.ticks[task.id];
    const box = (b: { number: number; text: string }, always: boolean) => ({
      number: b.number,
      // A concept's box shows its text only once it is ticked (FRONTEND.md, decision 1).
      text: always || ticks[b.number] != null ? b.text : null,
      ticked_at_turn: ticks[b.number] ?? null,
    });
    return {
      the_job_is_done: box(task.job, true),
      concepts: task.concepts.map((c) => ({
        number: c.number,
        name: c.name,
        checked: c.boxes.every((b) => ticks[b.number] != null),
        boxes: c.boxes.map((b) => box(b, false)),
      })),
    };
  }
  function ladder(s: State): LadderTask[] {
    return TASKS.map((t) => ({
      id: t.id,
      number: t.number,
      title: t.title,
      goal: t.goal,
      tier: t.tier,
      files: [...t.files],
      status: s.status[t.id],
      sheet: sheet(s, t),
      issues: copy(s.issues[t.id]),
    }));
  }

  {
    const demo = fresh("demo", WORKSPACE_NAME, "ready");
    for (const past of HISTORY) replay(demo, crafted(past.task_id), past.steps);
    replay(demo, crafted("task-3"), TASK_3_STEPS.slice(0, TASK_3_START));
    demo.script = TASK_3_STEPS.slice(TASK_3_START);
  }

  return {
    workspaces: async () => [...states.values()].map((s) => copy(s.workspace)),
    importRepository: async (body) => {
      if (!/^https:\/\/\S+$/.test(body.git_url))
        throw new Error("Use an https:// repository URL.");
      const state = fresh(`workspace-${next()}`, body.name, "running");
      return { workspace_id: state.workspace.id };
    },
    preparing: (workspace, handlers: Handlers<PreparingEvents>) => {
      const s = get(workspace);
      let stopped = false;
      const pause = () => sleep(delay * 20);
      void (async () => {
        if (s.workspace.preparing !== "ready") {
          const concepts = [
            ...new Map(
              TASKS.flatMap((t) => t.concepts).map((c) => [c.number, c]),
            ).values(),
          ];
          const steps: [PreparingEvents["step"]["name"], number | null][] = [
            ["copying", null],
            ["concepts", concepts.length],
            ["tasks", TASKS.length],
            ["ordering", null],
          ];
          for (const [name, count] of steps) {
            if (stopped) return;
            handlers.step?.({ name, state: "running", count: null });
            await pause();
            if (name === "concepts")
              for (const c of concepts) {
                if (stopped) return;
                handlers.concept?.({ number: c.number, name: c.name });
                await pause();
              }
            if (name === "tasks")
              for (const t of TASKS) {
                if (stopped) return;
                handlers.task?.({ id: t.id, number: t.number, title: t.title });
                await pause();
              }
            handlers.step?.({ name, state: "done", count });
          }
          s.workspace.preparing = "ready";
          commit(s);
        }
        if (!stopped) handlers.ready?.({ tasks_total: TASKS.length });
      })();
      return () => {
        stopped = true;
      };
    },
    task: async (workspace, task) => {
      const found = ladder(get(workspace)).find((t) => t.id === task);
      if (!found) throw new Error("Task not found");
      return found;
    },
    start: async (workspace) => {
      const s = get(workspace);
      if (!Object.values(s.status).some((v) => v !== "later")) {
        open(s, TASKS[0]);
        commit(s);
      }
      return { revision: s.revision };
    },
    snapshot: async (workspace, since) => {
      const s = get(workspace);
      if (since === s.revision)
        return { changed: false, revision: s.revision, snapshot: null };
      return {
        changed: true,
        revision: s.revision,
        snapshot: {
          revision: s.revision,
          workspace: copy(s.workspace),
          ladder: ladder(s),
          where: copy(s.where),
          story: copy(s.story),
          conversation: copy(s.conversation),
        },
      };
    },
    send: async (workspace, body) => {
      const s = get(workspace);
      const seen = s.sent.get(body.client_message_id);
      if (seen != null) return { turn: seen };
      const where = s.where;
      if (!where) throw new Error("Every task is done.");
      if (where.tutor === "answering")
        throw new Error("The tutor is still answering.");
      const task_id = where.task_id,
        turn = ++s.turns[task_id];
      s.sent.set(body.client_message_id, turn);
      say(s, task_id, turn, "learner", body.text, copy(body.attachments));
      where.tutor = "answering";
      s.stopping = false;
      commit(s);
      const step = s.script.shift() ?? PLACEHOLDER;
      for (const doing of step.tools ?? []) {
        s.streams.forEach((h) => h.tool?.({ task_id, turn, doing }));
        await sleep(delay * 15);
      }
      let said = "";
      for (const word of step.tutor.match(/\S+\s*/g) || []) {
        if (s.stopping) break;
        await sleep(delay);
        said += word;
        s.streams.forEach((h) => h.tutor?.({ task_id, turn, text: word }));
      }
      s.stopping = false;
      say(s, task_id, turn, "tutor", said.trimEnd());
      apply(s, task_id, turn, step);
      if (step.close_task) {
        const following = TASKS.find((t) => s.status[t.id] === "later");
        if (following) open(s, following);
      }
      if (s.where) s.where.tutor = "waiting_for_you";
      commit(s);
      return { turn };
    },
    stop: async (workspace) => {
      const s = get(workspace);
      if (s.where?.tutor === "answering") s.stopping = true;
    },
    stream: (workspace, handlers) => {
      const s = get(workspace);
      s.streams.add(handlers);
      return () => {
        s.streams.delete(handlers);
      };
    },
    files: async () => Object.keys(FILES),
    file: async (_workspace, path) => {
      if (FILES[path] == null) throw new Error("File not found");
      return { path, text: FILES[path] };
    },
  };
}
