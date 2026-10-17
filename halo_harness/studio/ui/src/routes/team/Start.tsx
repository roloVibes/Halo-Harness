// The Team section before there is a team to draw (3.0.8.0 R2): one Start
// view instead of three empty panels -- what a team is in three sentences
// (next to a lineup, an Orchestra run, a flow and a mission), the steps, and
// one button: Make my first team (`POST team/init`: the shipped template in
// <repo>/.halo/team.yaml and a starter brief). With a file that does not load
// or has problems, the Problems list instead, with Validate. "open the board
// anyway" (or ?view=workspace) goes straight to the panels.
import { useEffect } from "react";
import { Button, Surface } from "../../lib/ui";
import { Workspace } from "../../lib/workspace/Workspace";
import type { PanelSpec } from "../../lib/workspace/types";
import { SECTION_HELP } from "../sectionHelp";
import { initTeam, validate } from "./actions";
import { TeamDialogs } from "./Dialogs";
import { setView, showsStart, useTeam } from "./store";
import { startTeam } from "./sync";

export const WHAT: string[] = [
  "A team is one file that says who works on this project, where their work lands and in which order: the brief every agent reads first, the members, the blocks (a file, a folder or a git tree) and the stages.",
  "A lineup says who can play each part, an Orchestra run is several workers on one goal, a flow is a fixed pipeline with gates and a mission is one goal across the fleet; a team sits above them: its members play lineup parts and its stages are agent turns, Orchestra runs or flows.",
  "The board shows every stage as it runs, every block with who holds it and what changed, and every gate that waits on you.",
];

function Problems() {
  const info = useTeam((s) => s.info);
  const busy = useTeam((s) => s.busy);
  if (!info?.found) return null;
  return (
    <div className="tm-start-problems" data-testid="team-start-problems">
      <p>
        <b>{info.team ? "The team file has problems." : "The team file does not load."}</b> <span className="muted mono">{info.path}</span>
      </p>
      <ul>
        {info.problems.map((p) => (
          <li key={p} data-testid="team-start-problem">{p}</li>
        ))}
      </ul>
      <p className="muted">Fix them in the file (your editor), then Validate; the board shows as soon as the file is clean.</p>
      <div className="os-buttons">
        <Button variant="primary" disabled={busy === "validate"} onClick={() => void validate()} data-testid="team-start-validate">Validate</Button>
      </div>
    </div>
  );
}

export function StartView() {
  const copy = SECTION_HELP.team;
  const info = useTeam((s) => s.info);
  const busy = useTeam((s) => s.busy);
  const error = useTeam((s) => s.error);
  return (
    <div className="fl-start tm-start" data-testid="team-start">
      <div className="fl-start-inner">
        <header className="fl-start-head">
          <div className="glance-kicker mono">TEAM · PEOPLE, BLOCKS AND STAGES</div>
          <h1 className="fl-start-title">Your project's team</h1>
          {WHAT.map((line) => (
            <p key={line.slice(0, 24)} className="muted">{line}</p>
          ))}
        </header>
        <div className="fl-start-grid">
          <Surface className="fl-start-form" motion="idle">
            {info?.found ? (
              <Problems />
            ) : (
              <div className="os-where">
                <p>
                  This project has no team file yet. Make one from the shipped template: <span className="mono">{info?.path || ".halo/team.yaml"}</span> and a starter
                  {" "}<span className="mono">docs/BRIEF.md</span>, the same files <span className="mono">halo team init</span> writes. Edit them, then Validate and Run.
                </p>
                <div className="os-buttons">
                  <Button variant="primary" disabled={busy === "init"} onClick={() => void initTeam()} data-testid="team-start-init">Make my first team</Button>
                </div>
              </div>
            )}
            {error && <p className="og-problems">Studio could not read the team: {error}</p>}
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
            <button className="og-link mono" onClick={() => setView("workspace")} data-testid="team-open-workspace">open the board anyway</button>
          </aside>
        </div>
      </div>
    </div>
  );
}

/** The Team section: the Start view until the team loads clean, then the panels. */
export function TeamView({ section, specs }: { section: string; specs: PanelSpec[] }) {
  useEffect(() => startTeam(), []);
  const loaded = useTeam((s) => s.loaded);
  const start = useTeam(showsStart);
  if (!loaded)
    return (
      <div className="fl-start">
        <div className="og-wait mono muted">reading the team...</div>
      </div>
    );
  return (
    <>
      {start ? <StartView /> : <Workspace section={section} specs={specs} />}
      <TeamDialogs />
    </>
  );
}
