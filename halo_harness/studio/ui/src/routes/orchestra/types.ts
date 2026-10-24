// The Orchestra view's data: the JSON shapes of /api/orchestra/... (studio/
// orchestra_api.py), which are the run folder's own files (docs/ORCHESTRA.md).

export type StepState = "pending" | "running" | "done" | "failed" | "skipped" | "planned";
export type Step = { id: string; kind: string; lane: number | null; state: StepState; label: string; layer?: number };
// 3.0.9.0: an `after` edge joins two worker steps (a lane that starts after another); `label` says what it carries.
export type Edge = { from: string; to: string; kind: "flow" | "loop" | "after"; label?: string };
export type Workflow = { workers: number; steps: Step[]; edges: Edge[]; layers?: number[][] };

export type Goal = {
  what: string;
  done_when: string;
  stop_when: string;
  workers: number;
  return_cap: number;
  test: string;
  test_timeout_s: number;
  files: string[];
  lineup: string;
  lead: string;
  worker: string;
  handoffs?: Record<string, unknown>;
  plan?: "auto" | "review";
};

export type LaneState = "joined" | "writing" | "written" | "in_review" | "waiting" | "merged" | "failed" | "";
export type LaneStep = { state: LaneState; ts: number; elapsed_s: number; text: string };
export type Lane = {
  lane: number;
  job: string;
  title: string;
  claims: string[];
  order: number;
  state: LaneState;
  holder: string;
  branch: string;
  head: string;
  cost_usd: number;
  started: number | null;
  ended: number | null;
  pieces_returned: number;
  written: Record<string, string>;
  error: string;
  history: LaneStep[];
  // 3.0.9.0 (orchestra/handoff.py): what it declares, the jobs it starts after, where it started, what it gave
  handoff?: Handoff;
  after?: string[];
  base?: string;
  gave?: Gave[];
  // 3.1.2.0 R2 (orchestra/stale.py): its upstream was sent back; then re-based onto the new head
  stale?: { upstreams: number[]; jobs: string[]; reason: string; ts: number } | null;
  rebased?: { onto: { lane: number; job: string; head: string }[]; head?: string; tests_ok?: boolean; conflict?: string[]; ts: number } | null;
  // 3.1.8.0 R5 (isolation/lines.py): "isolation: container (<image>)", "secrets: 1password (3 refs)", "tools: ... (by bio X)"
  opt_ins?: string[];
};

export type Give = { name: string; kind: "files" | "summary" | "artifact"; paths?: string[] };
export type Need = { from: string; take: string };
export type Handoff = { gives?: Give[]; needs?: Need[] };
export type Gave = { name: string; kind: string; path: string; bytes: number };

export type Claim = { key: string; holder: string; state: string; ts: number; ttl_s: number; note: string; expires: number };

export type RunEvent = {
  ts: number;
  elapsed_s: number;
  lane: number | null;
  kind: "state" | "claim" | "merge" | "gate" | "report" | "note";
  text: string;
  data: Record<string, unknown>;
};

export type Check = { id: string; ok: boolean | null; detail: string };
export type Report = {
  run_id: string;
  status: "finished" | "stopped";
  stop_reason: string;
  branch: string;
  finished: string | null;
  tests_ok: boolean;
  tests_tail: string;
  cost_usd: number;
  ts: number;
  elapsed_s: number;
  goal_done_when: string;
  lanes: { lane: number; title: string; state: string; pieces_returned: number; cost_usd: number }[];
  checks: Check[];
  /** 3.2.0.0 R5: a workflow run's typed outputs and its block (halo_harness/workflows/outputs.py). */
  artifacts?: ArtifactRow[];
  workflow?: { ref: string; version: string; inputs: Record<string, unknown>; bounds: { stage: string; key: string; value: unknown; enforced: boolean; how: string }[] };
};

export type ArtifactRow = {
  name: string;
  type: string;
  schema: string;
  view: string;
  stage: string;
  lane?: number;
  state: "saved" | "skipped" | "missing";
  path?: string;
  bytes?: number;
  ok?: boolean;
  problems?: string[];
  why?: string;
};

export type Conflict = { lane: number; file: string; attempt: number; judge_session: string; applied: boolean; tests_ok: boolean };
export type Merge = { branch: string; base: string; order: number[]; merged: number[]; finished: string | null; conflicts: Conflict[] };
export type DryRun = { jobs: { id: string; worker: number; title: string; claims: string[] }[]; problems: string[]; stop: string };

// 3.0.9.0 R2: planned = the split waits for the reviewed plan (the plan canvas takes the console's place)
export type RunState = "running" | "planned" | "finished" | "stopped" | "dry run" | "new" | "interrupted";
export type RunRow = { run_id: string; created: number; state: RunState; workers: number; goal_what: string; cost_usd: number };

export type RunPayload = {
  run: { run_id: string; created: number; repo_root: string; lead_holder: string | null; state: RunState; cost_usd: number };
  goal: Goal;
  workflow: Workflow | null;
  split: { base: string; jobs: { id: string; title: string; claims: string[]; worker: number }[] } | null;
  lanes: Lane[];
  claims: Claim[];
  merge: Merge | null;
  report: Report | null;
  dry_run: DryRun | null;
  events_count: number;
  live: boolean;
};

export type RegionState = "claimed" | "writing" | "written" | "merged";
export type Region = {
  key: string;
  lane: number;
  holder: string;
  state: RegionState;
  lane_state: string;
  start_line: number;
  end_line: number;
  text: string[];
};
export type FileView = { path: string; base_ref: string; base: string[]; regions: Region[] };
