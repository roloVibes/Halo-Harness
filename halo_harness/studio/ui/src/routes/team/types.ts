// The Team section's shapes (3.0.8.0 R2), as the R1 routes serve them
// (studio/team_api.py, docs/TEAM.md): the team document, the board and its
// stage rows, the run status, the gate, a block's status, a change line, an
// event line and the `team` frame on the live feed.

export type Member = { name: string; lineup: string; role: string; harness: string | null };
export type BlockKind = "file" | "folder" | "git";
export type BlockSpec = { id: string; kind: BlockKind; path: string; claims: string };
export type StageKind = "agent" | "orchestra" | "flow";
export type StageSpec = {
  id: string;
  kind: StageKind;
  members: string[];
  reads: string[];
  writes: string[];
  trigger: string;
  lead: string;
  gate: string;
  acceptance: Record<string, unknown> | null;
  settle_s: number;
  goal: Record<string, unknown> | null;
  flow: string | null;
  inputs: Record<string, unknown>;
  prompt: string;
};
export type TeamDoc = {
  name: string;
  brief: string;
  members: Member[];
  blocks: BlockSpec[];
  workflow: { stages: StageSpec[] };
  path: string;
  source: string;
  root: string;
};

export type Finding = { id: string; severity: string; text: string; fix?: string };

/** GET team. */
export type TeamInfo = {
  found: boolean;
  path?: string;
  source?: string | null;
  root?: string;
  team: TeamDoc | null;
  problems: string[];
  preflight: Finding[];
  run: string | null;
  live: boolean;
};

export type StageState = "pending" | "ready" | "running" | "gated" | "done" | "failed" | "skipped";
export type GateAnswer = { action: string; text: string; ts: number; round: number };
export type StageRow = {
  id: string;
  kind: StageKind;
  state: StageState;
  trigger: string;
  members: string[];
  lead: string;
  gate: string;
  harness: string | null;
  started: number | null;
  ended: number | null;
  cost_usd: number;
  summary: string;
  error: string;
  round: number;
  waiting: string;
  gate_answer: GateAnswer | null;
};
export type Board = {
  run: string | null;
  team: string;
  created?: number;
  state: "open" | "done" | "stopped" | "none";
  stop_reason?: string;
  runner?: { pid: number; beat: number } | null;
  stages: StageRow[];
};
export type RunStatus = {
  run: string;
  team: string;
  state: string;
  stop_reason: string;
  runner_live: boolean;
  stages: Record<string, string[]>;
  waiting: string[];
  cost_usd: number;
};
/** GET team/board. */
export type BoardReply = { run: string | null; board: Board; status: RunStatus | null; live: boolean };

export type Gate = {
  id: string;
  run: string;
  stage: string;
  round: number;
  gate: string;
  text: string;
  summary: string;
  acceptance: { ok: boolean; note: string } | null;
  actions: string[];
  opened: number;
};

export type ChangeLine = { ts: number; by: string; member: string; stage: string; op: string; key: string; summary: string };
export type Holder = { key: string; holder: string; state: string; expires: number };
export type BlockStatus = BlockSpec & {
  ledger: string;
  exists: boolean;
  holders: Holder[];
  last_change: ChangeLine | null;
  changes_count: number;
  recent: ChangeLine[];
};

export type EventKind = "state" | "claim" | "change" | "gate" | "trigger" | "report" | "note";
export type EventLine = { ts: number; elapsed_s: number; kind: EventKind; stage: string | null; text: string; data: Record<string, unknown> };

/** The `data` of a `team` frame on /api/events. */
export type TeamFrame = {
  action: "stage" | "gate" | "claim" | "change";
  run: string;
  kind: EventKind;
  stage: string | null;
  text: string;
  ts: number;
  data: Record<string, unknown>;
  row?: StageRow | null;
};

export type Selection = { kind: "stage" | "block" | "member"; id: string } | null;

export type TeamDialog =
  | { kind: "stop" }
  | { kind: "validate"; ok: boolean; problems: string[]; preflight: Finding[] }
  | { kind: "file" }
  | { kind: "coach"; run: string } // 3.0.9.0 R3: the post-run coach
  | null;
