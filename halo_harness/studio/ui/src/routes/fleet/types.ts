// The Fleet section's shapes: GET fleet (studio/fleet_hub_api.py, R2) is
// {harnesses: [{..., sessions: [{...row, agents: [...]}]}], hub}; an agent row
// and a stream entry are R1's (agent/agent_registry.py, agent/agent_transcript.py).

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
  kind?: string | null;
  task?: string | null;
  since?: number | null;
  state?: AgentState | string | null;
  turns?: number | null;
  cost_usd?: number | null;
  current?: string | null;
  last_text?: string | null;
  /** 3.1.5.0 R3 (fleet/agent_tokens.py): its own tokens, from its transcript's usage lines. */
  tokens_in?: number | null;
  tokens_out?: number | null;
};

export type Pending = Partial<Record<"permission" | "question" | "plan" | "approval", string[]>> | null;

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
  cost_usd?: number | null;
  agents_live?: number | null;
  agents?: AgentRow[];
  /** 3.1.4.0 R2 (fleet/local_view.py): the status's own figures, for Session's Cost panel. */
  turns?: number | null;
  tokens_in?: number | null;
  tokens_out?: number | null;
  context_tokens?: number | null;
  context_limit?: number | null;
  /** 3.0.6.0: a `mission-worker` session's mission id and part number. */
  mission?: string | null;
  part?: string | number | null;
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
  version_mismatch?: boolean;
  local?: boolean;
  sessions: SessionRow[];
};

export type HubInfo = {
  serving?: boolean;
  name?: string | null;
  url?: string | null;
  port?: number | null;
  members?: number;
  online?: number;
  pair_code_active?: boolean;
  tls?: boolean;
  fingerprint?: string | null;
};

export type FleetView = { harnesses: Harness[]; hub: HubInfo | null };

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

export type LitEdge = { from: AgentKey; to: AgentKey; ts: number; kind: "spawn" | "message" };

export type AgentRef = { key: AgentKey; h: Harness; s: SessionRow; a: AgentRow; depth: number };

