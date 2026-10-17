// org-inspector (3.0.7.0 R3): what was clicked on the canvas or in the work
// lists. An agent: its title, role, manager and monthly budget (Save sends
// the changes to Paperclip), its adapter, and the actions Wake, Pause or
// Resume and Terminate (asks first), each answered with a toast. An issue:
// its status and assignee (changed in place), its description. A goal or a
// project: what Paperclip says about it. Every one links to its own page in
// Paperclip.
import { useEffect, useState, type ReactNode } from "react";
import { Button, Empty } from "../../lib/ui";
import { agentAction, patchAgent, patchIssue, type AgentAction } from "./actions";
import { agentById, openDialog, pcUrl, useOrg, usd } from "./store";
import { ISSUE_STATES, ROLES, type Agent, type Issue } from "./types";

function KV({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="oi-kv">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt className="rail-label mono">{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function AgentView({ a }: { a: Agent }) {
  const agents = useOrg((s) => s.agents);
  const busy = useOrg((s) => s.busy);
  const url = useOrg((s) => pcUrl(s, "agents", a.id));
  const [title, setTitle] = useState(a.title || "");
  const [role, setRole] = useState(a.role || "general");
  const [boss, setBoss] = useState(a.reportsTo || "");
  const [budget, setBudget] = useState(a.budgetMonthlyCents ? String(a.budgetMonthlyCents / 100) : "");
  useEffect(() => {
    setTitle(a.title || "");
    setRole(a.role || "general");
    setBoss(a.reportsTo || "");
    setBudget(a.budgetMonthlyCents ? String(a.budgetMonthlyCents / 100) : "");
  }, [a]);
  const patch: Partial<Agent> = {};
  if (title !== (a.title || "")) patch.title = title;
  if (role !== (a.role || "general")) patch.role = role;
  if (boss !== (a.reportsTo || "")) patch.reportsTo = boss || null;
  const cents = Math.round((parseFloat(budget) || 0) * 100);
  if (cents !== (a.budgetMonthlyCents || 0)) patch.budgetMonthlyCents = cents;
  const dirty = Object.keys(patch).length > 0;
  const act = (action: AgentAction) => void agentAction(a, action);
  const cfg = a.adapterConfig || {};
  return (
    <div className="oi" data-testid="org-inspector-agent">
      <header className="oi-head">
        <b className="oi-title">{a.name}</b>
        <span className="ow-state mono" data-state={a.status}>{a.status || "idle"}</span>
      </header>
      <label className="fd-field"><span className="rail-label mono">TITLE</span><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} /></label>
      <label className="fd-field">
        <span className="rail-label mono">ROLE</span>
        <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>{[...new Set([role, ...ROLES])].map((r) => <option key={r}>{r}</option>)}</select>
      </label>
      <label className="fd-field">
        <span className="rail-label mono">REPORTS TO</span>
        <select className="input" value={boss} onChange={(e) => setBoss(e.target.value)}>
          <option value="">(no one: Leadership)</option>
          {agents.filter((x) => x.id !== a.id).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
        </select>
      </label>
      <label className="fd-field">
        <span className="rail-label mono">MONTHLY BUDGET (USD) · SPENT {usd(a.spentMonthlyCents)}</span>
        <input className="input mono" type="number" min="0" step="1" value={budget} onChange={(e) => setBudget(e.target.value)} />
      </label>
      <div className="oi-actions">
        <Button size="sm" variant="primary" disabled={!dirty || busy === "agent"} onClick={() => void patchAgent(a, patch)} data-testid="org-agent-save">Save</Button>
        <Button size="sm" onClick={() => act("wakeup")} disabled={!!busy} data-testid="org-agent-wake">Wake</Button>
        <Button size="sm" onClick={() => act(a.status === "paused" ? "resume" : "pause")} disabled={!!busy}>{a.status === "paused" ? "Resume" : "Pause"}</Button>
        <Button size="sm" variant="danger" onClick={() => openDialog({ kind: "terminate", agent: a.id })} disabled={!!busy}>Terminate...</Button>
      </div>
      <KV rows={[
        ["ADAPTER", <span className="mono">{a.adapterType || "-"}</span>],
        ["COMMAND", <span className="mono">{[cfg.command, ...(cfg.args || [])].filter(Boolean).join(" ") || "-"}</span>],
        ["CWD", <span className="mono">{cfg.cwd || "-"}</span>],
        ["HALO BIO", a.metadata?.halo_agent || "-"],
        ["LINEUP", a.metadata?.halo_lineup || "-"],
      ]} />
      {a.errorReason && <p className="og-problems">{a.errorReason}</p>}
      <a className="og-link" href={url} target="_blank" rel="noopener noreferrer">open {a.name} in Paperclip</a>
    </div>
  );
}

function IssueView({ i }: { i: Issue }) {
  const agents = useOrg((s) => s.agents);
  const url = useOrg((s) => pcUrl(s, "issues", i.identifier || i.id));
  const who = useOrg((s) => agentById(s, i.assigneeAgentId)?.name);
  return (
    <div className="oi" data-testid="org-inspector-issue">
      <header className="oi-head">
        <span className="ow-id mono">{i.identifier}</span>
        <b className="oi-title">{i.title}</b>
      </header>
      <label className="fd-field">
        <span className="rail-label mono">STATUS</span>
        <select className="input" value={i.status || "todo"} onChange={(e) => void patchIssue(i, { status: e.target.value })}>
          {[...new Set([i.status || "todo", ...ISSUE_STATES])].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
        </select>
      </label>
      <label className="fd-field">
        <span className="rail-label mono">ASSIGNED TO</span>
        <select className="input" value={i.assigneeAgentId || ""} onChange={(e) => void patchIssue(i, { assigneeAgentId: e.target.value || null })}>
          <option value="">(unassigned)</option>
          {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </label>
      {i.description ? <p className="oi-desc">{i.description}</p> : <p className="muted">No description.</p>}
      <KV rows={[["ASSIGNEE", who || "-"], ["CREATED", <span className="mono">{i.createdAt || "-"}</span>]]} />
      <a className="og-link" href={url} target="_blank" rel="noopener noreferrer">open {i.identifier || "the issue"} in Paperclip</a>
    </div>
  );
}

export function InspectorDetail() {
  const sel = useOrg((s) => s.sel);
  const item = useOrg((s) =>
    !s.sel ? undefined : s.sel.kind === "agent" ? s.agents.find((x) => x.id === s.sel!.id) : s.sel.kind === "issue" ? s.issues.find((x) => x.id === s.sel!.id)
      : s.sel.kind === "goal" ? s.goals.find((x) => x.id === s.sel!.id) : s.projects.find((x) => x.id === s.sel!.id));
  const url = useOrg((s) => pcUrl(s));
  if (!sel || !item) return <Empty title="Nothing selected" body="Click a card on the canvas (double-click opens it here), or an issue, goal or project in the list." />;
  if (sel.kind === "agent") return <AgentView a={item as Agent} />;
  if (sel.kind === "issue") return <IssueView i={item as Issue} />;
  const r = item as { title?: string; name?: string; status?: string; level?: string; description?: string };
  return (
    <div className="oi" data-testid={"org-inspector-" + sel.kind}>
      <header className="oi-head">
        <span className="rail-label mono">{sel.kind.toUpperCase()}</span>
        <b className="oi-title">{r.title || r.name}</b>
      </header>
      {r.description && <p className="oi-desc">{r.description}</p>}
      <KV rows={[["STATUS", r.status || "-"], ...(r.level ? [["LEVEL", r.level] as [string, string]] : [])]} />
      <a className="og-link" href={url} target="_blank" rel="noopener noreferrer">open the company in Paperclip</a>
    </div>
  );
}

export function InspectorGlance() {
  const name = useOrg((s) => (s.sel?.kind === "agent" ? agentById(s, s.sel.id)?.name : s.sel ? s.sel.kind : ""));
  return (
    <div className="glance">
      <div className="glance-kicker mono">INSPECTOR</div>
      <div className="glance-text">{name || "Nothing selected"}</div>
    </div>
  );
}
