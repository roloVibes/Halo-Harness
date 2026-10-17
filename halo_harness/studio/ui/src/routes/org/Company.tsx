// org-company (3.0.7.0 R3): is Paperclip installed, is it running, which
// company Studio shows, and the Org mode switch; then what the classic page
// offered, each with its one line: Install, Link, Sync a lineup into the
// company, Pull its reporting lines back into the lineup, open Paperclip.
import type { ReactNode } from "react";
import type { MotionState } from "../../lib/motion";
import { Button } from "../../lib/ui";
import { installPaperclip, setOrgMode } from "./actions";
import { linkedId, openDialog, pcUrl, useOrg, usd } from "./store";

function Row({ label, ok, children }: { label: string; ok: boolean | null; children: ReactNode }) {
  return (
    <div className="oco-row" data-ok={ok === null ? undefined : String(ok)}>
      <span className="oco-dot" aria-hidden="true" />
      <span className="rail-label mono">{label}</span>
      <span className="oco-val">{children}</span>
    </div>
  );
}

function Action({ title, about, children }: { title: string; about: string; children: ReactNode }) {
  return (
    <div className="oco-action">
      <div className="oco-action-head">
        <b>{title}</b>
        {children}
      </div>
      <p className="muted">{about}</p>
    </div>
  );
}

export function InstallLog() {
  const log = useOrg((s) => s.installLog);
  const running = useOrg((s) => s.installing);
  if (!log.length) return null;
  return (
    <pre className="oco-log mono" data-running={running || undefined} data-testid="org-install-log">
      {log.slice(-40).join("\n")}
    </pre>
  );
}

export function CompanyDetail() {
  const st = useOrg((s) => s.status);
  const company = useOrg((s) => s.company);
  const cid = useOrg(linkedId);
  const busy = useOrg((s) => s.busy);
  const url = useOrg((s) => pcUrl(s));
  if (!st) return <div className="og-wait mono muted">asking Studio about Paperclip...</div>;
  return (
    <div className="oco">
      <div className="oco-rows">
        <Row label="INSTALLED" ok={st.installed || st.reachable}>{st.installed ? "yes, under ~/.paperclip" : st.reachable ? "elsewhere (linked by URL)" : "no"}</Row>
        <Row label="RUNNING" ok={st.reachable}>
          {st.reachable ? <>Paperclip {st.version} <span className="mono muted">{st.base_url}{st.mode ? " · " + st.mode : ""}</span></> : st.error || "not reachable"}
        </Row>
        <Row label="LINKED" ok={!!cid}>{company ? <>{company.name} <span className="mono muted">{company.issuePrefix || ""}</span></> : "no company"}</Row>
        <Row label="ORG MODE" ok={st.enabled}>
          {st.enabled ? "on: heartbeats run" : "off: nothing runs on a heartbeat"}
          <Button size="sm" variant={st.enabled ? "ghost" : "primary"} disabled={busy === "mode"} onClick={() => void setOrgMode(!st.enabled)} data-testid="org-mode-switch">
            Turn {st.enabled ? "off" : "on"}
          </Button>
        </Row>
        {company && (
          <Row label="BUDGET" ok={null}>
            <span className="mono">{usd(company.spentMonthlyCents)} / {usd(company.budgetMonthlyCents, 0)} this month</span>
          </Row>
        )}
      </div>
      {st.explainer && <p className="muted oco-explain">{st.explainer}</p>}
      {!st.reachable && !st.installed && (
        <Action title="Install Paperclip" about="Runs npx paperclipai onboard --yes: Node 24 or newer, an embedded PostgreSQL under ~/.paperclip, the server on port 3100, loopback only.">
          <Button size="sm" variant="primary" disabled={!st.node || busy === "install"} onClick={() => void installPaperclip()} data-testid="org-install">Install</Button>
        </Action>
      )}
      {!st.reachable && st.installed && <p className="muted">Paperclip is installed but not running: run <code>npx paperclipai run</code> in a terminal, then this panel fills in.</p>}
      <InstallLog />
      {st.reachable && (
        <Action title="Link a company" about="The company Studio (and halo paperclip) shows; pick another one any time.">
          <Button size="sm" disabled={!st.companies.length} onClick={() => openDialog({ kind: "link" })} data-testid="org-link">Link...</Button>
        </Action>
      )}
      {cid && (
        <>
          <Action title="Sync a lineup into it" about="One Paperclip agent per assignment, run through halo paperclip-run; nothing is deleted.">
            <Button size="sm" onClick={() => openDialog({ kind: "sync" })} data-testid="org-sync">Sync...</Button>
          </Action>
          <Action title="Pull the reporting lines" about="Writes who reports to whom here into a lineup's org.positions (your scope).">
            <Button size="sm" onClick={() => openDialog({ kind: "pull" })} data-testid="org-pull">Pull...</Button>
          </Action>
        </>
      )}
      {st.reachable && (
        <a className="og-link oco-open" href={url} target="_blank" rel="noopener noreferrer">open Paperclip in a new tab</a>
      )}
    </div>
  );
}

export function CompanyGlance() {
  const st = useOrg((s) => s.status);
  const company = useOrg((s) => s.company);
  return (
    <div className="glance">
      <div className="glance-kicker mono">{st?.reachable ? `PAPERCLIP ${st.version || ""}` : "PAPERCLIP"}</div>
      <div className="glance-text">{company ? company.name : st?.reachable ? "No company linked" : st?.installed ? "Installed, not running" : "Not installed"}</div>
      <div className="glance-hint mono">Org mode {st?.enabled ? "on" : "off"}</div>
    </div>
  );
}

export function useCompanyMotion(): MotionState {
  const st = useOrg((s) => s.status);
  const installing = useOrg((s) => s.installing);
  if (installing) return "working";
  if (!st) return "none";
  if (!st.reachable) return "waiting";
  return st.enabled ? "idle" : "none";
}
