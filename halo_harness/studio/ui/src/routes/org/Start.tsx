// The Org section before there is a company to show (3.0.7.0 R3): one Start
// view instead of four empty panels -- what Org mode is, the steps, where
// Paperclip stands (installed, running, linked) and the two buttons: Install
// Paperclip and Link a company (or, with no company in Paperclip yet, make
// one from a lineup). OrgView switches to the panels the moment a company is
// linked, or with "open the panels anyway".
import { useEffect } from "react";
import { Button, Surface } from "../../lib/ui";
import { Workspace } from "../../lib/workspace/Workspace";
import type { PanelSpec } from "../../lib/workspace/types";
import { SECTION_HELP } from "../sectionHelp";
import { installPaperclip } from "./actions";
import { InstallLog } from "./Company";
import { openDialog, setView, showsStart, useOrg } from "./store";
import { poll, startOrg } from "./sync";

function Where() {
  const st = useOrg((s) => s.status);
  const busy = useOrg((s) => s.busy);
  const error = useOrg((s) => s.error);
  if (!st) return <p className="og-problems">Studio could not ask about Paperclip: {error || "no answer"}</p>;
  const line = st.reachable
    ? st.companies.length ? `Paperclip ${st.version || ""} runs at ${st.base_url}: link one of its ${st.companies.length} compan${st.companies.length === 1 ? "y" : "ies"}.` : `Paperclip ${st.version || ""} runs at ${st.base_url} but has no company yet: make one from a lineup.`
    : st.installed ? `Paperclip is installed but not running at ${st.base_url}: run npx paperclipai run in a terminal, then Check again.`
      : "Paperclip is not installed here. Install runs npx paperclipai onboard --yes (Node 24 or newer, an embedded PostgreSQL under ~/.paperclip, the server on port 3100, loopback only).";
  return (
    <div className="os-where" data-reachable={st.reachable || undefined}>
      <p>{line}</p>
      <div className="os-buttons">
        <Button variant={st.reachable || st.installed ? "default" : "primary"} disabled={st.installed || st.reachable || !st.node || busy === "install"}
                onClick={() => void installPaperclip()} data-testid="org-install">
          Install Paperclip
        </Button>
        <Button variant={st.reachable ? "primary" : "default"} disabled={!st.reachable}
                onClick={() => openDialog({ kind: st.companies.length ? "link" : "sync" })} data-testid="org-link">
          {st.reachable && !st.companies.length ? "Make a company from a lineup" : "Link a company"}
        </Button>
        {!st.reachable && <Button variant="ghost" onClick={() => void poll()}>Check again</Button>}
      </div>
      {!st.node && !st.installed && !st.reachable && <p className="muted">Node.js was not found on PATH: install Node 24 or newer first.</p>}
      <InstallLog />
    </div>
  );
}

export function StartView() {
  const copy = SECTION_HELP.org;
  return (
    <div className="fl-start os-start" data-testid="org-start">
      <div className="fl-start-inner">
        <header className="fl-start-head">
          <div className="glance-kicker mono">ORG · YOUR COMPANY IN PAPERCLIP</div>
          <h1 className="fl-start-title">Your company of agents</h1>
          <p className="muted">{copy.what}</p>
        </header>
        <div className="fl-start-grid">
          <Surface className="fl-start-form" motion="idle">
            <Where />
          </Surface>
          <aside className="fl-start-side">
            <ol className="fl-explain">
              {copy.steps.map(([title, text], i) => (
                <li key={title}>
                  <span className="fl-explain-n mono">{i + 1}</span>
                  <span>
                    <b>{title}</b>
                    <span className="fl-explain-text">{text}</span>
                  </span>
                </li>
              ))}
            </ol>
            <button className="og-link mono" onClick={() => setView("workspace")} data-testid="org-open-workspace">
              open the panels anyway
            </button>
          </aside>
        </div>
      </div>
    </div>
  );
}

/** The Org section: the Start view while there is no company to show, then the panels. */
export function OrgView({ section, specs }: { section: string; specs: PanelSpec[] }) {
  useEffect(() => startOrg(), []);
  const loaded = useOrg((s) => s.loaded);
  const start = useOrg(showsStart);
  if (!loaded)
    return (
      <div className="fl-start">
        <div className="og-wait mono muted">asking Studio about Paperclip...</div>
      </div>
    );
  if (start) return <StartView />;
  return <Workspace section={section} specs={specs} />;
}
