// The Team section's store (3.0.8.0 R2): what `GET team` says (the file,
// the team, its problems and preflight findings), the board of the latest
// run (or the stages, all pending, before the first run) with its status,
// the blocks' status, the run's event lines (the change feed), the open gate
// of each gated stage, the selection the Inspector follows, the selected
// block's change list, the feed's filter chips, the Run problems shown
// inline, the one open dialog and the Start view switch. sync.ts feeds it
// from the routes and the `team` frames.
import { createStore, useStore } from "../../lib/store";
import type { MotionState } from "../../lib/motion";
import type { BlockStatus, Board, ChangeLine, EventKind, EventLine, Finding, Gate, RunStatus, Selection, StageRow, StageSpec, StageState, TeamDialog, TeamInfo } from "./types";

export type FilterKey = "state" | "trigger" | "gate" | "claim" | "change";
export const FILTERS: FilterKey[] = ["state", "trigger", "gate", "claim", "change"];
/** Which event kinds each chip shows; report and note lines always show. */
export const FILTER_KINDS: Record<FilterKey, EventKind[]> = { state: ["state"], trigger: ["trigger"], gate: ["gate"], claim: ["claim"], change: ["change"] };

export type RunProblems = { stage: string; problems: string[]; preflight: boolean; findings: Finding[] } | null;
export type Changes = { block: string; list: ChangeLine[]; next: number; done: boolean; error: string };

export type TeamState = {
  started: boolean;
  loaded: boolean;
  error: string;
  info: TeamInfo | null;
  board: Board | null;
  status: RunStatus | null;
  live: boolean;
  blocks: BlockStatus[];
  events: EventLine[];
  next: number;
  eventsRun: string | null;
  gates: Record<string, Gate>;
  sel: Selection;
  filter: Record<FilterKey, boolean>;
  runProblems: RunProblems;
  changes: Changes | null;
  dialog: TeamDialog;
  busy: string;
  view: "auto" | "start" | "workspace";
  frames: number;
};

export const NONE: never[] = [];

export const team = createStore<TeamState>({
  started: false,
  loaded: false,
  error: "",
  info: null,
  board: null,
  status: null,
  live: false,
  blocks: [],
  events: [],
  next: 0,
  eventsRun: null,
  gates: {},
  sel: null,
  filter: { state: true, trigger: true, gate: true, claim: true, change: true },
  runProblems: null,
  changes: null,
  dialog: null,
  busy: "",
  view: (/[?&]view=(start|workspace)/.exec(location.search)?.[1] as TeamState["view"]) || "auto",
  frames: 0,
});

export function useTeam<S>(pick: (s: TeamState) => S): S {
  return useStore(team, pick);
}

export const openDialog = (dialog: TeamDialog) => team.update(() => ({ dialog }));
export const closeDialog = () => team.update(() => ({ dialog: null }));
export const setView = (view: TeamState["view"]) => team.update(() => ({ view }));

/** The Start view: asked for, or no team file, or a file that does not load or has problems. */
export function showsStart(s: TeamState): boolean {
  if (s.view !== "auto") return s.view === "start";
  const i = s.info;
  return s.loaded && (!i || !i.found || !i.team || i.problems.length > 0);
}

export const doc = (s: TeamState) => s.info?.team || null;
export const rows = (s: TeamState): StageRow[] => s.board?.stages || NONE;
export const rowOf = (s: TeamState, id: string) => rows(s).find((r) => r.id === id);
export const specOf = (s: TeamState, id: string): StageSpec | undefined => doc(s)?.workflow.stages.find((x) => x.id === id);
export const blockOf = (s: TeamState, id: string) => s.blocks.find((b) => b.id === id);
export const memberOf = (s: TeamState, name: string) => doc(s)?.members.find((m) => m.name === name);
export const runOpen = (s: TeamState) => s.board?.state === "open";
export const runningCount = (s: TeamState) => rows(s).filter((r) => r.state === "running").length;
export const gatedRows = (s: TeamState) => rows(s).filter((r) => r.state === "gated");

/** The stage's open gate: from its gate frame, else its last gate line, while the row is gated. */
export function openGate(s: TeamState, id: string): Gate | null {
  const r = rowOf(s, id);
  if (!r || r.state !== "gated") return null;
  return s.gates[id] || null;
}

/** A block's badge: someone writes (amber), held (cyan), free. */
export function claimState(b: BlockStatus | undefined): "writing" | "held" | "free" {
  if (!b?.holders.length) return "free";
  return b.holders.some((h) => h.state === "writing") ? "writing" : "held";
}

/** The motion vocabulary for a stage state (the stage boxes draw their own colours too). */
export function stageMotion(state: StageState | undefined): MotionState {
  return state === "running" ? "working" : state === "gated" ? "waiting" : state === "done" ? "done" : state === "failed" ? "error" : state === "ready" ? "idle" : "none";
}

export const usd = (v: number | null | undefined) => "$" + (Number(v) || 0).toFixed(Number(v) && Number(v) < 0.1 ? 3 : 2);

export function elapsed(sec: number | null | undefined): string {
  const s = Math.max(0, Math.round(Number(sec) || 0));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m${String(s % 60).padStart(2, "0")}s`;
  return `${Math.floor(s / 3600)}h${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}m`;
}

/** The status bar's TEAM line and the section's own line. */
export function statusLine(s: TeamState): string {
  const d = doc(s);
  if (!s.loaded) return "";
  if (!s.info?.found) return "no team file (the Start view makes one)";
  if (!d) return "the team file does not load";
  const run = s.board?.run ? `run ${s.board.run} ${s.board.state}` : "no run yet";
  const n = runningCount(s), g = gatedRows(s).length;
  const parts = [d.name, run];
  if (n) parts.push(`${n} running`);
  if (g) parts.push(`${g} at a gate`);
  if (s.status?.cost_usd) parts.push(usd(s.status.cost_usd));
  return parts.join(" · ");
}
