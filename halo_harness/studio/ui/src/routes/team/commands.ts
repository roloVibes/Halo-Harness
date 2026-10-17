// The palette's Team group (3.0.8.0 R2): run the next stage, validate, stop
// the run (asks for a reason), open the team file (its path in a dialog with
// Copy), and run or open each stage by name.
import { goSection } from "../../lib/store";
import { runStage, select, showTeamPanel, validate } from "./actions";
import { openDialog, rows, runOpen, team } from "./store";
import { startTeam } from "./sync";

export type TeamCommand = { id: string; group: string; label: string; hint?: string; kbd?: string; run: () => void };

function inTeam(fn: () => void): () => void {
  return () => {
    goSection("team");
    startTeam();
    window.setTimeout(fn, 60);
  };
}

export function teamCommands(): TeamCommand[] {
  const s = team.get();
  const g = "Team";
  const out: TeamCommand[] = [
    { id: "team-run-next", group: g, label: "Team: run next stage", hint: "the first pending manual stage (POST team/run)", run: inTeam(() => void runStage(null)) },
    { id: "team-validate", group: g, label: "Team: validate", hint: "the file's problems and the lineup preflight for every member", run: inTeam(() => void validate()) },
    { id: "team-stop", group: g, label: "Team: stop", hint: runOpen(s) ? `end run ${s.board?.run} (asks for a reason)` : "no open run", run: inTeam(() => runOpen(team.get()) && openDialog({ kind: "stop" })) },
    { id: "team-open-file", group: g, label: "Team: open file", hint: s.info?.path || "where the team file is", run: inTeam(() => openDialog({ kind: "file" })) },
  ];
  for (const r of rows(s))
    out.push({ id: "team-stage-" + r.id, group: g, label: `Team: open stage ${r.id}`, hint: `${r.kind} · ${r.state} · ${r.trigger}`, run: inTeam(() => (select({ kind: "stage", id: r.id }), showTeamPanel("team-inspector"))) });
  return out;
}
