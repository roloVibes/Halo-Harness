// The shapes the Org section reads: Studio's `GET pc/status` and the
// Paperclip rows the proxy (`/api/pc/<path>`) passes through (agents,
// issues, goals, projects, the company), as observed on a real instance and
// in tests/helpers/fake_paperclip.py. Every field past the id is optional:
// Paperclip versions differ.

export type PcStatus = {
  enabled: boolean;
  explainer?: string;
  installed: boolean;
  base_url: string;
  token: boolean;
  company_id: string;
  reachable: boolean;
  version?: string;
  mode?: string;
  companies: { id: string; name: string; status?: string }[];
  node: boolean;
  install?: { running: boolean; code: number | null };
  error?: string;
};

export type Company = { id: string; name: string; status?: string; issuePrefix?: string; budgetMonthlyCents?: number; spentMonthlyCents?: number };

export type Agent = {
  id: string;
  name: string;
  role?: string;
  title?: string | null;
  status?: string;
  reportsTo?: string | null;
  adapterType?: string;
  adapterConfig?: { command?: string; args?: string[]; cwd?: string };
  metadata?: { halo_agent?: string; halo_lineup?: string; team?: string } | null;
  budgetMonthlyCents?: number;
  spentMonthlyCents?: number;
  errorReason?: string | null;
};

export type Issue = {
  id: string;
  identifier?: string;
  title: string;
  status?: string;
  assigneeAgentId?: string | null;
  description?: string;
  priority?: number;
  createdAt?: string;
};

export type Goal = { id: string; title?: string; name?: string; status?: string; level?: string; description?: string };
export type Project = { id: string; name: string; status?: string; description?: string };

export type Pos = { x: number; y: number };

/** What the Inspector shows. */
export type Sel = { kind: "agent" | "issue" | "goal" | "project"; id: string } | null;
export type WorkTab = "issues" | "goals" | "projects";

export type OrgDialog =
  | { kind: "reparent"; agent: string; boss: string | null; back: Pos | null }
  | { kind: "terminate"; agent: string }
  | { kind: "link" }
  | { kind: "sync" }
  | { kind: "pull" }
  | null;

export const ROLES = ["ceo", "cto", "cmo", "cfo", "security", "engineer", "designer", "pm", "qa", "devops", "researcher", "general"];
export const ISSUE_STATES = ["backlog", "todo", "in_progress", "in_review", "blocked", "done", "cancelled"];
export const OPEN_STATES = ["todo", "in_progress", "blocked", "in_review"];
