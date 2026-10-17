// What the Org panels do (3.0.7.0 R3): the Org mode switch, the Paperclip
// install (and its log), link a company, sync a lineup into it, pull its
// reporting lines back, an agent's fields and actions (`agents/<id>/<action>`:
// wakeup, pause, resume, terminate), an issue's status and assignee, a new
// issue, and a new reporting line from the canvas. Each one says how it went
// in a toast and polls again, so the panels show the result.
import { api, ApiError, call } from "../../lib/api";
import { toast } from "../../lib/store";
import { agentById, closeDialog, linkedId, org } from "./store";
import { poll } from "./sync";
import type { Agent, Issue } from "./types";

const msg = (e: unknown) => (e instanceof ApiError ? e.problems[0] || e.message : String(e));

async function run<T>(busy: string, fn: () => Promise<T>, done?: (r: T) => string): Promise<T | null> {
  org.update(() => ({ busy }));
  try {
    const r = await fn();
    if (done) toast(done(r), "done");
    return r;
  } catch (e) {
    toast(msg(e), "error", 5000);
    return null;
  } finally {
    org.update(() => ({ busy: "" }));
    void poll();
  }
}

export async function setOrgMode(on: boolean): Promise<void> {
  const r = await run("mode", () => api.post<{ enabled: boolean; agents?: string[]; note?: string }>("pc/mode", { enabled: on }), (r) =>
    r.enabled ? `Org mode on${r.agents?.length ? ": resumed " + r.agents.join(", ") : ""}` : `Org mode off${r.agents?.length ? ": paused " + r.agents.join(", ") : ""}`);
  if (r?.note) toast(r.note, "info", 5000);
}

let installTimer = 0;
async function tickInstall(): Promise<void> {
  try {
    const r = await api.get<{ running: boolean; code: number | null; log: string[] }>("pc/install");
    org.update(() => ({ installLog: r.log || [], installing: r.running }));
    if (r.running) installTimer = window.setTimeout(() => void tickInstall(), 1500);
    else {
      toast(r.code === 0 ? "Paperclip is up" : `The install ended with code ${r.code}`, r.code === 0 ? "done" : "error", 5000);
      void poll();
    }
  } catch (e) {
    org.update(() => ({ installing: false }));
    toast(msg(e), "error");
  }
}

export async function installPaperclip(): Promise<void> {
  window.clearTimeout(installTimer);
  const r = await run("install", () => api.post("pc/install"));
  if (r !== null) {
    org.update(() => ({ installing: true, installLog: ["starting the install..."] }));
    void tickInstall();
  }
}

export async function linkCompany(company_id: string): Promise<void> {
  const r = await run("link", () => api.post("pc/link", { company_id }), () => "Studio shows that company now");
  if (r !== null) closeDialog();
}

export async function syncLineup(lineup: string, newName = ""): Promise<void> {
  const company_id = linkedId(org.get());
  const body = newName ? { lineup, new: newName } : { lineup, company_id };
  const r = await run("sync", () => api.post<{ company_id: string; agents: number }>("pc/sync", body), (r) => `${r.agents} agent(s) synced from ${lineup}`);
  if (r && newName) await api.post("pc/link", { company_id: r.company_id }).catch(() => null);
  if (r) closeDialog();
}

export async function pullLines(lineup: string): Promise<void> {
  const company_id = linkedId(org.get());
  const r = await run("pull", () => api.post("pc/pull", { lineup, company_id }), () => `${lineup}: the reporting lines are in its org section`);
  if (r) closeDialog();
}

export async function patchAgent(a: Agent, patch: Partial<Agent>): Promise<void> {
  if (!Object.keys(patch).length) return;
  await run("agent", () => call("PATCH", `pc/agents/${a.id}`, patch), () => `${a.name} saved`);
}

export const ACTIONS = { wakeup: "Wake", pause: "Pause", resume: "Resume", terminate: "Terminate" } as const;
export type AgentAction = keyof typeof ACTIONS;

export async function agentAction(a: Agent, action: AgentAction): Promise<void> {
  await run(action, () => api.post<{ status?: string }>(`pc/agents/${a.id}/${action}`, {}), (r) =>
    `${a.name}: ${ACTIONS[action].toLowerCase()}${r && r.status ? " (" + r.status + ")" : ""}`);
  if (action === "terminate") closeDialog();
}

export async function patchIssue(i: Issue, patch: Partial<Issue>): Promise<void> {
  await run("issue", () => call("PATCH", `pc/issues/${i.id}`, patch), () => `${i.identifier || i.title} updated`);
}

export async function createIssue(title: string, assignee: string, description = ""): Promise<boolean> {
  const cid = linkedId(org.get());
  if (!cid || !title.trim()) return false;
  const r = await run("new-issue", () =>
    api.post<Issue>(`pc/companies/${cid}/issues`, { title: title.trim(), description, status: "todo", ...(assignee ? { assigneeAgentId: assignee } : {}) }),
    (r) => `${r.identifier || "Issue"} created${assignee ? ": Paperclip wakes the agent" : ""}`);
  return r !== null;
}

/** The canvas asked first (the reparent dialog): `agent` reports to `boss` (null: to no one, Leadership). */
export async function reparent(agent: string, boss: string | null): Promise<void> {
  const s = org.get();
  const a = agentById(s, agent);
  if (!a) return;
  const who = boss ? agentById(s, boss)?.name || boss : "no one";
  const r = await run("reparent", () => call("PATCH", `pc/agents/${a.id}`, { reportsTo: boss }), () => `${a.name} now reports to ${who}`);
  if (r !== null) closeDialog();
}
