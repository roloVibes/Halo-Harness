// The Flow routes' payloads (studio/flow_api.py, flow_model.py; docs/STUDIO.md
// "Flow and Media routes"). Optional fields are the ones a run fills as it goes.

export type StepState = "pending" | "running" | "waiting" | "done" | "failed" | "skipped" | string;
export type FlowStatus = "pending" | "running" | "waiting" | "finished" | "stopped" | "failed" | string;

export type TemplateRow = {
  name: string;
  source: "template" | "user" | "project" | string;
  steps: { id: string; kind: string }[];
  form: Record<string, unknown>;
  budget_usd?: number | null;
  version?: number | null;
  path: string;
  error?: string;
};

export type FlowRunRow = {
  run: string;
  name: string;
  status: FlowStatus;
  created: number;
  cost_usd: number;
  project?: string | null;
  budget_usd?: number | null;
  live: boolean;
  waiting_step?: string;
};

export type FlowStep = { id: string; kind: string; state: StepState };

export type StepRecord = {
  id: string;
  kind: string;
  started?: number | null;
  finished?: number | null;
  cost_usd?: number | null;
  output?: Record<string, unknown> | null;
  error?: string | null;
  rounds?: number | null;
};

export type GateArtboard = { id: string; kind?: string; path?: string; prompt_id?: string; bytes?: number };

export type Gate = {
  id: string;
  step: string;
  round: number;
  position?: string;
  text?: string;
  artboards?: GateArtboard[];
  actions?: string[];
  target?: string;
  opened?: number;
};

export type Artboard = {
  id: string;
  kind?: string;
  step?: string;
  title?: string;
  file: string;
  url: string;
  version: number;
  versions: number[];
  prompt_id?: string | null;
};

export type Post = {
  platform: string;
  text: string;
  title?: string;
  media?: string[];
  dry_run: boolean;
  argv?: string[];
  run?: string;
  step?: string;
  ts?: string;
  integration_id?: string;
  media_urls?: string[];
  post_id?: string | null;
  scheduled_at?: string | null;
  error?: string | null;
};

export type MetricRow = {
  ts: number | string;
  post_id?: string | null;
  platform: string;
  days?: number;
  metrics: Record<string, number | null>;
  run?: string;
  step?: string;
};

export type Report = {
  run: string;
  name?: string;
  project?: string | null;
  project_path?: string | null;
  status: FlowStatus;
  stop_reason?: string | null;
  created?: number;
  finished?: number;
  elapsed_s?: number;
  cost_usd: number;
  budget_usd?: number | null;
  steps?: { id: string; kind: string; state: string; cost_usd?: number; elapsed_s?: number; rounds?: number; error?: string | null }[];
  artboards?: GateArtboard[];
  posts?: { platform: string; dry_run: boolean; chars?: number; media?: number; post_id?: string | null; scheduled_at?: string | null; error?: string | null }[];
  metrics?: { samples?: number; posts?: number; totals?: Record<string, number>; summary?: string };
};

export type FlowRecord = {
  name: string;
  run: string;
  status: FlowStatus;
  cost_usd: number;
  budget_usd?: number | null;
  intake?: Record<string, unknown>;
  steps: FlowStep[];
  project?: string | null;
  created?: number;
};

export type FlowPayload = {
  flow: FlowRecord;
  steps: StepRecord[];
  gate: Gate | null;
  report: Report | null;
  events: number;
  posts: Post[];
  metrics_tail: MetricRow[];
  artboards: Artboard[];
  live: boolean;
  project: { slug: string; path: string } | null;
};

export type FlowEvent = { ts: number; elapsed_s: number; step: string | null; kind: string; text: string; data?: Record<string, unknown> };

export type LlmRow = { ref: string; provider?: string; group?: string };
