// The footer every Start view ends with (3.1.1.0 R1): "Next: <section> --
// <one line>", so the five Start views read as one story in this order:
// Roles -> Orchestra -> Team -> Design -> Fleet (Fleet's
// points back to Roles). The button opens that section.
import { goSection, type SectionId } from "../lib/store";

export const STORY: SectionId[] = ["roles", "orchestra", "team", "design", "fleet"];

// the section titles (routes/index.tsx SECTIONS has the same; kept here so the Start views need not import the registry)
const TITLE: Record<SectionId, string> = { roles: "Roles", orchestra: "Orchestra", team: "Team", design: "Design", fleet: "Fleet" };

/** Why the next section comes next, one line each (keyed by the NEXT section). */
export const NEXT_LINE: Record<SectionId, string> = {
  orchestra: "give your lineup one goal and watch its agents split it, write it and pass the gate",
  team: "put members, blocks and stages in your own repo's team file",
  design: "prototypes, pages and decks made on your own apps",
  fleet: "join your other machines and give the whole fleet one goal",
  roles: "back to the start: tune the lineup every section runs",
};

export function nextOf(section: SectionId): SectionId {
  const i = STORY.indexOf(section);
  return STORY[(i + 1) % STORY.length];
}

export function NextStep({ from }: { from: SectionId }) {
  const next = nextOf(from);
  const title = TITLE[next];
  return (
    <footer className="start-next" data-testid="start-next" data-next={next}>
      <span className="start-next-label mono">NEXT</span>
      <button className="start-next-btn" onClick={() => goSection(next)} data-testid="start-next-go">
        <b>{title}</b>
        <span className="muted"> -- {NEXT_LINE[next]}</span>
      </button>
    </footer>
  );
}
