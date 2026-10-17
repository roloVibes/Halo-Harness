// The palette's Org group (3.0.7.0 R3): sync a lineup into the company,
// pull its reporting lines back, link a company, Org mode on or off, and
// select any agent of the company by name (the Inspector opens on it).
import { goSection } from "../../lib/store";
import { setOrgMode } from "./actions";
import { openInspector } from "./Canvas";
import { askOrg } from "./Dialogs";
import { linkedId, org, select } from "./store";
import { poll, startOrg } from "./sync";

export type OrgCommand = { id: string; group: string; label: string; hint?: string; run: () => void };

function inOrg(fn: () => void): () => void {
  return () => {
    goSection("org");
    startOrg();
    window.setTimeout(fn, 60);
  };
}

export function orgCommands(): OrgCommand[] {
  const s = org.get();
  const g = "Org";
  const linked = !!linkedId(s);
  const name = s.company?.name || "the company";
  const out: OrgCommand[] = [
    { id: "org-sync", group: g, label: "Org: sync", hint: linked ? `a lineup into ${name}: one Paperclip agent per assignment` : "a lineup into a new Paperclip company", run: inOrg(() => askOrg("sync")) },
    { id: "org-pull", group: g, label: "Org: pull", hint: `${name}'s reporting lines into a lineup's org section`, run: inOrg(() => (linked ? askOrg("pull") : askOrg("link"))) },
    { id: "org-link", group: g, label: "Org: link company", hint: "the Paperclip company Studio shows", run: inOrg(() => askOrg("link")) },
    { id: "org-mode", group: g, label: s.status?.enabled ? "Org: turn Org mode off" : "Org: turn Org mode on", hint: "heartbeats on or off for the company's agents", run: () => void setOrgMode(!s.status?.enabled) },
    { id: "org-refresh", group: g, label: "Org: read Paperclip again", hint: "the panels refresh every 3 s while Org shows", run: inOrg(() => void poll()) },
  ];
  for (const a of s.agents.slice(0, 40))
    out.push({ id: "org-agent-" + a.id, group: g, label: `Org: agent ${a.name}`, hint: [a.role, a.title, a.status].filter(Boolean).join(" · "), run: inOrg(() => (select({ kind: "agent", id: a.id }), openInspector())) });
  return out;
}
