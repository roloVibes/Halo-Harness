// Setup's last page (3.3.1.0 R1): the Summary, as in the terminal wizard
// (docs/WIZARD.md rule 10): one row per step with what it holds now and a
// **Change** jump to that step's page; then the last check's result with the
// Check block's **Run the ticked checks** (the ticks the Check page shows:
// doctor, catalog and hello until changed there) and a button to the Check
// page; then the guided first run's card (what `halo start` does, the models
// it calls, the estimate, the time, what it writes) and its Run button.
import { useEffect } from "react";
import { runStart, start } from "../../lib/start";
import { useStore } from "../../lib/store";
import { Button } from "../../lib/ui";
import { useLoadState, Waiting } from "./BlockFoot";
import { lastCheckWord, runChecks, startCheck, ticked, useCheck } from "./checkStore";
import { goto, isDone, stepsOf, TITLES, usePage, valueOf, type StepId } from "./pages";
import { NONE, setup, useSetup } from "./store";

function Rows() {
  const page = usePage();
  const joined = useSetup((s) =>
    stepsOf(s.data, page)
      .filter((st) => st !== "summary")
      .map((st) => [st, isDone(s.data, st) ? "done" : "todo", valueOf(s.data, st)].join("~"))
      .join("|"),
  );
  const rows = joined.split("|").map((x) => x.split("~") as [StepId, string, string]);
  return (
    <div className="su-sum-rows" data-testid="setup-summary-rows">
      {rows.map(([st, state, value]) => (
        <div key={st} className="su-sum-row" data-testid="setup-summary-row" data-step={st} data-state={state}>
          <span className="su-sum-mark mono" aria-hidden="true">{state === "done" ? "✓" : "-"}</span>
          <span className="su-sum-title">{TITLES[st]}</span>
          <span className="su-sum-value mono" data-testid="setup-summary-value">{value}</span>
          <Button size="sm" variant="ghost" onClick={() => goto(st)} data-testid="setup-summary-change" data-step={st} title={`Open the ${TITLES[st]} page`}>
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

function StartPart() {
  const card = useSetup((s) => s.data?.card || NONE);
  const busy = useStore(start, (s) => s.busy || (s.running && !s.summary));
  return (
    <section className="su-sum-part" data-testid="setup-summary-start" aria-label="The guided first run">
      <div className="su-sum-title">The guided first run</div>
      {card.length > 0 && <pre className="su-check-card mono" data-testid="setup-summary-card">{card.join("\n")}</pre>}
      <div className="su-foot-row">
        <Button size="sm" onClick={() => void runStart()} disabled={busy} data-testid="setup-summary-run-start" title="halo start: the card above says what it calls and costs">
          {busy ? "Running..." : "Run the guided first run"}
        </Button>
        <span className="su-note muted">its seven steps show on the Check page, under its row</span>
      </div>
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
      <StartPart />
    </div>
  );
}
