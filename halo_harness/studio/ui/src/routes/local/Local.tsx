// Local (Alt+0, 3.3.5.0 R1, plans/ROADMAP.md "3.3.5.0 becomes Local"): the
// machines that serve models and the models they serve, in one tab. Paged like
// Setup and Settings: the page rail on the left (LocalRail.tsx), one page on the
// right (LocalPage.tsx): Resources (the live strip per host and the traffic
// view), Hosts (every server Halo knows, its controls), Models (every model per
// host, its card and meter, the intent filter), then Library, Hugging Face,
// Benchmarks and Steward, framed for the rounds that fill them. No panel
// workspace, nothing to move or Arrange, and nothing opens on its own; the page
// lands on Resources or the page last open (pages.ts), a door's `?page=` on that
// page (door.ts). Fleet's Ollama panel stays the short form and links here.
import { useEffect } from "react";
import { LocalPage } from "./LocalPage";
import { LocalRail } from "./LocalRail";
import { startJobs } from "./jobs";
import { adoptRemembered } from "./pages";
import { loadHosts, startLocal } from "./store";

/** The section's view: the rail beside the open page. */
export function LocalView() {
  useEffect(() => {
    startLocal();
    startJobs(); // 3.3.5.0 R3: the pull jobs (running ones too) and their frames
    adoptRemembered();
    void loadHosts();
  }, []);
  return (
    <div className="lc-room" data-testid="local-room">
      <LocalRail />
      <div className="lc-scroll">
        <LocalPage />
      </div>
    </div>
  );
}

/** The section's entry (the palette or a door may open a page before the view draws). */
export function enterLocal(): void {
  startLocal();
  startJobs();
}
