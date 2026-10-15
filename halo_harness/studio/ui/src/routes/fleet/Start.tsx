// The Fleet section when only this harness is here and nothing runs on it:
// one Start view instead of an empty map -- what Fleet is in five lines,
// "start a session in a terminal, it appears here", the pair code and QR to
// invite another harness, the share / control settings as radio rows, the
// hubs and members it knows, and "open the workspace anyway". FleetView
// decides between it and the panels (map + agent) the moment a session
// registers or a member joins.
import { useEffect } from "react";
import { Surface } from "../../lib/ui";
import { Workspace } from "../../lib/workspace/Workspace";
import type { PanelSpec } from "../../lib/workspace/types";
import { FleetSettings, PairCard } from "./Pair";
import { setView, showsStart, useFleet } from "./store";
import { startFleet } from "./sync";

const WHAT: string[] = [
  "Every Halo session on this machine shows up here by itself, its agents as a live tree.",
  "Other harnesses join with a six-word pair code; each one says what it shares and what you may do there.",
  "Click an agent: what it thinks, the tools it runs and what it writes, as it happens.",
  "Steer any agent, not only the main one: a nudge it reads before its next step, or a new task.",
  "Pause, resume or stop one agent, or shut a session down; every command names who sent it.",
];

export function StartView() {
  const error = useFleet((s) => s.error);
  return (
    <div className="fl-start fs-start" data-testid="fleet-start">
      <div className="fl-start-inner">
        <header className="fl-start-head">
          <div className="glance-kicker mono">FLEET · EVERY HARNESS, EVERY AGENT</div>
          <h1 className="fl-start-title">Your fleet</h1>
          <p className="muted">Nothing runs here yet. This is what you will see, and how to bring another machine in.</p>
        </header>
        <div className="fl-start-grid">
          <Surface className="fl-start-form" motion="idle">
            <ol className="fl-explain">
              {WHAT.map((line, i) => (
                <li key={line}>
                  <span className="fl-explain-n mono">{i + 1}</span>
                  <span>{line}</span>
                </li>
              ))}
            </ol>
            <div className="fs-try">
              <b>Start a session in a terminal, it appears here.</b>
              <span className="muted">
                Run <code>halo</code> (or <code>halo -p "..."</code>, an Orchestra run, a flow) anywhere on this machine: its card and its agents show on the map within a second.
                <code>halo --private</code> keeps one out.
              </span>
            </div>
            <PairCard />
          </Surface>
          <aside className="fl-start-side">
            <FleetSettings />
            {error && <p className="og-problems">Studio could not read the fleet: {error}</p>}
            <button className="og-link mono" onClick={() => setView("workspace")} data-testid="fleet-open-workspace">
              open the workspace anyway
            </button>
          </aside>
        </div>
      </div>
    </div>
  );
}

/** The Fleet section: the Start view while nothing is here, then the panels. */
export function FleetView({ section, specs }: { section: string; specs: PanelSpec[] }) {
  useEffect(() => startFleet(), []);
  const loaded = useFleet((s) => s.loaded);
  const start = useFleet(showsStart);
  if (!loaded)
    return (
      <div className="fl-start">
        <div className="og-wait mono muted">reading the fleet...</div>
      </div>
    );
  if (start) return <StartView />;
  return <Workspace section={section} specs={specs} />;
}
