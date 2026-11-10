// The Inspector's Lineup tab (3.0.7.0 R2; 3.3.16.0 R1b "one thing at a time"): it opens on the lineup's SUMMARY
// (LineupSummary.tsx: six plain-words lines, then one Edit row per block) and Edit opens that block alone on its page
// (LineupPage.tsx: what this does, "not set = Halo does ...", the block's form, its YAML toggle, its `?`). Studio is
// the one editor of lineups (`halo studio --edit lineup:<name>` opens the summary, `lineup:<name>:<block>` that
// page). A save that answers 422 lists the validator's lines above either (LineupHeader.tsx SaveProblems). Every
// testid of the 3.0.7.0 tab stays: `roles-lineup-tab` here, `roles-block-<name>` on the summary's rows, the rest on
// the pages.
import { LineupPage } from "./LineupPage";
import { SaveProblems } from "./LineupHeader";
import { LineupSummary } from "./LineupSummary";
import { useLineupPage } from "./pages";
import { useRoles } from "./store";

/** The summary or one block's page (the Assignment tab with no card draws the same). */
export function LineupBody() {
  const page = useLineupPage();
  return (
    <>
      <SaveProblems />
      {page ? <LineupPage id={page} /> : <LineupSummary />}
    </>
  );
}

export function LineupTab() {
  const name = useRoles((s) => s.name);
  const page = useLineupPage();
  if (!name) return <p className="muted">Open a lineup in Lineups first.</p>;
  return (
    <div className="re-lineup" data-testid="roles-lineup-tab" data-lineup={name} data-page={page || "summary"}>
      <LineupBody />
    </div>
  );
}
