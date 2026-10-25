// "Start here" (3.1.1.0 R1): the overlay a fresh home opens on (no lineup of
// your own, no run). It offers the ten-minute start or "Just look around"
// (remembered for the home); once the start runs, the same dialog is its
// panel: the seven steps with their state, the running step's command and
// its last lines, then the outcome and where to go next. lib/start.ts holds
// the state and talks to /api/start.
import { useEffect } from "react";
import { Button, Dialog } from "../lib/ui";
import { goSection, useStore } from "../lib/store";
import { closeStart, dismissStart, loadStart, runStart, start, stopStart, type StartFrame } from "../lib/start";
import { loadLists } from "../routes/roles/sync";

const MARK: Record<string, string> = { pending: "", ready: "..", running: ">>", done: "ok", failed: "!!", stopped: "--" };

function Step({ frame, current }: { frame: StartFrame; current: boolean }) {
  const lines = (frame.lines || []).slice(-10);
  return (
    <li className="sh-step" data-testid="start-step" data-state={frame.state} data-key={frame.key} aria-current={current || undefined}>
      <span className="sh-step-n mono">{MARK[frame.state] || frame.step}</span>
      <span className="sh-step-body">
        <b>{frame.title}</b>
        <span className="fl-explain-text">{frame.why}</span>
        {current && frame.command && <code className="sh-step-cmd">$ {frame.command}</code>}
        {current && lines.length > 0 && <pre className="sh-step-lines mono">{lines.join("\n")}</pre>}
      </span>
    </li>
  );
}

function Offer() {
  const busy = useStore(start, (s) => s.busy);
  const error = useStore(start, (s) => s.error);
  return (
    <div className="sh-offer">
      <p>
        This home has no lineup of its own and no run yet. The ten-minute start makes both: it copies a shipped lineup into one of yours, writes a small sample repo, gives one Orchestra goal to your agents, approves the lead's plan, runs the lanes, and ends on the report and the coach.
      </p>
      <p className="muted">It uses the model you configured. The same start in a terminal, one screen per step: <code>halo start</code>.</p>
      {error && <p className="og-problems" data-testid="start-here-error">{error}</p>}
      <div className="os-buttons">
        <Button variant="primary" onClick={() => void runStart()} disabled={busy} data-testid="start-here-run">
          Run the ten-minute start
        </Button>
        <Button variant="ghost" onClick={() => void dismissStart()} data-testid="start-here-dismiss">
          Just look around
        </Button>
      </div>
    </div>
  );
}

function Run() {
  const plan = useStore(start, (s) => s.plan);
  const steps = useStore(start, (s) => s.steps);
  const summary = useStore(start, (s) => s.summary);
  const frames = (plan.length ? plan : Object.values(steps)).map((p) => steps[p.key] || p).sort((a, b) => a.step - b.step);
  const current = [...frames].reverse().find((f) => f.state !== "pending")?.key;
  return (
    <div className="sh-run">
      <ol className="sh-steps">
        {frames.map((f) => (
          <Step key={f.key} frame={f} current={f.key === current} />
        ))}
      </ol>
      {summary && (
        <div className="sh-done" data-testid="start-here-done" data-ok={summary.ok ? "true" : "false"}>
          {summary.ok ? (
            <p>
              Done: lineup <b>{summary.lineup}</b>, run <code>{summary.run}</code> in <code>{summary.repo}</code>.
            </p>
          ) : (
            <p className="og-problems" data-testid="start-here-reason">
              Stopped at {summary.stopped_at || "the start"}: {summary.reason}
              {summary.error_log && (
                <>
                  <br />
                  the full error is in <code>{summary.error_log}</code>
                </>
              )}
            </p>
          )}
          <div className="os-buttons">
            {(["roles", "team", "fleet"] as const).map((s) => (
              <Button key={s} variant="ghost" onClick={() => (closeStart(), goSection(s))}>
                {s === "roles" ? "Roles: your lineup" : s === "team" ? "Team: a team file" : "Fleet: more machines"}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function StartHere() {
  const open = useStore(start, (s) => s.open);
  const view = useStore(start, (s) => s.view);
  const running = useStore(start, (s) => s.running && !s.summary);
  const finished = useStore(start, (s) => !!s.summary);
  useEffect(() => {
    void loadStart();
  }, []);
  useEffect(() => {
    if (finished) void loadLists().catch(() => undefined); // the start made a lineup of your own: Roles shows it
  }, [finished]);
  if (!open) return null;
  const footer = view === "run" && running ? (
    <>
      <span className="muted">Closing this keeps the start running; the palette brings it back.</span>
      <Button variant="danger" onClick={() => void stopStart()} data-testid="start-here-stop">
        Stop the start
      </Button>
    </>
  ) : undefined;
  return (
    <Dialog
      open
      onClose={view === "offer" ? () => void dismissStart() : closeStart}
      title={view === "offer" ? "Start here" : "The ten-minute start"}
      kicker="HALO · THE FIRST TEN MINUTES"
      className="start-here"
      testid="start-here"
      footer={footer}
    >
      {view === "offer" ? <Offer /> : <Run />}
    </Dialog>
  );
}
