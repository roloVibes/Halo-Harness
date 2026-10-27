// Setup (Alt+8): this box's setup, the terminal wizard's steps as pages
// (3.3.1.0 R1, after the owner on 3.3.0.0's one page of eight panels: "Have it
// go thru pages not like a huge confusing blob on one page"). On top the step
// rail (SetupRail.tsx: the wizard's order, the current step highlighted, the
// done ones ticked, a click opens any) with its one-line summary of what is
// set; under it one page (SetupPage.tsx): one block, its own Save, Back /
// Next; the Summary last (Summary.tsx). The pages are pages.ts. No panel
// workspace here: nothing to move, resize or Arrange, the room is the page.
// 3.3.0.0's blocks are unchanged inside: R1 Default model, Permissions,
// Terminal theme and Team; R2 Providers and Local models; R3 Linux fixes and
// Check; R4 the doors (door.ts: `?first=1` leads the summary line with "set
// up this box" and opens nothing, `?block=` opens that page).
import { useEffect } from "react";
import { startDoneFeed } from "./done";
import { adoptRemembered } from "./pages";
import { SetupPage } from "./SetupPage";
import { SetupRail } from "./SetupRail";
import { startSetup, useSetup } from "./store";

/** The section's view: the rail over the open page. */
export function SetupView() {
  const home = useSetup((s) => s.data?.home || "");
  useEffect(() => {
    startSetup();
    startDoneFeed();
  }, []);
  useEffect(() => adoptRemembered(home), [home]);
  return (
    <div className="su-page" data-testid="setup-page">
      <SetupRail />
      <div className="su-scroll">
        <SetupPage />
      </div>
    </div>
  );
}

/** The section's entry (the palette or a door may open a page before the view draws). */
export function enterSetup(): void {
  startSetup();
  startDoneFeed(); // 3.3.3.0 R1: a Done pressed in another tab moves this one too
}
