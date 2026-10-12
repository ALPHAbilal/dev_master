// The wire contract between the learner's screen and the backend.
// Page 1 of the backend spec: new_completly_desighn/FRONTEND.md §7.
export type Id = string;

// IDs are written in full, never shortened: "task-3", "issue-1".

// One learner + one imported repository.
export interface Workspace {
  id: Id;
  name: string;
  preparing: "running" | "ready" | "failed";
  tasks_done: number;
  tasks_total: number;
}

// Everything the main screen shows, with one revision number.
export interface Snapshot {
  revision: number;
  workspace: Workspace;
  ladder: LadderTask[];
  where: Where | null;
  story: StoryLine[]; // every task, in order
  conversation: Message[]; // every task, in order
}

// One task of the ladder, with everything the sidebar shows under it.
export interface LadderTask {
  id: Id;
  number: number; // task 3
  title: string; // guests always get the generic error
  goal: string;
  tier: string; // the task crafter's tier, such as "debug"
  files: string[];
  status: "done" | "current" | "later";
  sheet: TaskSheet;
  issues: LadderIssue[]; // the waiting room, in priority order: the server orders it
}

export interface LadderIssue {
  id: Id;
  number: number; // issue 1
  title: string;
  parent_issue_id: Id | null; // null = right under the task
  // now: the focus · on_hold: waiting, or paused with a note · cleared, already_knew: done
  status: "now" | "on_hold" | "cleared" | "already_knew";
}

// Where the learner is now.
export interface Where {
  task_id: Id;
  issue_id: Id | null; // null = on the task itself
  depth: number;
  you_are_here: string; // the current focus: the issue's or the task's title
  tutor: "waiting_for_you" | "answering";
}

// The learner's view of the task sheet. Its private fields stay on the server.
export interface TaskSheet {
  the_job_is_done: Box;
  concepts: SheetConcept[];
}
export interface SheetConcept {
  number: number; // concept 15
  name: string; // loop variables outlive the loop
  checked: boolean;
  boxes: Box[];
}
export interface Box {
  number: number; // box 3
  text: string | null; // a concept's box: null until ticked
  ticked_at_turn: number | null;
}

export interface StoryLine {
  id: Id;
  task_id: Id;
  issue_id: Id | null; // the issue in focus when it happened
  turn: number; // a click opens the conversation at this turn
  depth: number;
  kind: StoryKind;
  text: string;
  picking_up: string | null; // only for came_back
}
export type StoryKind =
  | "started"
  | "did"
  | "ticked"
  | "almost"
  | "found_a_gap"
  | "went_to_learn_first"
  | "needed_first"
  | "saved_for_later"
  | "put_on_hold"
  | "picked_up"
  | "cleared"
  | "already_knew"
  | "came_back"
  | "done";

export interface Message {
  id: Id;
  task_id: Id;
  turn: number;
  role: "learner" | "tutor";
  text: string;
  attachments: Attachment[];
}

// The agents get label + text; source only helps the screen.
export type Attachment = { label: string; text: string } & (
  | {
      kind: "repository_code";
      source: { file: string; first_line: number; last_line: number };
    }
  | { kind: "editor_code"; source: { editor_file: string } }
  | { kind: "conversation"; source: { message_id: Id } }
);

export interface StreamEvents {
  revision: { revision: number }; // fetch the snapshot again
  tutor: { task_id: Id; turn: number; text: string }; // the reply, piece by piece
  tool: { task_id: Id; turn: number; doing: string }; // "reading app.py, lines 600 to 640"
}

export type PreparingStep = "copying" | "concepts" | "tasks" | "ordering";
export interface PreparingEvents {
  step: { name: PreparingStep; state: "running" | "done"; count: number | null };
  concept: { number: number; name: string };
  task: { id: Id; number: number; title: string };
  ready: { tasks_total: number };
  failed: { step: PreparingStep; error: string };
}

export type Handlers<T> = { [K in keyof T]?: (event: T[K]) => void } & {
  error?: (error: Error) => void;
};

export interface Identity {
  user_id: string | null;
  getToken(): Promise<string | null>;
}

export interface SnapshotUpdate {
  changed: boolean;
  revision: number;
  snapshot: Snapshot | null;
}

export interface Api {
  workspaces(): Promise<Workspace[]>;
  importRepository(body: {
    name: string;
    git_url: string;
  }): Promise<{ workspace_id: Id }>;
  preparing(workspace: Id, handlers: Handlers<PreparingEvents>): () => void;
  task(workspace: Id, task: Id): Promise<LadderTask>;
  start(workspace: Id): Promise<{ revision: number }>;
  snapshot(workspace: Id, since?: number | null): Promise<SnapshotUpdate>;
  send(
    workspace: Id,
    body: { client_message_id: string; text: string; attachments: Attachment[] },
  ): Promise<{ turn: number }>;
  stream(workspace: Id, handlers: Handlers<StreamEvents>): () => void;
  stop(workspace: Id): Promise<void>; // the tutor stops its reply where it is
  files(workspace: Id): Promise<string[]>;
  file(workspace: Id, path: string): Promise<{ path: string; text: string }>;
}
