"""tests.test_studio_ui -- the Studio page boots in a real browser (Halo
2.1.0 round B3): headless Chrome loads the page over a seeded scratch home,
the lineup draws its node cards, and docs/media/studio-roles.png (the README's
capture) exists and is a PNG. 3.0.3.0: the classic page is the one at
/legacy/, and the React shell at / is checked by its data-testid counts. Skipped when no Chrome is found, like the
front-page PNG step. 3.0.4.0 R6b (Studio clarity): the Orchestra Start view
then the grid, a click focuses a panel and `?` opens its help, the framed
classic page has no second header, and the Roles canvas draws its groups --
the last three through real clicks and keys (tests/helpers/studio_clarity.py
over the DevTools protocol).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


def _chrome() -> "str | None":
    sys.path.insert(0, str(REPO / "tools"))
    from capture_screens import find_chrome
    return find_chrome(os.environ.get("HALO_CHROME", ""))


_RUNS: dict = {}


def _json_of(*args: str) -> "tuple[subprocess.CompletedProcess, dict]":
    """Run a tool or helper with a scrubbed environment (its own scratch home), once per argument list;
    the last stdout line is its JSON."""
    if args not in _RUNS:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_"))}
        env["PYTHONPATH"] = str(REPO)
        env["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        r = subprocess.run([sys.executable, *args], capture_output=True, encoding="utf-8", errors="replace", timeout=300, env=env, cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUNS[args] = (r, info)
    return _RUNS[args]


@test
def test_page_boots_and_draws_nodes_in_headless_chrome(ctx: Ctx):
    if not _chrome():
        raise SkipTest("no Chrome found (the page smoke needs headless Chrome)")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_"))}
    env["PYTHONPATH"] = str(REPO)
    env["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
    r = subprocess.run([sys.executable, str(REPO / "tools" / "capture_studio.py"), "--dom"], capture_output=True, text=True, timeout=240, env=env, cwd=str(REPO))
    ctx.check(f"the capture tool ran, got {r.stdout[-300:]!r} {r.stderr[-300:]!r}", r.returncode == 0)
    try:
        info = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        info = {}
    ctx.check(f"the page drew the halo-dev-cycle cards, got {info}", info.get("nodes", 0) >= 7 and "Halo Studio" in info.get("title", ""))


@test
def test_shell_boots_with_its_sections_in_headless_chrome(ctx: Ctx):
    """3.0.3.0: the React shell at / draws the section tabs (five since
    3.0.4.0: Flow is Alt+5); Orchestra shows its console, Roles frames the
    classic page at /legacy/."""
    if not _chrome():
        raise SkipTest("no Chrome found (the shell smoke needs headless Chrome)")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_"))}
    env["PYTHONPATH"] = str(REPO)
    env["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
    r = subprocess.run([sys.executable, str(REPO / "tools" / "capture_studio.py"), "--mode", "shell", "--dom"], capture_output=True, text=True, timeout=240, env=env, cwd=str(REPO))
    ctx.check(f"the capture tool ran, got {r.stdout[-300:]!r} {r.stderr[-300:]!r}", r.returncode == 0)
    try:
        info = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        info = {}
    orch, roles = info.get("orchestra", {}), info.get("roles", {})
    # R6b: a folder with no Orchestra run opens on the Start view, not on empty panels
    ctx.check(f"Orchestra: five section tabs and the Start view, got {orch}", orch == {"section-tab": 5, "orchestra-root": 0, "start-view": 1, "legacy-frame": 0})
    ctx.check(f"Roles: five section tabs and the framed classic page, got {roles}", roles == {"section-tab": 5, "orchestra-root": 0, "start-view": 0, "legacy-frame": 1})
    ctx.check("the title names the section", "Halo Studio" in info.get("title", ""))


@test
def test_orchestra_run_console_draws_a_finished_run_in_headless_chrome(ctx: Ctx):
    """3.0.3.0 R4: over a seeded finished run (the R2 fixture: five lanes, one
    judged conflict, eight checks) the Orchestra section draws the graph with
    its gate, five lanes, five claimed bands, every check and five tiles."""
    if not _chrome():
        raise SkipTest("no Chrome found (the Orchestra smoke needs headless Chrome)")
    r, info = _json_of(str(REPO / "tools" / "capture_studio.py"), "--mode", "orchestra", "--dom")
    ctx.check(f"the capture tool ran, got {r.stdout[-300:]!r} {r.stderr[-300:]!r}", r.returncode == 0)
    ctx.check(f"the graph and its gate, got {info}", info.get("orchestra-graph") == 1 and info.get("gate", 0) >= 1)
    ctx.check(f"five lanes and five tiles, got {info}", info.get("lane") == 5 and info.get("grid-tile") == 5)
    ctx.check(f"a band per claimed unit, got {info}", info.get("claim-region", 0) >= 5)
    ctx.check(f"every report check, got {info}", info.get("report-check") == 8)
    ctx.check(f"the shell around it, got {info}", info.get("section-tab") == 5 and info.get("orchestra-root") == 1)


@test
def test_flow_section_draws_a_run_in_headless_chrome(ctx: Ctx):
    """3.0.4.0 R6: over a finished social-post run and one parked at its
    confirm gate (the R3 fakes, a FakeComfy) the Flow section draws its eight
    panels, the gate diamond, the open gate's card with the render inline,
    the accepted band and the dry-run posts of the finished run, the runs in
    the rail, and the four Media panels as strips. Owner feedback (R6): the
    Start view stands in for empty panels (`?view=start`), and while ComfyUI
    does not answer the Media group is one status card with the fix."""
    if not _chrome():
        raise SkipTest("no Chrome found (the Flow smoke needs headless Chrome)")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_"))}
    env["PYTHONPATH"] = str(REPO)
    env["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
    r = subprocess.run([sys.executable, str(REPO / "tools" / "capture_studio.py"), "--mode", "flow", "--dom"], capture_output=True,
                       encoding="utf-8", errors="replace", timeout=300, env=env, cwd=str(REPO))
    ctx.check(f"the capture tool ran, got {r.stdout[-300:]!r} {r.stderr[-300:]!r}", r.returncode == 0)
    try:
        info = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        info = {}
    wait, done = info.get("waiting", {}), info.get("finished", {})
    panels = ("flow-intake", "flow-graph", "flow-step", "flow-renders", "flow-posts", "flow-metrics", "flow-log", "flow-report",
              "media-status", "media-models", "media-workflows", "media-render")
    for name, got in (("waiting", wait), ("finished", done)):
        ctx.check(f"{name}: five section tabs and every Flow and Media panel once, got {got}",
                  got.get("section-tab") == 5 and all(got.get(p) == 1 for p in panels))
        ctx.check(f"{name}: the confirm step is the gate diamond, got {got.get('gate-diamond')}", got.get("gate-diamond") == 1)
        ctx.check(f"{name}: the render inline and both runs in the rail, got {got}", got.get("flow-artboard") == 1 and got.get("flow-rail-run") == 2)
    ctx.check(f"waiting: the gate card is open, nothing answered yet, got {wait}", wait.get("gate-card") == 1 and wait.get("gate-answered") == 0)
    ctx.check(f"finished: the band says accepted, no card, two dry-run posts, got {done}",
              done.get("gate-card") == 0 and done.get("gate-answered") == 1 and done.get("flow-post") == 2)
    start, down = info.get("start", {}), info.get("down", {})
    ctx.check(f"?view=start: one Start view with the intake form and the past runs, no empty panels, got {start}",
              start.get("flow-start") == 1 and start.get("flow-intake-form") == 1 and start.get("flow-rail-run") == 2
              and not any(start.get(p) for p in panels))
    ctx.check(f"ComfyUI down: the status card with the fix, the other three Media panels gone, got {down}",
              down.get("media-fix") == 1 and down.get("media-status") == 1
              and not any(down.get(p) for p in ("media-models", "media-workflows", "media-render")))


@test
def test_orchestra_start_view_then_grid(ctx: Ctx):
    """R6b: with no run the Orchestra section is one Start view (the goal form,
    the explainer, open the workspace anyway), no empty panels; once a run is
    open the grid shows, every panel with its about line, the Goal panel with
    every field and Run at its default size (no inner scroll), the run in the
    rail. The first visit (no tour=off) shows the section's welcome card."""
    if not _chrome():
        raise SkipTest("no Chrome found (the Orchestra smoke needs headless Chrome)")
    r, grid = _json_of(str(REPO / "tools" / "capture_studio.py"), "--mode", "orchestra", "--dom")
    ctx.check(f"the capture tool ran, got {r.stdout[-300:]!r} {r.stderr[-300:]!r}", r.returncode == 0)
    start = grid.get("start", {})
    ctx.check(f"no run: the Start view with the goal form and the way to the panels, got {start}",
              start.get("start-view") == 1 and start.get("orchestra-goal-form") == 1 and start.get("orchestra-open-workspace") == 1)
    ctx.check(f"no run: none of the run panels, got {start}",
              not any(start.get(k) for k in ("orchestra-root", "orchestra-graph", "lane", "grid-tile", "report-check", "panel-about")))
    ctx.check(f"a run open: the grid, not the Start view, got {grid}", grid.get("start-view") == 0 and grid.get("orchestra-root") == 1)
    ctx.check(f"a run open: eight about lines, the run in the rail, got {grid}", grid.get("panel-about") == 8 and grid.get("orchestra-rail-run") == 1)
    ctx.check("the Goal panel fits every field and Run at its default size", grid.get("goal-overflow") is False)
    ctx.check(f"tour=off keeps the welcome shut; a first visit shows it, got {grid.get('section-help')} / {grid.get('welcome')}",
              grid.get("section-help") == 0 and grid.get("welcome", {}).get("section-help") == 1)


@test
def test_panel_focus_on_click_and_help(ctx: Ctx):
    """R6b: a click on a panel's body focuses it (the ring, the keyboard
    focus); `?` opens its help from the PanelSpec and Esc closes it; the ...
    menu has Float, Collapse, Reset, Settings and Help; Settings opens the
    Inspector, which follows the next panel clicked; the Compact toggle; the
    section's "How this works" from the ? beside the tabs, remembered as seen."""
    if not _chrome():
        raise SkipTest("no Chrome found (the click test needs headless Chrome)")
    r, got = _json_of("-m", "tests.helpers.studio_clarity", "panel")
    ctx.check(f"the click run finished, got {r.stdout[-300:]!r} {r.stderr[-400:]!r}", r.returncode == 0)
    ctx.check(f"eight about lines, got {got.get('about')}", got.get("about") == 8)
    ctx.check(f"the clicked panel is the one active and focused, got {got}", got.get("active") is True and got.get("focused") is True and got.get("others_active") == 1)
    ctx.check(f"a click on a title bar focuses that panel and leaves the layout default, got {got.get('title_click')} / {got.get('layout_after_click')}",
              got.get("title_click") == "graph" and got.get("layout_after_click") == "default")
    ctx.check(f"? opens the Report's help, got {got.get('help_title')} / {got.get('help_lines')}", got.get("help_title") == "Report" and got.get("help_lines", 0) >= 3)
    ctx.check("Esc closes it", got.get("help_closed") is True)
    ctx.check(f"the ... menu, got {got.get('menu')}", got.get("menu") == ["float", "collapse", "reset", "settings", "help"])
    ctx.check(f"Settings opens the Inspector on Lanes, then it follows the click to Report, got {got.get('inspector')} / {got.get('inspector_follows')}",
              got.get("inspector") == "Lanes" and got.get("inspector_follows") == "Report")
    ctx.check("the Compact toggle", got.get("compact") == "glance")
    ctx.check(f"How Orchestra works: steps and every panel, got {got}",
              got.get("section_title") == "How Orchestra works" and got.get("section_steps") == 5 and got.get("section_panels") == 8)
    ctx.check("closed and remembered as seen", got.get("section_closed") is True and got.get("seen") == "1")


@test
def test_legacy_embedded_hides_header(ctx: Ctx):
    """R6b: framed in the shell (embedded=1) the classic page has no logo, no
    Roles / Org / Design buttons and no footer, a toolbar at most 48 px tall;
    its status line shows in the shell's status bar; O inside the frame
    switches the SHELL to Org; opened on its own it keeps its full header."""
    if not _chrome():
        raise SkipTest("no Chrome found (the embedded-page test needs headless Chrome)")
    r, dom = _json_of(str(REPO / "tools" / "capture_studio.py"), "--mode", "orchestra", "--dom")
    roles = dom.get("roles", {})
    ctx.check(f"the embedded page's DOM: the toolbar, no logo, no mode buttons, got {roles}",
              roles.get("legacy-toolbar") == 1 and roles.get("embedded") == 1 and roles.get("brand") == 0 and roles.get("mode-buttons") == 0)
    r, got = _json_of("-m", "tests.helpers.studio_clarity", "legacy")
    ctx.check(f"the click run finished, got {r.stdout[-300:]!r} {r.stderr[-400:]!r}", r.returncode == 0)
    ctx.check(f"in the shell: toolbar, no logo, no mode buttons, no footer, got {got}",
              got.get("toolbar") is True and got.get("brand") is False and got.get("mode_buttons") == 0 and got.get("footer_shown") is False)
    ctx.check(f"one slim line, got {got.get('toolbar_height')}", 0 < (got.get("toolbar_height") or 0) <= 48)
    ctx.check(f"the page's status line is in the shell's status bar, got {got.get('status')!r}", "valid" in str(got.get("status")))
    ctx.check(f"O in the frame switches the shell's section, got {got.get('section_after_o')}", got.get("section_after_o") == "Org")
    ctx.check(f"on its own: the full header and the footer, got {got}",
              got.get("standalone_brand") is True and got.get("standalone_modes") == 3 and got.get("standalone_footer") is True)


@test
def test_roles_canvas_draws_groups(ctx: Ctx):
    """R6b: the Roles canvas draws one labelled box per role of the lineup
    (halo-dev-cycle: Main, Workers, Researchers, Reviewers, Custom roles)
    with every card inside one; a card dropped into another box takes its
    role; the toolbar's Groups button hides and shows them."""
    if not _chrome():
        raise SkipTest("no Chrome found (the groups test needs headless Chrome)")
    r, got = _json_of("-m", "tests.helpers.studio_clarity", "legacy")
    ctx.check(f"the click run finished, got {r.stdout[-300:]!r} {r.stderr[-400:]!r}", r.returncode == 0)
    ctx.check(f"five boxes, got {got.get('groups')} {got.get('labels')}",
              got.get("groups") == 5 and set(got.get("labels") or []) == {"Main", "Workers", "Researchers", "Reviewers", "Custom roles"})
    ctx.check("every card sits inside a box", got.get("cards_in_boxes") is True)
    ctx.check(f"verify dropped into Reviewers became a reviewer, got {got.get('joined')} / {got.get('reviewers')}",
              got.get("joined") == "reviewer" and got.get("reviewers") == 2)
    ctx.check(f"Groups hides them and shows them again, got {got.get('groups_off')} / {got.get('groups_on')}",
              got.get("groups_off") == "off" and (got.get("groups_on") or 0) >= 5)
    ctx.check(f"an empty catalog shows the model notice with a Refresh button, got {got.get('models_notice')}",
              (got.get("models_notice") or 0) >= 1)


@test
def test_readme_capture_exists(ctx: Ctx):
    png = REPO / "docs" / "media" / "studio-roles.png"
    ctx.check("docs/media/studio-roles.png exists", png.is_file())
    if png.is_file():
        ctx.check("it is a PNG under 1 MB", png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and png.stat().st_size < 1024 * 1024)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio ui tests"))
