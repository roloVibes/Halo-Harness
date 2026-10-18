// The Team board's run bar (3.0.8.0 R2): the run id and its state, what it
// cost, the runner dot (live: Studio drives the run now; none: nothing
// drives it), Run next (`POST team/run` with no stage: the first pending
// manual stage), Stop (asks for a reason on a card) and Validate (the file's
// problems and the lineup preflight, in a dialog). 3.0.9.0 R3: Coach, once the
// run is done or stopped (the post-run coach's cards, in a dialog).
import { Button } from "../../lib/ui";
import { runStage, validate } from "./actions";
import { openDialog, runOpen, usd, useTeam } from "./store";

export function RunBar() {
  const run = useTeam((s) => s.board?.run || null);
  const state = useTeam((s) => s.board?.state || "none");
  const cost = useTeam((s) => s.status?.cost_usd || 0);
  const live = useTeam((s) => s.live || !!s.status?.runner_live);
  const open = useTeam(runOpen);
  const busy = useTeam((s) => s.busy);
  const name = useTeam((s) => s.info?.team?.name || "");
  const reason = useTeam((s) => s.board?.stop_reason || "");
  return (
    <div className="tm-bar" data-testid="team-runbar" data-state={state}>
      <b className="tm-bar-name">{name}</b>
      <span className="mono tm-bar-run" data-testid="team-run-id" title={run ? `the run ledger: .halo/team/${run}/` : "no run yet: Run next starts one"}>
        {run ? `run ${run}` : "no run yet"}
      </span>
      <span className="og-chip mono tm-run-state" data-testid="team-run-state" data-state={state} title={reason || undefined}>{state === "none" ? "not started" : state}</span>
      <span className="mono muted" title="what the run's stages cost so far">{usd(cost)}</span>
      <span className="tm-runner mono" data-testid="team-runner" data-live={live || undefined} title={live ? "Studio drives this run now (the block watchers armed)" : "nothing drives the run now: Run or an answer starts it"}>
        <i className="tm-runner-dot" /> {live ? "runner live" : "no runner"}
      </span>
      <span className="spacer" />
      <Button size="sm" variant="primary" disabled={busy === "run"} onClick={() => void runStage(null)} title="Start the next pending manual stage" data-testid="team-run-next">Run next</Button>
      <Button size="sm" variant="danger" disabled={!open || busy === "stop"} onClick={() => openDialog({ kind: "stop" })} title={open ? "End the run: every stage not done is skipped (asks for a reason)" : "No open run"} data-testid="team-stop">Stop</Button>
      <Button size="sm" variant="ghost" disabled={!run || (state !== "done" && state !== "stopped")} onClick={() => run && openDialog({ kind: "coach", run })}
              title={run && (state === "done" || state === "stopped") ? "What the run's files suggest changing" : "The coach reads a run once it is done or stopped"} data-testid="team-coach">Coach</Button>
      <Button size="sm" variant="ghost" disabled={busy === "validate"} onClick={() => void validate()} title="Check the file and run the lineup preflight for every member" data-testid="team-validate">Validate</Button>
    </div>
  );
}
