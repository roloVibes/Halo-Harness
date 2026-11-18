// The Map drawer's title for the page it shows (pure: tests/test_goal_run_report_page.py loads it in node). 3.6.0.3 B:
// a goal run's pages -- `run:<id>` while it runs, `report:<id>` once it ended -- are "Goal run" (the id is inside the
// page); the goal form -- the first page, and any other -- is "Run a goal". The view bar's drawer
// button keeps the room of the longest from the first draw (styles/agents.css, 7.6em).
export const mapPageTitle = (page: string): string =>
  page.startsWith("run:") || page.startsWith("report:") ? "Goal run" : "Run a goal";
