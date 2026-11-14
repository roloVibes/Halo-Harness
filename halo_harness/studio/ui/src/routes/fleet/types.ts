// The live shapes: GET live (studio/live_api.py) is {harnesses: [{..., sessions: [{...row, agents: [...]}]}]} -- this
// harness alone; an agent row and a stream entry are agent/agent_registry.py's and agent/agent_transcript.py's.

export type AgentState = "queued" | "running" | "waiting" | "paused" | "done" | "failed" | "stopped";
export const LIVE_STATES = ["queued", "running", "waiting", "paused"];

export type AgentRow = {
  agent_id: string;
  parent?: string | null;
  name?: string | null;
  role?: string | null;
  bio?: string | null;
  lineup?: string | null;
  model?: string | null;
  /** 3.1.9.0 R2: why an `auto` member runs on `model` (models_auto.py), when it was picked. */
  model_reason?: string | null;
  /** 3.1.8.0 R5: its isolation / secrets / tool-list lines (isolation/lines.py), when declared. */
  opt_ins?: string[] | null;
  kind?: string | null;
  task?: string | null;
  since?: number | null;
  state?: AgentState | string | null;
  /** Its model calls (shown as "calls"; a session row's `turns` are the user's turns). */
  turns?: number | null;
  cost_usd?: number | null;
  current?: string | null;
  last_text?: string | null;
  /** Its own tokens: its meter's from each message_end (3.1.8.0 R6), else its transcript's usage lines (fleet/agent_tokens.py). */
  tokens_in?: number | null;
  tokens_out?: number | null;
  /** 3.3.16.0 R3: a square's agent or node (workflows/receipts.py): its name and engine. */
  square?: { name: string; engine: string; does?: string } | null;
  /** 3.3.16.3: the parent's step that started it (agent_hooks.spawn_of): Live boxes the agents of one step. */
  spawn?: { step: string; description?: string; lead?: string } | null;
};

export type Pending = Partial<Record<"permission" | "question" | "plan" | "approval", string[]>> | null;

/** 3.3.5.0 R4: the last request's parts in tokens (agent/prompt_composition.ledger_fields). */
export type Composition = { system: number; memory: number; topic_index: number; tools_schema: number; history: number; user: number; total: number };
/** 3.3.5.0 R4: a preflight card waiting for an answer (agent/preflight.py). */
export type Preflight = { id: string; line: string; switch_to?: string | null; default?: string };
/** 3.3.6.0 R6: the eyes offer waiting for an answer (agent/eyes_offer.py): the line and the three choices. */
export type EyesPending = { id: string; line: string; default?: string;
  choices: { id: "lane" | "describe" | "send"; label: string; what: string; disabled?: boolean }[] };

export type Project = { root?: string | null; repo?: string | null; branch?: string | null; dirty?: boolean | null };

export type SessionRow = {
  session_id: string;
  title?: string | null;
  mode?: string | null;
  kind?: string | null;
  cwd?: string | null;
  started?: number | null;
  harness?: { id?: string; name?: string } | null;
  project?: Project | null;
  parent?: string | null;
  status?: string | null;
  busy?: boolean;
  pending?: Pending;
  model?: string | null;
  /** 3.3.5.0 R0 (e): what the effort level does on its model (`think on`, `effort n/a`, or the level). */
  effort?: string | null;
  cost_usd?: number | null;
  /** 3.3.3.1: false when some model answered with no price (`cost_usd` is then the priced part); `cost_unknown` names those models. */
  cost_complete?: boolean | null;
  cost_unknown?: string[];
  agents_live?: number | null;
  agents?: AgentRow[];
  /** 3.1.4.0 R2 (fleet/local_view.py): the status's own figures, for Session's Cost panel; 3.1.8.0 R6 the
   *  session's own message_end / status frames move them too (figures.ts). `turns`: the user's turns. */
  turns?: number | null;
  tokens_in?: number | null;
  tokens_out?: number | null;
  context_tokens?: number | null;
  context_limit?: number | null;
  /** 3.3.5.0 R4: the last request's composition, and a preflight card waiting for an answer. */
  composition?: Composition | null;
  preflight?: Preflight | null;
  eyes?: EyesPending | null;
};

export type Harness = {
  id: string;
  name?: string | null;
  host?: string | null;
  user?: string | null;
  version?: string | null;
  os?: string | null;
  share?: string | null;
  allow_control?: string | null;
  online?: boolean;
  last_seen?: number | null;
  cost_today?: number | null;
  cost_today_complete?: boolean | null; // 3.4.0.1: false when some model had no price
  cost_today_unknown?: string[];
  version_mismatch?: boolean;
  local?: boolean;
  sessions: SessionRow[];
};

export type FleetView = { harnesses: Harness[] };

/** One transcript entry (R1's shape) or a frame turned into one; `you` marks a steer sent from here. */
export type Entry = {
  kind: string;
  text?: string;
  id?: string | null;
  name?: string | null;
  input?: unknown;
  label?: string;
  task?: string;
  is_error?: boolean;
  /** 3.3.10.0 R2: a tool result's pack verdicts as one line (`policy: deny -- fence: outside the project`). */
  policy?: string;
  ts?: number | null;
  tag?: string | null;
  cmd?: string;
  by?: string;
  mode?: string;
  what?: string;
  reason?: string | null;
  you?: boolean;
};

export type Stream = {
  entries: Entry[];
  loaded: boolean;
  loading: boolean;
  error: string;
  /** agent_event frames arrive for it (it is followed): the raw text/tool frames are skipped. */
  viaEvents: boolean;
  following: boolean;
  tick: number;
};

/** What an agent is doing right now, from the raw frames (Live Roles' glow, the map's tool icon). */
export type Activity = { kind: "typing" | "tool"; tool?: string; ts: number; calls: number };

/** `harness|session|agent`. */
export type AgentKey = string;

export type LitEdge = { from: AgentKey; to: AgentKey; ts: number; kind: "spawn" | "message" | "talk" }; // 3.3.16.2: talk, from the speaker

export type AgentRef = { key: AgentKey; h: Harness; s: SessionRow; a: AgentRow; depth: number };

