// The shapes the Roles section reads (3.0.7.0 R2), as studio/api.py,
// studio/model.py and studio/models_api.py answer them.

export type Raw = Record<string, unknown>;
export type Entry = { agent?: string; role?: string; as?: string; instances?: number; use_for?: string[]; models?: Raw; [k: string]: unknown };
export type Pos = { x: number; y: number };

export type StateInfo = {
  version: string;
  active_team: string;
  roles_enabled: boolean;
  default_model: string;
  top_sections: string[];
  shipped_lineups: string[];
  shipped_bios: string[];
  /** 3.2.0.0 R2: the packs that run here (a disabled one is absent): one group each in Lineups and Bios. */
  packs?: PackInfo[];
};

export type PackInfo = { id: string; name: string; version: string; scope: string };
/** 3.2.0.0 R2 (studio/packs_roles_api.row_fields): the pack name a file of yours shadows, a clone's origin. */
export type PackFields = { shadows?: string; shadowed_by?: string; from_pack?: string };

export type LineupRow = { name: string; scope: string; description: string; about: string; active: boolean; agents: number; roles: string[]; shipped_copy?: boolean } & PackFields;

export type GraphNode = {
  id: string;
  index: number;
  agent: string;
  role: string;
  alias: string;
  instances: number;
  use_for: string[];
  model: string;
  /** 3.1.4.0 R4: what the card runs on without its own model (its bio's, or 3.1.6.0 its tier's). */
  bio_model?: string;
  /** 3.1.6.0 R1: where `model` / `bio_model` come from: "card", "bio", "tier:<name>", "session", "fallback". */
  model_source?: string;
  inherit_source?: string;
  fallback: string;
  price: string;
  context: string;
  tools: number | null;
  scope: string;
  kind: string;
  description: string;
  problems: string[];
  warnings: string[];
};

export type GraphEdge = { from: string; to: string; kind: "delegation" | "pipeline"; label: string };
/** 3.1.6.0 R1: a tier's trigger, in a bio trigger's shapes plus `on: schedule` (teams_tier_fields.py). */
export type TierTrigger = { on: "schedule" | "file_change" | "event" | "message"; every?: string; cron?: string; paths?: string[]; name?: string; from?: string; prompt?: string; model?: string };
export type Tier = {
  name: string;
  members: string[];
  max_parallel: number | null;
  /** 3.1.6.0 R1: what its members run on unless a card or a pinned bio names a model; null: none. */
  model?: string | null;
  trigger?: TierTrigger | null;
  index: number;
  implicit: boolean;
  node_ids: string[];
};
export type Graph = { nodes: GraphNode[]; edges: GraphEdge[]; tiers: Tier[] };

export type Finding = { id: string; severity: "blocks" | "warns"; text: string; fix: string; node: string };

export type LineupPayload = {
  name: string;
  scope: string;
  path: string;
  active: boolean;
  raw: Raw;
  yaml: string;
  graph: Graph;
  role_table: Record<string, unknown>;
  notes: string[];
  problems: string[];
  findings?: Finding[];
  enforcement: Record<string, [string, string]>;
  layout: Record<string, unknown>;
  /** 3.2.0.0 R2: the pack it comes from ("" for yours): it opens read-only. */
  pack?: string;
};

export type BioRow = { name: string; scope: string; description: string; kind: string; model: string; tools: number;
  capabilities?: string[]; model_problem?: string } & PackFields;
export type BioPayload = { name: string; scope: string; path: string; raw: Raw; resolved: Raw; yaml: string; problems: string[]; kinds: string[];
  pack?: string; model_info?: { capabilities: string[]; ref: string; how: string; problem: string } | null };

export type ModelRow = {
  ref: string;
  provider: string;
  group: string;
  detail: string;
  price_in: number | null;
  price_out: number | null;
  price: string;
  context: string;
  context_tokens: number | null;
  speed: string;
  local: boolean;
  chips: string;
  /** 3.1.4.0 R4: false on a row GET models/fallback adds (a ref in use, or Halo's shipped list): not verified. */
  verified?: boolean;
  source?: "in use" | "shipped";
};

/** 3.1.4.0 R4: one provider's answer to Refresh (studio/models_refresh.py), and what status looked at. */
export type Outcome = { name: string; provider: string; ok: boolean; count: number | null; line: string; ms: number; pending?: boolean; skipped?: boolean };
export type LookedAt = { name: string; label: string; ok: boolean; line: string };
export type ModelsStatus = {
  rows: number;
  providers: { name: string; label: string; enabled: boolean; credentials: boolean; status: string; model_count: number | null }[];
  reason: string;
  looked_at?: LookedAt[];
  refreshed_at?: number | null;
  outcomes?: Outcome[];
};
export type Probe = { ok: boolean; latency_ms: number | null; error: string; cost_line: string; ref: string; reply: string };
export type GymScore = { score: number; tokens_per_second: number | null };

export type RolesDialog =
  | null
  | { kind: "new-lineup"; from: string }
  | { kind: "dup-lineup"; from: string }
  | { kind: "delete-lineup"; name: string }
  | { kind: "apply" }
  | { kind: "new-bio"; from: string }
  | { kind: "dup-bio"; from: string }
  | { kind: "delete-bio"; name: string }
  | { kind: "delete-card"; node: string }
  | { kind: "discard"; then: string }
  /** 3.2.0.0 R2: Clone or Customize met a name that is yours (or Halo's): replace it, or pick another. */
  | { kind: "clone-exists"; what: "bio" | "lineup"; name: string; target: string; shipped: boolean; error: string; open: boolean };

/** A live agent on a card (routes/fleet/frames.ts liveRows, or a replay frame). */
export type LiveAgent = {
  key: string;
  harness: string;
  session: string;
  session_id: string;
  agent_id: string;
  parent: string | null;
  name: string;
  role: string;
  bio: string;
  lineup: string;
  model: string;
  state: string;
  task: string;
  current: string;
  cost_usd: number;
  since: number;
  activity: string;
  tool: string;
  calls: number;
  control: string;
  /** 3.1.5.0 R3: when it ended (ms), for the done glow's ten-second fade (glow.ts). */
  endedAt?: number;
};

export type ReplayMeta = { harness: string; session_id: string; title: string; started: number; ended: number; cost_usd: number; agents: Raw[]; costs: { t: number; usd: number }[] };
export type ReplayEvent = { t: number; agent_id: string; state: string; activity?: string; tool?: string };
export type Replay = { meta: ReplayMeta; events: ReplayEvent[]; t: number; t0: number; t1: number; speed: number; playing: boolean };

export type HistoryRun = { session_id?: string; bio?: string; role?: string; status?: string; is_error?: boolean; cost_usd?: number; task?: string; started?: number; finished?: number };
