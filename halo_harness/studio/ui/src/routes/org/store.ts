// The Org section's store (3.0.7.0 R3): Studio's Paperclip status, the
// linked company and its agents, issues, goals and projects (fed by the
// diffed poller, sync.ts), the card positions of the canvas (the server's
// `layout/pc:<company id>`), what the Inspector shows, the open dialog and
// the install log. Org (Alt+3) reads only this.
import { createStore, useStore } from "../../lib/store";
import type { Agent, Company, Goal, Issue, OrgDialog, PcStatus, Pos, Project, Sel, WorkTab } from "./types";

export type OrgState = {
  started: boolean;
  loaded: boolean;
  status: PcStatus | null;
  company: Company | null;
  agents: Agent[];
  issues: Issue[];
  goals: Goal[];
  projects: Project[];
  /** Saved and dragged card positions (world px), per agent id. */
  positions: Record<string, Pos>;
  /** The company whose positions are loaded. */
  posFor: string;
  sel: Sel;
  tab: WorkTab;
  /** Only the selected agent's issues in the Issues tab. */
  mine: boolean;
  view: "auto" | "workspace";
  error: string;
  dialog: OrgDialog;
  lineups: string[];
  installLog: string[];
  installing: boolean;
  busy: string;
};

export const NONE: never[] = [];

export const org = createStore<OrgState>({
  started: false,
  loaded: false,
  status: null,
  company: null,
  agents: [],
  issues: [],
  goals: [],
  projects: [],
  positions: {},
  posFor: "",
  sel: null,
  tab: "issues",
  mine: false,
  view: "auto",
  error: "",
  dialog: null,
  lineups: [],
  installLog: [],
  installing: false,
  busy: "",
});

export function useOrg<S>(select: (s: OrgState) => S): S {
  return useStore(org, select);
}

/** The company Studio shows: the linked one, when Paperclip has it. */
export function linkedId(s: OrgState): string {
  const st = s.status;
  if (!st || !st.reachable || !st.company_id) return "";
  return st.companies.some((c) => c.id === st.company_id) ? st.company_id : "";
}

/** The Start view stands in for the panels while Paperclip is not running or no company is linked. */
export function showsStart(s: OrgState): boolean {
  return s.loaded && s.view !== "workspace" && !linkedId(s);
}

export const setView = (view: OrgState["view"]) => org.update(() => ({ view }));
export const openDialog = (dialog: OrgDialog) => org.update(() => ({ dialog }));
export const closeDialog = () => org.update(() => ({ dialog: null }));

export function agentById(s: OrgState, id: string | null | undefined): Agent | undefined {
  return id ? s.agents.find((a) => a.id === id) : undefined;
}

export const usd = (cents?: number | null, digits = 2) => "$" + ((Number(cents) || 0) / 100).toFixed(digits);

/** The Paperclip page of the company, an agent or an issue (opens in a new tab). */
export function pcUrl(s: OrgState, kind?: "agents" | "issues", ref?: string): string {
  const base = (s.status?.base_url || "").replace(/\/+$/, "");
  const prefix = s.company?.issuePrefix || s.company?.id || "";
  return [base, prefix, ...(kind && ref ? [kind, ref] : [])].filter(Boolean).join("/");
}

/** agent id -> its manager's id, for the agents whose manager is in the company. */
export function bosses(agents: Agent[]): Map<string, string> {
  const ids = new Set(agents.map((a) => a.id));
  return new Map(agents.filter((a) => a.reportsTo && ids.has(a.reportsTo)).map((a) => [a.id, a.reportsTo as string]));
}

/** True when `boss` is `id` or reports (directly or not) to `id`: making `id` report to `boss` would loop. */
export function wouldLoop(agents: Agent[], id: string, boss: string): boolean {
  const up = bosses(agents);
  let cur: string | undefined = boss;
  const seen = new Set<string>();
  while (cur && !seen.has(cur)) {
    if (cur === id) return true;
    seen.add(cur);
    cur = up.get(cur);
  }
  return false;
}

export function select(sel: Sel): void {
  org.update((s) => (s.sel?.kind === sel?.kind && s.sel?.id === sel?.id ? {} : { sel }));
}

/** One line for the status bar: the company, its agents and the open issues. */
export function statusLine(s: OrgState): string {
  if (!s.status) return "";
  if (!s.status.reachable) return s.status.installed ? "Paperclip is installed but not running" : "Paperclip is not installed";
  if (!s.company) return "no company linked";
  const open = s.issues.filter((i) => ["todo", "in_progress", "blocked", "in_review"].includes(String(i.status))).length;
  return `company: ${s.company.name} · ${s.agents.length} agents · ${open} open issues · Org mode ${s.status.enabled ? "on" : "off"}`;
}
