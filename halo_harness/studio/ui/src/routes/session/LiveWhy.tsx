// `why?` on an action row that a thought led to (3.3.16.2): its first answer is that thought, opened inline under the
// row (LiveThink.tsx WhyThought, `live-why`); "what the model saw" there asks the turn's postmortem as before (Why.tsx,
// the Inspector). A row no thought led to keeps Why.tsx's own chip.
import { useState } from "react";
import type { LiveLine } from "../shared/liveFeed";
import { WhyThought } from "./LiveThink";

export function WhyChip({ l, thought }: { l: LiveLine; thought: LiveLine }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className="slv-why mono" data-testid="session-live-why" data-thought={thought.n} aria-pressed={open} aria-expanded={open}
              onClick={() => setOpen(!open)} title={open ? "Hide the thought" : "Why? The thought that led to this, under the row"}>
        why?
      </button>
      {open && <WhyThought l={l} thought={thought} />}
    </>
  );
}
