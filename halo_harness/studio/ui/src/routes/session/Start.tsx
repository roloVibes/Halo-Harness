// The Session section before this harness has a live session (3.1.4.0 R2):
// three lines, "start a session in a terminal (halo), it appears here the
// moment it registers" and "open the workspace anyway", built from Fleet's
// Start pieces. SessionView switches to the five panels the moment a session
// of this harness registers (and back when the last one ends).
import { useEffect } from "react";
import { Surface } from "../../lib/ui";
import { Workspace } from "../../lib/workspace/Workspace";
import type { PanelSpec } from "../../lib/workspace/types";
import { Explain, OpenAnyway, TryIt } from "../fleet/Start";
import { useFleet } from "../fleet/store";
import { setSessionView, startSession, useSessionStart } from "./store";

const WHAT: string[] = [
  "Your sessions on this machine, live: a card per session, its agents as a tree under it, the one at work lit.",
  "Click an agent: what it thinks, the tools it runs and what it writes, as it happens; steer, pause or stop it.",
  "The timeline and the log, what waits on you and what it costs, for the session you chose.",
];

export function SessionStart() {
  return (
    <div className="fl-start ss-start" data-testid="session-start">
      <div className="fl-start-inner">
        <header className="fl-start-head">
          <div className="glance-kicker mono">SESSION · THIS SESSION, LIVE</div>
          <h1 className="fl-start-title">Your session</h1>
          <p className="muted">No session is live on this harness yet. This is what you will see.</p>
        </header>
        <Surface className="fl-start-form ss-start-form" motion="idle">
          <Explain lines={WHAT} />
          <TryIt title="Start a session in a terminal (halo), it appears here the moment it registers.">
            Run <code>halo</code> in any folder on this machine; <code>/studio</code> in it opens this view on that session. <code>halo --private</code> keeps one out.
          </TryIt>
          <OpenAnyway onOpen={() => setSessionView("workspace")} testid="session-open-workspace" />
        </Surface>
      </div>
    </div>
  );
}

/** The Session section: the Start view while this harness has no live session, then the five panels. */
export function SessionView({ section, specs }: { section: string; specs: PanelSpec[] }) {
  useEffect(() => startSession(), []);
  const loaded = useFleet((s) => s.loaded);
  const start = useSessionStart();
  if (!loaded)
    return (
      <div className="fl-start">
        <div className="og-wait mono muted">reading this session...</div>
      </div>
    );
  if (start) return <SessionStart />;
  return <Workspace section={section} specs={specs} />;
}
