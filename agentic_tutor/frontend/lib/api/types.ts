// Current Python storage uses integer IDs; the target control plane uses strings.
// Preserve the wire value, especially for strict reference validation.
export type Id = string | number;
export type Ref = { label: string; snippet: string } & (
  | { kind: "code"; source: { file: string; lo: number; hi: number } }
  | { kind: "test"; source: { editor_id: string; text: string } }
  | { kind: "convo"; source: { message_id: Id } }
);
export interface DriverState {
  status: "awaiting_learner" | "parked" | "done";
  journey_id: Id;
  projection_revision: number;
  turn_id: string | null;
  unit_id: Id | null;
  axis: string | null;
  question: string | null;
  step: string | null;
  highlight: boolean;
  resume_question: string | null;
  reason: string;
}
export interface Codebase {
  id: Id;
  name: string;
  session_id: string | null;
  unit_count: number;
}
export interface Unit {
  id: Id;
  slug: string;
  title: string;
  file: string;
  lo: number;
  hi: number;
  ordinal: number;
  depth: number;
  parent_id: Id | null;
  anchor_kind: string;
  state: string;
}
export interface Message {
  id: Id;
  role: string;
  message_kind: string;
  content: string;
  turn_id: string | null;
  sequence: number;
  status: string;
  axis: string | null;
  thread_kind: "main" | "aside";
  thread_id: string | null;
  refs: Ref[];
}
export interface Lifecycle {
  id: Id;
  unit_id: Id;
  event_type: string;
  axis?: string | null;
  payload_json?: string;
  payload?: Record<string, unknown>;
}
export interface SemanticNode {
  id: Id;
  unit_id: Id;
  kind: string;
  text?: string;
  label?: string;
  status: string;
  axis?: string;
  [key: string]: unknown;
}
export interface Snapshot {
  snapshot_version: 2;
  journey: {
    id: Id;
    root_unit_id: Id;
    state: string;
    projection_revision: number;
  };
  units: Unit[];
  axes: { unit_id: Id; axis: string; verdict: string; ordinal: number }[];
  semantic_nodes: SemanticNode[];
  semantic_edges: Record<string, unknown>[];
  lifecycle: Lifecycle[];
  conversation: Message[];
  aside_threads: {
    id: string;
    journey_id: Id;
    unit_id: Id;
    origin_message_id: Id | null;
    title: string;
  }[];
  aside_turns: {
    id: string;
    thread_id: string;
    status: string;
    learner_message_id: Id;
    reply_message_id: Id | null;
  }[];
  tool_calls: ToolEvent[];
  axis_wording: Record<string, string>;
}
export interface SnapshotUpdate {
  journey_id: Id;
  changed: boolean;
  revision: number;
  snapshot: Snapshot | null;
}
export interface Answer {
  turn_id: string;
  unit_id: Id;
  axis: string;
  question: string;
  answer: string;
  refs?: Ref[];
}
export interface Aside {
  request_id: string;
  unit_id: Id;
  question: string;
  refs?: Ref[];
  thread_id?: string;
  origin_message_id?: Id;
}
export interface AsideAck {
  operation: "aside";
  journey_id: Id;
  thread_id: string;
  request_id: string;
  status: "pending" | "complete";
  learner_message_id: Id;
  reply_message_id: Id | null;
  projection_revision: number;
}
export interface Init {
  target: string;
  document_id: string;
  display_name: string;
  language: string;
}
export interface WorkspaceWrite {
  changed: boolean;
  workspace_revision: number;
  revision_hash: string;
}
export interface ToolEvent {
  turn_id: string;
  capability: string;
  agent?: string;
  step?: string;
  [key: string]: unknown;
}
export interface StreamEvents {
  revision: { revision: number };
  tool: ToolEvent;
  token: { thread_id?: string; turn_id: string; text: string };
}
export interface ScanEvents {
  thinking: { text: string };
  unit: { slug: string; file: string; lo: number; hi: number };
  done: { journey_id: Id };
}
export type Handlers<T> = { [K in keyof T]?: (event: T[K]) => void } & {
  error?: (error: Error) => void;
};
export interface Identity {
  user_id: string | null;
  getToken(): Promise<string | null>;
}
export interface Api {
  codebases(): Promise<Codebase[]>;
  register(body: {
    name: string;
    source: string;
  }): Promise<{ codebase_id: Id; name: string }>;
  open(id: Id): Promise<{ session_id: string }>;
  init(body: Init): Promise<{
    document_id: string;
    display_name: string;
    workspace_revision: number;
  }>;
  map(): Promise<DriverState>;
  resume(): Promise<DriverState>;
  park(
    id: Id,
    unit_id: Id,
  ): Promise<{ status: string; journey_id: Id; projection_revision: number }>;
  snapshot(id: Id, since?: number | null): Promise<SnapshotUpdate>;
  answer(id: Id, body: Answer): Promise<DriverState>;
  aside(id: Id, body: Aside): Promise<AsideAck>;
  workspace(body: {
    expected_revision: number;
    content: string;
  }): Promise<WorkspaceWrite>;
  stream(id: Id, handlers: Handlers<StreamEvents>): () => void;
  scan(handlers: Handlers<ScanEvents>): () => void;
}
