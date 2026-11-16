// The Session section before this harness has a live session (3.1.4.0 R2):
// three lines, "start a session in a terminal (halo), it appears here the
// moment it registers" and "open the workspace anyway", built from Fleet's
// Start pieces. SessionView switches to the five panels the moment a session
// of this harness registers (and back when the last one ends). 3.3.11.0 R2: "New session" starts one with no
// terminal at all (NewSession.tsx: the model, the folder; Session opens on it with the Prompt focused).
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { Surface } from "../../lib/ui";
import { startLines } from "../crew/map/truth";
import { Workspace } from "../../lib/workspace/Workspace";
import type { PanelSpec } from "../../lib/workspace/types";
import { Explain, OpenAnyway, TryIt } from "../shared/StartBits";
import { NewSession } from "./NewSession";
import { useCatalog } from "../shared/catalog";
import { useFleet } from "../fleet/store";
import { knownNext, lastBuild } from "./pick";
import { setSessionView, startSession, useSessionStart } from "./store";
import { useSupervise, watchSupervise } from "./supervise";

const WHAT: string[] = [
  "Your sessions on this machine, live: a card per session, its agents as a tree under it, the one at work lit.",
  "Click an agent: what it thinks, the tools it runs and what it writes, as it happens; steer, pause or stop it.",
  "The timeline and the log, what waits on you and what it costs, for the session you chose.",
];

/** R4: {B} as this page last heard it (a session's row, a build); else the one read of the maps list, after the first
 *  draw (R28: nothing is fetched before it). Undefined until known: the sentence's room is held, nothing moves. */
function useNext(): string | null | undefined {
  const heard = knownNext();
  const [read, setRead] = useState<string | null | undefined>(undefined);
  useEffect(() => {
    if (!heard) void api.get<{ next?: string | null }>("crew/maps").then((d) => setRead(d.next || null), () => setRead(null));
  }, [heard]);
  return heard ? heard.b : read;
}

/** R4 the Start view's words: "No session is open here. New sessions will run on {B}." and, when this page heard a build
 *  from a session that has since ended, "Your last session built the map {X} at {t}. ..." + [New session], which takes
 *  him to the New session form below (R5: the form starts it). */
function StartSaid() {
  const b = useNext();
  const rows = useFleet((s) => s.harnesses);
  void rows; // a fleet change re-reads the last build
  const lines = b === undefined ? [] : startLines(b, lastBuild([]));
  const focus = () => {
    const el = document.querySelector<HTMLElement>("[data-testid=session-start] [data-testid=session-new-cwd]");
    el?.scrollIntoView({ block: "nearest" });
    el?.focus();
  };
  return (
    <div className="ss-start-said" data-testid="session-start-said">
      {lines.map((l, i) => (
        <p key={i} className="muted" data-testid={i ? "session-start-built" : "session-start-map"}>
          {l.text}
          {l.act === "new-session" && <>{" "}<button type="button" className="mp-link" onClick={focus} data-testid="session-start-new">{l.label}</button></>}
        </p>
      ))}
    </div>
  );
}

export function SessionStart() {
  const line = useSupervise((s) => (s.running ? s.line : ""));
  return (
    <div className="fl-start ss-start" data-testid="session-start">
      <div className="fl-start-inner">
        <header className="fl-start-head">
          <div className="glance-kicker mono">SESSION · THIS SESSION, LIVE</div>
          <h1 className="fl-start-title">Your session</h1>
          <StartSaid />
          {line ? <p className="ss-supervise mono" data-testid="session-supervise-line">Supervisor: {line}</p> : null}
        </header>
        <Surface className="fl-start-form ss-start-form" motion="idle">
          <Explain lines={WHAT} />
          <NewSession />
          <TryIt title="Or start a session in a terminal (halo), it appears here the moment it registers.">
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
  useEffect(() => {
    watchSupervise(true);
    return () => watchSupervise(false);
  }, []);
  const loaded = useFleet((s) => s.loaded);
  const start = useSessionStart();
  // 3.6.0.0 R5c: the Start view is drawn whole -- New session's MODEL lines with it -- so the catalog landing never
  // moves New session's Start or Open the workspace anyway (16 px down) under a click
  const catalog = useCatalog().loaded;
  if (!loaded || (start && !catalog))
    return (
      <div className="fl-start">
        <div className="og-wait mono muted">reading this session...</div>
      </div>
    );
  if (start) return <SessionStart />;
  return <Workspace section={section} specs={specs} />;
}
