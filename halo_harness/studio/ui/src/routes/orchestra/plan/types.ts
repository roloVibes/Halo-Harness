// The reviewed plan's shapes (3.0.9.0 R2), as studio/orchestra_plan_api.py
// answers them: the jobs are split.json's plus R1's hand-off fields and the
// worker's bio / model; a problem names the jobs it is about.
import type { Handoff } from "../types";

export type PlanJob = {
  id: string;
  title: string;
  claims: string[];
  after?: string[];
  handoff?: Handoff;
  bio?: string;
  model?: string;
  worker?: number;
  order?: number;
  est_tokens?: { in: number; out: number }; // 3.1.2.0 R2: the lead's estimate the forecast prices
};

// 3.1.2.0 R2 (orchestra/forecast.py, work/forecast.py): a lane's forecast and the plan's total
export type ForecastLine = {
  lane: number; job: string; model: string; tokens_in: number; tokens_out: number;
  usd: number | null; usd_low: number | null; usd_high: number | null; source: string; priced: boolean;
};
export type ForecastTotal = { usd: number; usd_low: number; usd_high: number; budget_usd: number | null; over: boolean; unpriced: number; units: number };
export type Forecast = { lanes: ForecastLine[]; total: ForecastTotal | null; heuristic?: string };

export type PlanProblem = { jobs: string[]; field: string; text: string };
export type PlanFinding = { id: string; severity: "blocks" | "warns"; text: string; fix: string };
export type PlanDecision = { approved: boolean; reason?: string; jobs?: PlanJob[]; by?: string; ts?: number };

export type PlanPayload = {
  run_id: string;
  state: string;
  planned: boolean;
  mode: "auto" | "review";
  source: "draft" | "split";
  jobs: PlanJob[];
  lead_jobs: PlanJob[];
  problems: PlanProblem[];
  preflight: PlanFinding[];
  units: string[];
  decision: PlanDecision | null;
  forecast?: Forecast;
};
