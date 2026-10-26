// "Start here" (3.1.1.0 R1): the overlay a fresh home opens on (no lineup of
// your own, no run). It offers the guided first run or "Just look around"
// (remembered for the home); once the start runs, the same dialog is its
// panel: the seven steps with their state, the running step's command and
// its last lines, then the outcome and where to go next. lib/start.ts holds
// the state and talks to /api/start. 3.2.2.0 R2: the offer shows the card
// `halo start` opens on (what it does, the models, the cost, the time, what
// it writes) above its Run button. 3.3.0.0 R3: the first button is "Set up
// this box" (Setup opens, the overlay closes; the primary one while no
// provider is set up); "Just look around" stays. 3.3.1.0 R1: the offer never
// shows while the section is Setup (Setup's first page is what "Set up this
// box" opens); it shows on the other sections of a fresh home as before.
import { useEffect } from "react";
import { Button, Dialog } from "../lib/ui";
import { goSection, studio, useStore } from "../lib/store";
import { closeStart, dismissStart, loadStart, runStart, setUpThisBox, start, stopStart, type StartFrame } from "../lib/start";
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
  const card = useStore(start, (s) => s.card);
  const noProvider = useStore(start, (s) => s.noProvider);
  return (
    <div className="sh-offer">
      <p>
        This home has no lineup of its own and no run yet. The guided first run makes both: it copies a shipped lineup into one of yours, writes a small sample repo, gives one real Orchestra goal to your agents, approves the lead's plan, runs the lanes, and ends on the report and the coach.
      </p>
      {card.length > 0 && (
        <pre className="sh-card mono" data-testid="start-here-card">
          {card.join("\n")}
        </pre>
      )}
      <p className="muted">It runs on your models. The same run in a terminal, one screen per step: <code>halo start</code> (<code>halo start --explain</code> prints this card).</p>
      {error && <p className="og-problems" data-testid="start-here-error">{error}</p>}
      <div className="os-buttons">
        <Button variant={noProvider ? "primary" : "default"} onClick={setUpThisBox} data-testid="start-here-setup">
          Set up this box
        </Button>
        <Button variant={noProvider ? "default" : "primary"} onClick={() => void runStart()} disabled={busy} data-testid="start-here-run">
          Run the guided first run
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
  const onSetup = useStore(studio, (s) => s.section === "setup");
  useEffect(() => {
    void loadStart();
  }, []);
  useEffect(() => {
    if (finished) void loadLists().catch(() => undefined); // the start made a lineup of your own: Roles shows it
  }, [finished]);
  if (!open || (onSetup && view === "offer")) return null;
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
      title={view === "offer" ? "Start here" : "The guided first run"}
      kicker="HALO · THE GUIDED FIRST RUN"
      className="start-here"
      testid="start-here"
      footer={footer}
    >
      {view === "offer" ? <Offer /> : <Run />}
    </Dialog>
  );
}
