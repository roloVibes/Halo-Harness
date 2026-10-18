// The Mission panel's store (3.0.6.0 R8), beside the map's (store.ts) and
// the panels' (pstore.ts): the missions list (summary rows), the one mission
// open in the panel (its document, plan and summary), its report and the
// panel's own choices (the face, the part picked, a part being dragged on
// the map, the file viewer, the stop dialog). The shapes are R7's routes
// (studio/fleet_mission_api.py -> fleet/mission_api.py); mload.ts feeds it.
import { createStore, useStore } from "../../lib/store";

export type MissionState = "drafted" | "planned" | "approved" | "running" | "merging" | "done" | "failed" | "stopped";
export type PartStateName = "planned" | "pending" | "asked" | "running" | "done" | "failed" | "stopped" | "skipped" | "merged";

export type PlanPart = {
  id: string;
  title: string;
  brief: string;
  kind: "repo" | "files";
  harness: string | null;
  harness_name: string | null;
  reason: string;
  needs: string[];
  depends_on: string[];
  claims: string[];
  outputs: string[];
  est_cost_usd: number;
  pinned: boolean;
  unassignable: string | null;
  sequenced?: { after: string; because: string }[];
  take?: "outputs" | "all"; // 3.0.9.0: what it reads of its dependencies (fleet/mission_handoff.py)
};

export type Plan = {
  mission: string;
  created: number;
  attempts: number;
  lead_cost_usd: number;
  prefer: string[];
  harnesses: { harness: string; name: string; local: boolean }[];
  parts: PlanPart[];
  merge_order: string[];
  notes: string[];
};

export type PartRun = {
  state: PartStateName;
  harness?: string | null;
  harness_name?: string | null;
  session_id?: string | null;
  command_id?: string | null;
  via_session?: string | null;
  started?: number | null;
  ended?: number | null;
  cost_usd?: number;
  error?: string | null;
  branch?: string | null;
  files?: string[];
  refused?: number;
  base?: string | null; // 3.0.9.0: the commit a repo part started from
};

export type Conflict = { part: string; file: string; hunks: number; applied: boolean; tests_ok: boolean | null; cost_usd: number };
export type Merge = { ok: boolean; branch: string; order: string[]; merged: string[]; skipped: { part: string; why: string }[]; conflicts: Conflict[]; finished: string | null; missing_outputs: string[]; error: string | null };

export type MissionDoc = {
  id: string;
  goal: string;
  constraints: string;
  prefer: string[];
  budget_usd: number | null;
  state: MissionState;
  created: number;
  updated: number;
  ended: number | null;
  hub: { id: string; name: string };
  repo: { name: string; base: string; branch: string } | null;
  approved_by: string | null;
  plan_cost_usd: number;
  plan_problems?: string[];
  stop_reason: string | null;
  parts: Record<string, PartRun>;
  history: { ts: number; state: string; why: string; by: string }[];
  decisions: { ts: number; what: string; by: string }[];
  merge: Merge | null;
};

export type Summary = {
  id: string;
  goal: string;
  state: MissionState;
  created: number;
  updated: number;
  ended: number | null;
  parts: number;
  part_states: Record<string, number>;
  harnesses: string[];
  cost_usd: number;
  budget_usd: number | null;
  stop_reason: string | null;
};

export type View = { mission: MissionDoc; plan: Plan | null; summary: Summary; running: boolean };

export type ReportPart = { id: string; title: string; kind: string; harness: string; harness_name: string; state: string; cost_usd: number; est_cost_usd: number; duration_s: number | null; files: string[]; error: string | null; pinned: boolean; merged: boolean };
export type Report = {
  mission: string;
  goal: string;
  state: string;
  stop_reason: string | null;
  duration_s: number | null;
  cost: { total_usd: number; plan_usd: number; parts_usd: number; est_usd: number; budget_usd: number | null; over_budget: boolean };
  parts: ReportPart[];
  harnesses: { harness: string; name: string; parts: string[]; cost_usd: number; done: number; failed: number }[];
  decisions: { ts: number; what: string; by: string }[];
  files: string[];
  refused: { part: string; file: string; tool: string; harness: string; ts: number }[];
  failed: { part: string; state: string; error: string }[];
  merge: Merge | null;
  artifacts: string[];
  missing_outputs: string[];
};

export type FileRow = { path: string; size: number; mtime: number };
export type FileText = { path: string; size: number; text: string; truncated: boolean };

export type Face = "auto" | "start" | "plan" | "run" | "report" | "coach"; // coach: 3.0.9.0 R3
/** A part node held on the map: where it was let go (SVG units) while its reassign is in flight. */
export type Drag = { part: string; dx: number; dy: number; pending: boolean };

export type MState = {
  started: boolean;
  list: Summary[] | null;
  listError: string;
  open: string;
  view: View | null;
  viewError: string;
  notHere: string;
  face: Face;
  busy: string;
  problems: string[];
  selPart: string;
  drag: Drag | null;
  report: { report: Report; markdown: string; final: boolean } | null;
  reportError: string;
  files: FileRow[] | null;
  file: FileText | null;
  stopAsk: boolean;
  newFocus: number;
};

export const missions = createStore<MState>({
  started: false,
  list: null,
  listError: "",
  open: "",
  view: null,
  viewError: "",
  notHere: "",
  face: "auto",
  busy: "",
  problems: [],
  selPart: "",
  drag: null,
  report: null,
  reportError: "",
  files: null,
  file: null,
  stopAsk: false,
  newFocus: 0,
});

export function useMissions<S>(pick: (s: MState) => S): S {
  return useStore(missions, pick);
}

export const LIVE: MissionState[] = ["running", "merging"];
export const FINAL: MissionState[] = ["done", "failed", "stopped"];
export const EDITABLE: MissionState[] = ["planned", "approved"];

/** The face a mission opens on by its state (the panel's tabs override it). */
export function faceFor(state: MissionState | undefined): Exclude<Face, "auto"> {
  if (!state) return "start";
  if (LIVE.includes(state)) return "run";
  if (FINAL.includes(state)) return "report";
  return "plan";
}

/** A part's state for the map and the tables: its run state, else `planned` while nothing runs. */
export function partState(v: View | null, pid: string): PartStateName {
  const st = v?.mission.parts?.[pid]?.state;
  if (!st || (st === "pending" && !["approved", ...LIVE].includes(v?.mission.state || ""))) return "planned";
  return st;
}

/** The lib/motion vocabulary for a part: asked waits (amber), running works, failed errs. */
export function partMotion(state: PartStateName): "working" | "waiting" | "error" | "done" | "idle" | "none" {
  if (state === "running") return "working";
  if (state === "asked") return "waiting";
  if (state === "failed") return "error";
  if (state === "done" || state === "merged") return "done";
  if (state === "stopped" || state === "skipped") return "idle";
  return "none";
}

export const usd = (n: number | null | undefined) => `$${(Number(n) || 0).toFixed((Number(n) || 0) < 1 ? 3 : 2)}`;
