// org-work (3.0.7.0 R3): the company's issues, goals and projects from the
// proxied Paperclip routes, one tab each. Click a row: the Inspector shows
// it. With an agent selected on the canvas, "only <agent>" narrows the
// issues to the ones assigned to it. Under the issues: a new issue, assigned
// or not (Paperclip wakes an assigned agent at once).
import { memo, useState } from "react";
import type { MotionState } from "../../lib/motion";
import { Button, Empty, Tabs } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { createIssue } from "./actions";
import { openInspector } from "./Canvas";
import { agentById, org, select, useOrg } from "./store";
import { OPEN_STATES, type Goal, type Issue, type Project, type WorkTab } from "./types";

const IssueRow = memo(function IssueRow({ i, who, on }: { i: Issue; who: string; on: boolean }) {
  return (
    <button className="ow-row" data-testid="org-issue" aria-pressed={on} onClick={() => select({ kind: "issue", id: i.id })} onDoubleClick={openInspector}>
      <span className="ow-id mono">{i.identifier || "-"}</span>
      <span className="ow-title">{i.title}</span>
      <span className="ow-state mono" data-state={i.status}>{String(i.status || "").replace("_", " ")}</span>
      <span className="ow-who muted">{who}</span>
    </button>
  );
});

function NewIssue() {
  const agents = useOrg((s) => s.agents);
  const selAgent = useOrg((s) => (s.sel?.kind === "agent" ? s.sel.id : ""));
  const busy = useOrg((s) => s.busy === "new-issue");
  const [title, setTitle] = useState("");
  const [who, setWho] = useState("");
  const assignee = who === "-" ? "" : who || selAgent;
  const go = async () => {
    if (await createIssue(title, assignee)) setTitle("");
  };
  return (
    <div className="ow-new">
      <div className="rail-label mono">NEW ISSUE</div>
      <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="What should be done" aria-label="Issue title"
             onKeyDown={(e) => e.key === "Enter" && void go()} data-testid="org-new-issue" />
      <div className="ow-new-row">
        <select className="input" value={assignee || "-"} onChange={(e) => setWho(e.target.value)} aria-label="Assign to">
          <option value="-">(unassigned)</option>
          {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <Button size="sm" variant="primary" disabled={!title.trim() || busy} onClick={() => void go()}>Create</Button>
      </div>
    </div>
  );
}

function Issues() {
  const issues = useOrg((s) => s.issues);
  const agents = useOrg((s) => s.agents);
  const sel = useOrg((s) => s.sel);
  const mine = useOrg((s) => s.mine);
  const agent = sel?.kind === "agent" ? agents.find((a) => a.id === sel.id) : undefined;
  const rows = agent && mine ? issues.filter((i) => i.assigneeAgentId === agent.id) : issues;
  const name = (id?: string | null) => agentById(org.get(), id)?.name || "";
  return (
    <>
      {agent && (
        <label className="check ow-mine">
          <input type="checkbox" checked={mine} onChange={(e) => org.update(() => ({ mine: e.target.checked }))} /> only {agent.name}'s issues
        </label>
      )}
      {rows.length ? (
        <div className="ow-list">{rows.slice(0, 200).map((i) => <IssueRow key={i.id} i={i} who={name(i.assigneeAgentId)} on={sel?.kind === "issue" && sel.id === i.id} />)}</div>
      ) : (
        <Empty title={agent && mine ? `No issue is assigned to ${agent.name}` : "No issues yet"} body="Make one below, or let the agents open their own." />
      )}
      <NewIssue />
    </>
  );
}

function Plain<T extends Goal | Project>({ rows, kind }: { rows: T[]; kind: "goal" | "project" }) {
  const sel = useOrg((s) => s.sel);
  if (!rows.length) return <Empty title={`No ${kind}s yet`} body={`Add ${kind}s in Paperclip; they show here within a few seconds.`} />;
  return (
    <div className="ow-list">
      {rows.map((r) => (
        <button key={r.id} className="ow-row" data-testid={"org-" + kind} aria-pressed={sel?.kind === kind && sel.id === r.id}
                onClick={() => select({ kind, id: r.id })} onDoubleClick={openInspector}>
          <span className="ow-title">{"title" in r && r.title ? r.title : (r as Project).name || (r as Goal).name}</span>
          <span className="ow-state mono" data-state={r.status}>{String(r.status || "").replace("_", " ")}</span>
        </button>
      ))}
    </div>
  );
}

export function WorkDetail() {
  const tab = useOrg((s) => s.tab);
  const issues = useOrg((s) => s.issues.length);
  const goals = useOrg((s) => s.goals);
  const projects = useOrg((s) => s.projects);
  const items = [
    { id: "issues", label: `Issues ${issues}`, testid: "org-tab-issues" },
    { id: "goals", label: `Goals ${goals.length}`, testid: "org-tab-goals" },
    { id: "projects", label: `Projects ${projects.length}`, testid: "org-tab-projects" },
  ];
  return (
    <div className="ow">
      <Tabs items={items} value={tab} onChange={(t) => org.update(() => ({ tab: t as WorkTab }))} label="Work" />
      <div className="ow-body">
        {tab === "issues" ? <Issues /> : tab === "goals" ? <Plain rows={goals} kind="goal" /> : <Plain rows={projects} kind="project" />}
      </div>
    </div>
  );
}

export function WorkGlance() {
  const open = useOrg((s) => s.issues.filter((i) => OPEN_STATES.includes(String(i.status))).length);
  const blocked = useOrg((s) => s.issues.filter((i) => i.status === "blocked").length);
  const goals = useOrg((s) => s.goals.length);
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={open} label="open issues" tone={open ? "accent" : undefined} />
        <Metric value={blocked} label="blocked" tone={blocked ? "warn" : undefined} />
        <Metric value={goals} label="goals" />
      </div>
    </div>
  );
}

export function useWorkMotion(): MotionState {
  const blocked = useOrg((s) => s.issues.some((i) => i.status === "blocked"));
  const moving = useOrg((s) => s.issues.some((i) => i.status === "in_progress"));
  return blocked ? "waiting" : moving ? "working" : "idle";
}
