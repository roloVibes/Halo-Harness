// The Org dialogs (3.0.7.0 R3, one at a time: store `dialog`): a new
// reporting line from a canvas drop (Cancel puts the card back where it
// was), Terminate an agent, Link a company, Sync a lineup into the company
// (or into a new one) and Pull its reporting lines back into a lineup.
import { useState } from "react";
import { Button, Dialog } from "../../lib/ui";
import { agentAction, linkCompany, pullLines, reparent, syncLineup } from "./actions";
import { agentById, closeDialog, linkedId, org, useOrg, wouldLoop } from "./store";
import { movePositions } from "./sync";
import type { OrgDialog } from "./types";

function Reparent({ d }: { d: Extract<OrgDialog, { kind: "reparent" }> }) {
  const a = useOrg((s) => agentById(s, d.agent));
  const boss = useOrg((s) => (d.boss ? agentById(s, d.boss) : undefined));
  const loops = useOrg((s) => (d.boss ? wouldLoop(s.agents, d.agent, d.boss) : false));
  const busy = useOrg((s) => s.busy === "reparent");
  const cancel = () => {
    if (d.back) movePositions({ [d.agent]: d.back });
    closeDialog();
  };
  const name = boss ? boss.name : "no one (Leadership)";
  return (
    <Dialog open onClose={cancel} title={`${a?.name || "This agent"} reports to ${name}?`} kicker="ORG · REPORTING LINE" testid="org-reparent"
            footer={<><Button onClick={cancel}>Cancel</Button><Button variant="primary" disabled={loops || busy} onClick={() => void reparent(d.agent, d.boss)} data-testid="org-reparent-yes">Change it</Button></>}>
      {loops ? (
        <p className="og-problems">{boss?.name} reports to {a?.name} already (directly or through a manager): pick a card outside its team.</p>
      ) : (
        <p>Paperclip changes {a?.name}'s manager (PATCH the agent's reportsTo); the card moves into that box on the next read.</p>
      )}
    </Dialog>
  );
}

function Terminate({ d }: { d: Extract<OrgDialog, { kind: "terminate" }> }) {
  const a = useOrg((s) => agentById(s, d.agent));
  if (!a) return null;
  return (
    <Dialog open onClose={closeDialog} title={`Terminate ${a.name}?`} kicker="ORG · AGENT" testid="org-terminate"
            footer={<><Button onClick={closeDialog}>Cancel</Button><Button variant="danger" onClick={() => void agentAction(a, "terminate")} data-testid="org-terminate-yes">Terminate</Button></>}>
      <p>Paperclip stops {a.name} for good (POST agents/{a.id.slice(0, 8)}.../terminate); its issues stay.</p>
    </Dialog>
  );
}

function Link() {
  const st = useOrg((s) => s.status);
  const [cid, setCid] = useState(st?.company_id || st?.companies[0]?.id || "");
  const busy = useOrg((s) => s.busy === "link");
  return (
    <Dialog open onClose={closeDialog} title="Link a company" kicker="ORG · PAPERCLIP" testid="org-link-dialog"
            footer={<><Button onClick={closeDialog}>Cancel</Button><Button variant="primary" disabled={!cid || busy} onClick={() => void linkCompany(cid)} data-testid="org-link-go">Link it</Button></>}>
      <p className="muted">Studio shows this company, and halo paperclip uses it. Nothing in Paperclip changes.</p>
      {st?.companies.length ? (
        <div className="ow-list" role="radiogroup" aria-label="Companies">
          {st.companies.map((c) => (
            <label key={c.id} className="check od-pick">
              <input type="radio" name="org-company" checked={cid === c.id} onChange={() => setCid(c.id)} /> {c.name} <span className="mono muted">{c.status || ""}</span>
            </label>
          ))}
        </div>
      ) : (
        <p>Paperclip has no company yet: Sync a lineup into a new one (the Start view, or Org: sync).</p>
      )}
    </Dialog>
  );
}

function LineupPick({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const lineups = useOrg((s) => s.lineups);
  if (!lineups.length) return <p className="muted">No lineup yet: make one in Roles (Alt+2).</p>;
  return (
    <label className="fd-field">
      <span className="rail-label mono">LINEUP</span>
      <select className="input" value={value} onChange={(e) => onChange(e.target.value)} data-testid="org-lineup">
        {lineups.map((n) => <option key={n}>{n}</option>)}
      </select>
    </label>
  );
}

function Sync() {
  const lineups = useOrg((s) => s.lineups);
  const cid = useOrg(linkedId);
  const company = useOrg((s) => s.company);
  const [lineup, setLineup] = useState(lineups[0] || "");
  const [fresh, setFresh] = useState(!cid);
  const [name, setName] = useState("");
  const busy = useOrg((s) => s.busy === "sync");
  const pick = lineup || lineups[0] || "";
  const ok = !!pick && (!fresh || !!name.trim());
  return (
    <Dialog open onClose={closeDialog} title={fresh ? "Sync a lineup into a new company" : `Sync a lineup into ${company?.name || "the company"}`} kicker="ORG · SYNC" testid="org-sync-dialog"
            footer={<><Button onClick={closeDialog}>Cancel</Button><Button variant="primary" disabled={!ok || busy} onClick={() => void syncLineup(pick, fresh ? name.trim() : "")} data-testid="org-sync-go">Sync</Button></>}>
      <p className="muted">One Paperclip agent per assignment of the lineup, run through halo paperclip-run; the reporting lines come from its org section (or everyone reports to main). Agents already there are updated, nothing is deleted.</p>
      <LineupPick value={pick} onChange={setLineup} />
      {cid && (
        <label className="check od-pick"><input type="checkbox" checked={fresh} onChange={(e) => setFresh(e.target.checked)} /> into a new company instead</label>
      )}
      {fresh && (
        <label className="fd-field">
          <span className="rail-label mono">NEW COMPANY NAME</span>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Halo Harness" data-testid="org-sync-name" />
        </label>
      )}
    </Dialog>
  );
}

function Pull() {
  const lineups = useOrg((s) => s.lineups);
  const company = useOrg((s) => s.company);
  const [lineup, setLineup] = useState(lineups[0] || "");
  const busy = useOrg((s) => s.busy === "pull");
  const pick = lineup || lineups[0] || "";
  return (
    <Dialog open onClose={closeDialog} title={`Pull ${company?.name || "the company"}'s reporting lines`} kicker="ORG · PULL" testid="org-pull-dialog"
            footer={<><Button onClick={closeDialog}>Cancel</Button><Button variant="primary" disabled={!pick || busy} onClick={() => void pullLines(pick)} data-testid="org-pull-go">Pull</Button></>}>
      <p className="muted">Writes who reports to whom in Paperclip into the lineup's org.positions (your scope); the rest of the lineup stays as it is.</p>
      <LineupPick value={pick} onChange={setLineup} />
    </Dialog>
  );
}

export function OrgDialogs() {
  const d = useOrg((s) => s.dialog);
  if (!d) return null;
  if (d.kind === "reparent") return <Reparent d={d} />;
  if (d.kind === "terminate") return <Terminate d={d} />;
  if (d.kind === "link") return <Link />;
  if (d.kind === "sync") return <Sync />;
  return <Pull />;
}

/** Open a dialog from the palette once the lineups are known. */
export function askOrg(kind: "link" | "sync" | "pull"): void {
  org.update(() => ({ dialog: { kind } }));
}
