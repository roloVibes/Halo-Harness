// The Map drawer's title for the page it shows (pure: tests/test_goal_run_report_page.py loads it in node). 3.6.0.3 B:
// a goal run's pages -- `run:<id>` while it runs, `report:<id>` once it ended -- are "Goal run" (the id is inside the
// page); the goal form is "Run a goal"; History's list keeps its name while History is there. The view bar's drawer
// button keeps the room of the longest from the first draw (styles/agents.css, 7.6em).
export const mapPageTitle = (page: string): string =>
  page === "goal" ? "Run a goal" : page.startsWith("run:") || page.startsWith("report:") ? "Goal run" : "History";
