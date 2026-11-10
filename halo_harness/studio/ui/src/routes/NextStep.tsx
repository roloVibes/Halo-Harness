// The footer every Start view ends with (3.1.1.0 R1): "Next: <where> -- <one line>", so the Start views read as one
// story. 3.3.16.0 R1: Agents' two Start views, then Fleet, and back (Team's Start view went with its board; 3.3.13.0
// R2: Design left the story with the core for the design pack). 3.3.16.0 R2: the Fleet section went, its Start view
// is Setup -> Machines' lead -- Cast -> Runs -> Machines -> Cast. The button opens it.
import { goSection } from "../lib/store";
import { goto as gotoSetup } from "./setup/pages";

export type StoryStep = "cast" | "runs" | "machines";
export const STORY: StoryStep[] = ["cast", "runs", "machines"];

const TITLE: Record<StoryStep, string> = { cast: "Agents: Cast", runs: "Agents: Runs", machines: "Setup: Machines" };

/** Why the next step comes next, one line each (keyed by the NEXT step). */
export const NEXT_LINE: Record<StoryStep, string> = {
  runs: "give your lineup one goal and watch its agents split it, write it and pass the gate",
  machines: "pair your other machines: their agents show on Live, their models in Local",
  cast: "back to the start: tune the lineup every section runs",
};

export function nextOf(step: StoryStep): StoryStep {
  const i = STORY.indexOf(step);
  return STORY[(i + 1) % STORY.length];
}

export function NextStep({ from }: { from: StoryStep }) {
  const next = nextOf(from);
  const go = () => (next === "machines" ? (gotoSetup("machines"), goSection("setup")) : goSection("agents", next));
  return (
    <footer className="start-next" data-testid="start-next" data-next={next}>
      <span className="start-next-label mono">NEXT</span>
      <button className="start-next-btn" onClick={go} data-testid="start-next-go">
        <b>{TITLE[next]}</b>
        <span className="muted"> -- {NEXT_LINE[next]}</span>
      </button>
    </footer>
  );
}
