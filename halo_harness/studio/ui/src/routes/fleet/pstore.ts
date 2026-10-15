// The Fleet panels' store (3.0.5.0 R4): what the five panels added in R4
// read, beside the map's store (store.ts). The shapes are the R4 routes'
// (studio/fleet_panels_api.py, studio/fleet_extras_api.py): the attention
// queue, costs and caps, health, conflicts and project rooms, the digest.
// The activity log and the timeline lanes are kept here from the feed
// (pload.ts); `dialog` is the one Fleet dialog open (PanelDialogs.tsx).
import { createStore, useStore } from "../../lib/store";
import type { AgentKey } from "./types";

export type AttnRow = {
  id: string;
  kind: string;
  harness: string;
  harness_name: string;
  local: boolean;
  session_id: string | null;
  session: string;
  agent_id: string | null;
  agent: string;
  what: string;
  detail: string;
  since: number;
  keys: Record<string, string>;
  text_for: string | null;
  remote_attached: number;
  target: Record<string, unknown>;
};

export type OpenTarget = { section: string; panel?: string; harness?: string; session_id?: string; agent_id?: string; a?: string; b?: string; file?: string; mission?: string; part?: string | null };

export type CapKey = "per_harness_usd_per_day" | "per_project_usd_per_day" | "fleet_usd_per_day";
export type Reached = { scope: string; key: string; label: string; spent: number; cap: number; sessions: [string, string][]; lifted: boolean };
export type Costs = {
  fleet: number;
  harnesses: { id: string; name: string; local: boolean; usd: number; sessions: number }[];
  projects: { key: string; label: string; usd: number; sessions: number; harnesses: string[] }[];
  sessions: { harness: string; harness_name: string; session_id: string; title: string; project: string; usd: number; started: number; today: boolean }[];
  caps: Record<CapKey, number | null>;
  keys: CapKey[];
  reached: Reached[];
  lifted: string[];
  balances: Record<string, unknown>;
};

export type Provider = { name: string; configured: boolean; reachable: boolean | null; note: string };
export type HealthRow = {
  id: string;
  name: string;
  local: boolean;
  online: boolean;
  version: string;
  host: string;
  os: string;
  cached: boolean;
  status: "ok" | "warn" | "bad" | "unknown";
  python?: string;
  providers: Provider[];
  disk?: { free_gb: number; total_gb: number; free_pct: number } | null;
  sockets?: number | null;
  studio?: { version?: string; running?: boolean } | null;
  checked: number;
  note?: string;
};
export type Health = { harnesses: HealthRow[]; cache_s: number };

export type Ref = { key: AgentKey; harness: string; harness_name: string; session_id: string; agent_id: string; name: string };
export type Conflict = { id: string; repo: string; file: string; a: Ref; b: Ref; since: number; source: string };
export type RoomCard = { harness: string; harness_name: string; session_id: string; branch?: string; dirty?: boolean; ahead?: number; behind?: number; worktree?: string; linked?: boolean };
export type Conflicts = { conflicts: Conflict[]; rooms: { key: string; label: string; cards: RoomCard[] }[] };

export type DigestHarness = {
  id: string;
  name: string;
  local: boolean;
  started: { session_id: string; title: string; ts: number }[];
  ended: { session_id: string; title: string; ts: number }[];
  cost_usd: number;
  decisions: { what: string; answer: string; by: string; ts: number }[];
  files: string[];
  errors: { session_id: string; text: string; ts: number }[];
  handoffs: { action: string; to?: string; issue?: string; path?: string; by?: string; agent?: string; ts: number }[];
  quiet: boolean;
};
export type Digest = {
  since: number;
  until: number;
  harnesses: DigestHarness[];
  totals: { started: number; ended: number; files: number; errors: number; handoffs: number; decisions: number; cost_usd: number };
};

export type LogKind = "state" | "tool" | "text" | "ask" | "error" | "fleet";
export type LogLine = { n: number; ts: number; key: AgentKey; harness: string; session_id: string; agent_id: string; kind: LogKind; text: string };
/** One lane's history: each state from the moment it began (ms). */
export type Seg = { t: number; state: string };

export type Run = { agent_id: string; session_id: string; role?: string | null; bio?: string | null; started?: number; finished?: number; status?: string; is_error?: boolean; cost_usd?: number; task?: string };

export type HandoffOut = { ok: boolean; mode: string; to?: string; title?: string; note?: string; path?: string; issue?: { id?: string; identifier?: string; title?: string; status?: string } };
export type Dialog =
  | { kind: "take_over"; key: AgentKey; label: string }
  | { kind: "hand_to"; key: AgentKey; label: string }
  | { kind: "handed"; label: string; out: HandoffOut }
  | { kind: "message"; hid: string; sid: string; name: string }
  | { kind: "kick"; hid: string; name: string }
  | { kind: "recording"; name: string; url: string; bytes: number; label: string }
  | null;

export type Filter = { harness: string; session: string; agent: string; kind: string };

export type PanelsState = {
  started: boolean;
  attention: AttnRow[];
  attnCount: number | null;
  attnLoaded: boolean;
  attnError: string;
  attnSel: string;
  replyFor: string;
  costs: Costs | null;
  costsError: string;
  health: Health | null;
  healthError: string;
  healthAt: number;
  healthBusy: boolean;
  conflicts: Conflicts | null;
  digest: Digest | null;
  digestOpen: boolean;
  log: LogLine[];
  filter: Filter;
  logFollow: boolean;
  lanes: Record<AgentKey, Seg[]>;
  ticks: Record<AgentKey, number[]>;
  span: 5 | 15 | 60;
  dialog: Dialog;
  history: Run[] | null;
};

export const panels = createStore<PanelsState>({
  started: false,
  attention: [],
  attnCount: null,
  attnLoaded: false,
  attnError: "",
  attnSel: "",
  replyFor: "",
  costs: null,
  costsError: "",
  health: null,
  healthError: "",
  healthAt: 0,
  healthBusy: false,
  conflicts: null,
  digest: null,
  digestOpen: false,
  log: [],
  filter: { harness: "", session: "", agent: "", kind: "" },
  logFollow: true,
  lanes: {},
  ticks: {},
  span: 15,
  dialog: null,
  history: null,
});

export function usePanels<S>(select: (s: PanelsState) => S): S {
  return useStore(panels, select);
}

export const openDialog = (dialog: Dialog) => panels.update(() => ({ dialog }));
export const closeDialog = () => panels.update(() => ({ dialog: null }));

/** "4s", "12m", "3h", "2d" since a unix time in seconds. */
export function age(ts: number, now = Date.now()): string {
  const s = Math.max(0, now / 1000 - (Number(ts) || 0));
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  if (s < 86400) return `${Math.round(s / 3600)}h`;
  return `${Math.round(s / 86400)}d`;
}

/** The attention count: the watcher's (live from its `fleet` frame), else what the tree shows. */
export function useAttnCount(fallback: number): number {
  const n = usePanels((s) => s.attnCount);
  return n ?? fallback;
}
