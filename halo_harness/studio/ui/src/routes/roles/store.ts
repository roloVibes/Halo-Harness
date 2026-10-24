// The Roles section's store (3.0.7.0 R2): the lineups, the bios, the model
// catalog (with best-for and gym scores) and the tool names; the lineup
// open in the editor (its saved payload, the edited mapping, the graph and
// the findings of the last validate), the undo / redo history of the edits,
// the card positions and each tier box's collapsed state (the server's
// `layout/<name>`), the bio open in the Bios panel, the probe results, the
// live agents on the cards (routes/fleet/frames.ts feeds them; a replay
// stands in for them while it plays) and the one open dialog.
import { createStore, useStore } from "../../lib/store";
import type {
  Analysis, BioPayload, BioRow, Finding, Graph, GymScore, HistoryRun, LineupPayload, LineupRow, LiveAgent, ModelRow, ModelsStatus, Pos, Probe, Raw, Replay, RolesDialog, StateInfo,
} from "./types";

export type InspectorTab = "assignment" | "lineup" | "live";
export type LiveSub = "thinking" | "working" | "output";
/** 3.0.9.0 R3: what a coach card's Apply filled in (the bio form marks the field; nothing is saved yet). */
export type CoachHint = { bio: string; field: string; value: unknown; run: string; text: string } | null;

export type RolesState = {
  started: boolean;
  loaded: boolean;
  error: string;
  info: StateInfo | null;
  lineups: LineupRow[];
  bios: BioRow[];
  models: ModelRow[];
  modelsLoaded: boolean;
  /** 3.1.4.0 R4: the refs GET models/fallback adds (in use, or the shipped list; not verified), and why GET models failed. */
  fallback: ModelRow[];
  modelsError: string;
  /** A Refresh ran on this page: the selects show what each provider said (until the page reloads). */
  justRefreshed: boolean;
  bestFor: Record<string, string[]>;
  gym: Record<string, GymScore>;
  /** 3.1.9.0 R1: the last Analyze on this page (POST models/analyze). */
  analysis: Analysis | null;
  tools: string[];
  modelsStatus: ModelsStatus | null;
  name: string;
  current: LineupPayload | null;
  raw: Raw | null;
  graph: Graph | null;
  findings: Finding[];
  saveProblems: string[];
  dirty: boolean;
  past: Raw[];
  future: Raw[];
  sel: string;
  tab: InspectorTab;
  positions: Record<string, Pos>;
  collapsed: Record<string, boolean>;
  posFor: string;
  bio: string;
  bioData: BioPayload | null;
  bioDraft: Raw | null;
  bioProblems: string[];
  probe: Record<string, Probe | "running">;
  scope: "user" | "project";
  dialog: RolesDialog;
  busy: string;
  view: "auto" | "start" | "workspace";
  live: LiveAgent[];
  /** 3.1.5.0 R3 (glow.ts): agents that ended but still glow: done for ten seconds, failed until their card is clicked. */
  ended: LiveAgent[];
  watched: string;
  liveSub: LiveSub;
  replay: Replay | null;
  history: { card: string; runs: HistoryRun[] | null; error: string };
  coachHint: CoachHint;
  /** 3.1.1.0 R3: an edit target being opened (shell/edit.ts); the active lineup does not open over it. */
  editing: string;
  /** 3.1.4.0 R4: a model select to move the focus to once it shows (the Inspector's strip, the bio form's MODELS). */
  modelFocus: "" | "strip" | "bio";
  /** 3.1.6.0 R1: the canvas bar's Add tier name field is open; the tier whose name is being edited in its box head;
   *  the tier box menu open (where, and which face: the items or one of its forms). */
  tierAdd: boolean;
  tierRename: string;
  tierMenu: TierMenuAt | null;
};

export type TierMenuAt = { tier: string; x: number; y: number; face: "menu" | "model" | "trigger" | "max" };

export const HISTORY_MAX = 50;
export const NONE: never[] = [];

export const roles = createStore<RolesState>({
  started: false,
  loaded: false,
  error: "",
  info: null,
  lineups: [],
  bios: [],
  models: [],
  modelsLoaded: false,
  fallback: [],
  modelsError: "",
  justRefreshed: false,
  bestFor: {},
  gym: {},
  analysis: null,
  tools: [],
  modelsStatus: null,
  name: "",
  current: null,
  raw: null,
  graph: null,
  findings: [],
  saveProblems: [],
  dirty: false,
  past: [],
  future: [],
  sel: "",
  tab: "assignment",
  positions: {},
  collapsed: {},
  posFor: "",
  bio: "",
  bioData: null,
  bioDraft: null,
  bioProblems: [],
  probe: {},
  scope: "user",
  dialog: null,
  busy: "",
  view: (/[?&]view=(start|workspace)/.exec(location.search)?.[1] as RolesState["view"]) || "auto",
  live: [],
  ended: [],
  watched: "",
  liveSub: "thinking",
  replay: null,
  history: { card: "", runs: null, error: "" },
  coachHint: null,
  editing: "",
  modelFocus: "",
  tierAdd: false,
  tierRename: "",
  tierMenu: null,
});

export function useRoles<S>(pick: (s: RolesState) => S): S {
  return useStore(roles, pick);
}

export const openDialog = (dialog: RolesDialog) => roles.update(() => ({ dialog }));
export const closeDialog = () => roles.update(() => ({ dialog: null }));
export const setView = (view: RolesState["view"]) => roles.update(() => ({ view }));
export const setTab = (tab: InspectorTab) => roles.update((s) => (s.tab === tab ? {} : { tab }));

/** A lineup of your own: not one Halo ships, nor the untouched copy of one Halo puts in ~/.halo/teams. */
export const ownLineups = (s: RolesState) => s.lineups.filter((l) => l.scope !== "template" && !l.shipped_copy);

/** The Start view: asked for, or only shipped lineups exist and none of them is active. */
export function showsStart(s: RolesState): boolean {
  if (s.view !== "auto") return s.view === "start";
  return s.loaded && !ownLineups(s).length && !s.info?.active_team && !s.name;
}

export const shipped = (scope: string | undefined) => scope === "template";
export const scopeLabel = (scope: string | undefined) => (scope === "template" ? "shipped" : scope || "?");

/** The card's lineup key: its alias, else its role (what `tiers[*].members`, routing and the live agents name). */
export const keyOf = (n: { alias: string; role: string }) => n.alias || n.role;

export function nodeById(s: RolesState, id: string) {
  return s.graph?.nodes.find((n) => n.id === id);
}

export const agentsOf = (raw: Raw | null) => (Array.isArray(raw?.agents) ? (raw!.agents as Raw[]) : []);

export const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v ?? null));

export function modelRow(s: RolesState, ref: string): ModelRow | undefined {
  return ref ? s.models.find((m) => m.ref === ref) : undefined;
}

/** "$0.60 / $2.40" per 1M tokens, from the catalog row (the card's model pill). */
export function priceText(m: ModelRow | undefined): string {
  if (!m) return "price ?";
  const f = (v: number | null) => (typeof v === "number" ? "$" + (v < 1 ? v.toFixed(2) : v.toFixed(v < 10 ? 2 : 0)) : "?");
  return `${f(m.price_in)} / ${f(m.price_out)}`;
}

/** One line for the status bar: the lineup, its cards, its problems, saved or not. */
export function statusLine(s: RolesState): string {
  const dflt = s.info?.lineup_default ? s.info?.lineup_in_use || "" : ""; // 3.1.9.0 R2: no team: set -> auto
  if (!s.name || !s.graph) return s.loaded ? (s.info?.active_team ? `active: ${s.info.active_team}` : dflt ? `active: ${dflt} (default)` : "no active lineup (one model for everything)") : "";
  const blocks = s.findings.filter((f) => f.severity === "blocks").length;
  const warns = s.findings.length - blocks;
  const state = blocks ? `${blocks} problem${blocks === 1 ? "" : "s"}` : warns ? `${warns} warning${warns === 1 ? "" : "s"}` : "valid";
  const active = s.info?.active_team === s.name ? " · active" : !s.info?.active_team && dflt === s.name ? " · active (default)" : "";
  return `${s.name}${active} · ${s.graph.nodes.length} cards · ${state}${s.dirty ? " · unsaved" : ""}`;
}
