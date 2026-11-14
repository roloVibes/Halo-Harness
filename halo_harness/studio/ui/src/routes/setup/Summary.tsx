// Setup's last page (3.3.1.0 R1): the Summary, as in the terminal wizard
// (docs/WIZARD.md rule 10): one row per step with what it holds now and a
// **Change** jump to that step's page; then the last check's result with the
// Check block's **Run the ticked checks** (the ticks the Check page shows:
// doctor, catalog and hello until changed there) and a button to the Check
// page (3.4.0.0 B: the guided first run is the first-run pack's).
// 3.3.3.0 R1: at the foot, the primary "Done: start halo" (done.ts): the
// terminal that ran `halo init` starts halo, Studio opens Session. 3.3.15.0 R6:
// its note says whether an init terminal waits; with none, Studio opens one.
import { useEffect } from "react";
import { Button } from "../../lib/ui";
import { useLoadState, Waiting } from "./BlockFoot";
import { pressDone, useDoneBusy, useDoneError } from "./done";
import { lastCheckWord, runChecks, startCheck, ticked, useCheck } from "./checkStore";
import { goto, isDone, stepsOf, titleOf, usePage, valueOf, type StepId } from "./pages";
import { NONE, setup, useSetup } from "./store";

function Rows() {
  const page = usePage();
  // 3.3.11.0 R3: a pack's blocks are rows too (their title, "<pack>: done | skipped | waiting"); JSON, as the rail
  const joined = useSetup((s) =>
    JSON.stringify(
      stepsOf(s.data, page)
        .filter((st) => st !== "summary")
        .map((st) => [st, isDone(s.data, st) ? "done" : "todo", valueOf(s.data, st), titleOf(s.data, st)]),
    ),
  );
  const rows = JSON.parse(joined) as [StepId, string, string, string][];
  return (
    <div className="su-sum-rows" data-testid="setup-summary-rows">
      {rows.map(([st, state, value, title]) => (
        <div key={st} className="su-sum-row" data-testid="setup-summary-row" data-step={st} data-state={state}>
          <span className="su-sum-mark mono" aria-hidden="true">{state === "done" ? "✓" : "-"}</span>
          <span className="su-sum-title">{title}</span>
          <span className="su-sum-value mono" data-testid="setup-summary-value">{value}</span>
          <Button size="sm" variant="ghost" onClick={() => goto(st)} data-testid="setup-summary-change" data-step={st} title={`Open the ${title} page`}>
            Change
          </Button>
        </div>
      ))}
    </div>
  );
}

function CheckPart() {
  const last = useSetup((s) => s.data?.last_check);
  const rows = useSetup((s) => s.data?.checks || NONE);
  const running = useCheck((s) => s.running);
  const busy = useCheck((s) => s.busy);
  const names = useCheck((s) => rows.filter((c) => ticked(s, setup.get().data, c.key)).map((c) => c.key).join(", "));
  const word = running ? "running..." : lastCheckWord(last);
  return (
    <section className="su-sum-part" data-testid="setup-summary-check" aria-label="Check">
      <div className="su-sum-line">
        <span className="su-sum-title">Last check</span>
        <span className="su-sum-value mono" data-testid="setup-summary-last" data-word={word}>{word}</span>
      </div>
      <div className="su-foot-row">
        <Button variant="primary" size="sm" onClick={() => void runChecks()} disabled={busy || running || !names}
                title="the checks ticked on the Check page, in its order, as one job" data-testid="setup-summary-run">
          {busy ? "Starting..." : "Run the ticked checks"}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => goto("check")} data-testid="setup-summary-to-check">
          The Check page
        </Button>
        <span className="su-note muted">ticked: {names || "none"}</span>
      </div>
    </section>
  );
}

function DonePart() {
  const busy = useDoneBusy();
  const error = useDoneError();
  const waiting = useSetup((s) => !!s.data?.init_waiting); // 3.3.15.0 R6
  const note = waiting
    ? "halo starts in the terminal that ran halo init, paired with this Studio; Studio opens Session"
    : "no halo init is waiting: Studio opens a terminal running halo (or says to run halo yourself); Studio opens Session";
  return (
    <section className="su-sum-part su-sum-done" data-testid="setup-summary-done" aria-label="Done">
      <div className="su-foot-row">
        <Button variant="primary" onClick={() => void pressDone()} disabled={busy} data-testid="setup-done"
                title="Marks this box set up; the terminal that ran `halo init` starts halo; Studio opens Session">
          {busy ? "Marking..." : "Done: start halo"}
        </Button>
        <span className="su-note muted" data-testid="setup-done-note" data-waiting={waiting || undefined}>{note}</span>
      </div>
      {error && <pre className="su-lines mono" data-testid="setup-done-error">{error}</pre>}
    </section>
  );
}

export function SummaryDetail() {
  const { ready, error } = useLoadState();
  useEffect(() => void startCheck(), []);
  if (!ready) return <Waiting error={error} />;
  return (
    <div className="su-block" data-testid="setup-summary">
      <Rows />
      <CheckPart />
      <DonePart />
    </div>
  );
}
