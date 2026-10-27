"""tests.test_studio_ui -- Studio in a real browser (headless Chrome; skipped without one).
3.0.7.0 R2: the React Roles section draws the lineup's cards in their tier boxes; the shell at
/ by its data-testid counts. 3.0.4.0 R6b (tests/helpers/studio_clarity.py): the Orchestra
Start view then the grid, a click focuses a panel and `?` opens its help; no section nests a
second header. Registered here: R2 Roles (studio_ui_roles.py), 3.0.5.0 Fleet (studio_ui_fleet.py),
3.0.6.0 Missions (studio_ui_mission.py), 3.0.7.0 R3 the React Design section (studio_ui_design.py),
3.0.8.0 R2 the Team tab (studio_ui_team.py), 3.0.9.0 R2 the plan canvas (studio_ui_plan.py), R3 the coach
(studio_ui_coach.py); five section tabs since 3.1.4.0 R3 (Org and Flow are gone), six with Session (Alt+1 and the first tab since
3.1.6.0 R6: tests/helpers/studio_ui_order.py reads the tab strip in order);
3.1.4.0 R1 the Fleet default layout (studio_ui_fleet_layout.py).
"""

from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all
from tests.helpers.studio_ui_fleet import register as register_fleet
from tests.helpers.studio_ui_fleet_layout import register as register_fleet_layout
from tests.helpers.studio_ui_coach import register as register_coach
from tests.helpers.studio_ui_mission import register as register_mission
from tests.helpers.studio_ui_order import register as register_order
from tests.helpers.studio_ui_design import register as register_design
from tests.helpers.studio_ui_plan import register as register_plan
from tests.helpers.studio_ui_roles import register as register_roles
from tests.helpers.studio_ui_team import register as register_team

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


def _chrome() -> "str | None":
    from tests.helpers.chrome_driver import find_chrome  # 3.1.0.0 R1: the driver base (HALO_CHROME first)
    return find_chrome()


def _env() -> dict:
    """BRIDGE_* and the provider variables scrubbed (the driver scopes its own scratch home), HALO_CHROME kept."""
    from tests.helpers.chrome_driver import driver_env
    return driver_env(REPO)


_RUNS: dict = {}


def _json_of(*args: str) -> "tuple[subprocess.CompletedProcess, dict]":
    """Run a tool or helper with a scrubbed environment (its own scratch home), once per argument list;
    the last stdout line is its JSON."""
    if args not in _RUNS:
        r = subprocess.run([sys.executable, *args], capture_output=True, encoding="utf-8", errors="replace", timeout=300, env=_env(), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUNS[args] = (r, info)
    return _RUNS[args]


@test
def test_page_boots_and_draws_nodes_in_headless_chrome(ctx: Ctx):
    """3.0.7.0 R2: tools/capture_studio.py --dom (Roles, React): the Start view with only the shipped
    lineups, then the seeded lineup's eight cards in three tier boxes."""
    if not _chrome():
        raise SkipTest("no Chrome found (the page smoke needs headless Chrome)")
    r, info = _json_of(str(REPO / "tools" / "capture_studio.py"), "--mode", "roles", "--dom")
    ctx.check(f"the capture tool ran, got {r.stdout[-300:]!r} {r.stderr[-300:]!r}", r.returncode == 0)
    start, roles = info.get("start", {}), info.get("roles", {})
    ctx.check(f"the Start view first, got {start}", start.get("roles-start") == 1 and start.get("roles-card") == 0)
    ctx.check(f"then the cards in their tier boxes, got {roles}", roles.get("roles-card") == 8 and roles.get("roles-tier") == 3 and roles.get("roles-canvas") == 1)


@test
def test_shell_boots_with_its_sections_in_headless_chrome(ctx: Ctx):
    """3.0.3.0: the React shell at / draws the section tabs (five since
    3.1.4.0: Orchestra, Roles, Design, Fleet, Team); Orchestra shows its
    console, Roles (3.0.7.0 R2) its React canvas, no frame."""
    if not _chrome():
        raise SkipTest("no Chrome found (the shell smoke needs headless Chrome)")
    env = _env()
    r = subprocess.run([sys.executable, str(REPO / "tools" / "capture_studio.py"), "--mode", "shell", "--dom"], capture_output=True, encoding="utf-8", errors="replace", timeout=240, env=env, cwd=str(REPO))
    ctx.check(f"the capture tool ran, got {r.stdout[-300:]!r} {r.stderr[-300:]!r}", r.returncode == 0)
    try:
        info = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        info = {}
    orch, roles = info.get("orchestra", {}), info.get("roles", {})
    # R6b: a folder with no Orchestra run opens on the Start view, not on empty panels
    ctx.check(f"Orchestra: eight section tabs and the Start view, got {orch}", orch.get("section-tab") == 8 and orch.get("start-view") == 1 and orch.get("orchestra-root") == 0)
    ctx.check(f"Roles: seven section tabs and its canvas, no frame, got {roles}",
              roles == {"section-tab": 8, "orchestra-root": 0, "start-view": 0, "roles-canvas": 1, "roles-start": 0, "legacy-frame": 0})
    ctx.check("the title names the section", "Halo Studio" in info.get("title", ""))


@test
def test_orchestra_run_console_draws_a_finished_run_in_headless_chrome(ctx: Ctx):
    """3.0.3.0 R4: over a seeded finished run (the R2 fixture: five lanes, one
    judged conflict, eight checks) the Orchestra section draws the graph with
    its gate, five lanes, five claimed bands, every check and five tiles; 3.0.9.0:
    lane 2 takes lane 1's summary, so one lane-edge, and a base line on every lane."""
    if not _chrome():
        raise SkipTest("no Chrome found (the Orchestra smoke needs headless Chrome)")
    r, info = _json_of(str(REPO / "tools" / "capture_studio.py"), "--mode", "orchestra", "--dom")
    ctx.check(f"the capture tool ran, got {r.stdout[-300:]!r} {r.stderr[-300:]!r}", r.returncode == 0)
    ctx.check(f"the graph and its gate, got {info}", info.get("orchestra-graph") == 1 and info.get("gate", 0) >= 1)
    ctx.check(f"five lanes and five tiles, got {info}", info.get("lane") == 5 and info.get("grid-tile") == 5)
    ctx.check(f"a band per claimed unit, got {info}", info.get("claim-region", 0) >= 5)
    ctx.check(f"every report check, got {info}", info.get("report-check") == 8)
    ctx.check(f"3.0.9.0: lane 2's hand-off edge and every lane's base, got {info}", info.get("lane-edge") == 1 and info.get("lane-base") == 5)
    ctx.check(f"the shell around it, got {info}", info.get("section-tab") == 8 and info.get("orchestra-root") == 1)


@test
def test_orchestra_start_view_then_grid(ctx: Ctx):
    """R6b: with no run the Orchestra section is one Start view (the goal form,
    the explainer, open the workspace anyway), no empty panels; once a run is
    open the grid shows, every panel with its about line, the Goal panel with
    every field and Run at its default size (no inner scroll), the run in the
    expanded rail (3.3.2.0 R1: the icon rail draws no run list; tests/helpers/studio_clarity.py expands it).
    3.3.2.0 R1: the first visit (no tour=off) opens no welcome card either."""
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
    ctx.check(f"a run open: eight about lines, no run list in the icon rail, got {grid}", grid.get("panel-about") == 8 and grid.get("orchestra-rail-run") == 0)
    ctx.check("the Goal panel fits every field and Run at its default size", grid.get("goal-overflow") is False)
    ctx.check(f"3.3.2.0 R1: no help card with or without tour=off, got {grid.get('section-help')} / {grid.get('welcome')}",
              grid.get("section-help") == 0 and grid.get("welcome", {}).get("section-help") == 0)


@test
def test_panel_focus_on_click_and_help(ctx: Ctx):
    """R6b: a click on a panel's body focuses it (the ring, the keyboard
    focus); `?` opens its help from the PanelSpec and Esc closes it; the ...
    menu has Float, Collapse, Reset, Settings and Help; Settings opens the
    Inspector, which follows the next panel clicked; the Compact toggle; the
    section's "How this works" from the ? in the header (3.3.2.0 R1: nothing to remember as seen); the
    Orchestra run in the expanded rail."""
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
    ctx.check(f"the ? beside the tabs is a menu: How this works and the Glossary (3.1.1.0 R1), got {got.get('help_menu')}",
              got.get("help_menu") == ["section-help-item", "glossary-item"])
    ctx.check(f"How Orchestra works: steps and every panel, got {got}",
              got.get("section_title") == "How Orchestra works" and got.get("section_steps") == 8 and got.get("section_panels") == 8)  # 3.0.9.0 R3: + Coach
    ctx.check("closed; nothing remembered as seen (3.3.2.0 R1: no welcome to hold back)", got.get("section_closed") is True and got.get("seen") == 0)
    ctx.check(f"the run in the expanded rail (3.3.2.0 R1), got {got.get('rail_run')}", got.get("rail_run") == 1)


@test
def test_roles_header_is_not_nested(ctx: Ctx):
    """3.0.7.0 R2: Roles is a React section: no framed page, so no second header, its status line
    straight from its store in the shell's status bar."""
    if not _chrome():
        raise SkipTest("no Chrome found (the Roles test needs headless Chrome)")
    r, dom = _json_of(str(REPO / "tools" / "capture_studio.py"), "--mode", "orchestra", "--dom")
    roles = dom.get("roles", {})
    ctx.check(f"the Roles section: its canvas and cards, no frame, got {roles}",
              roles.get("roles-canvas") == 1 and (roles.get("roles-card") or 0) >= 7 and roles.get("legacy-frame") == 0 and roles.get("section-tab") == 8)


@test
def test_roles_canvas_draws_tier_boxes(ctx: Ctx):
    """3.0.7.0 R2: the Roles canvas draws one labelled box per tier (the seeded lineup: top, leads
    and the implicit rest) with every card inside the box of its tier."""
    if not _chrome():
        raise SkipTest("no Chrome found (the Roles test needs headless Chrome)")
    r, got = _json_of("-m", "tests.helpers.studio_roles", "roles")
    ctx.check(f"the click run finished, got {r.stdout[-300:]!r} {r.stderr[-400:]!r}", r.returncode == 0)
    ctx.check(f"eight cards in three tier boxes, got {got.get('cards')} {got.get('tiers')}", got.get("cards") == 8 and got.get("tiers") == ["top", "leads", "rest"])
    ctx.check("every card sits inside the box of its tier", got.get("cards_in_tiers") is True)
    ctx.check(f"3.1.1.0 R2: the Problems panel's Config group lists the lineup's unknown key, got {got.get('config_problem')!r}",
              "unknown key 'notes'" in str(got.get("config_problem") or ""))


register_fleet(test, _json_of, _chrome)  # the Fleet checks (R3 and R4): tests/helpers/studio_ui_fleet.py
register_fleet_layout(test, _json_of, _chrome)  # 3.1.4.0 R1: the default layout, the log line, the folds: tests/helpers/studio_ui_fleet_layout.py
register_mission(test, _json_of, _chrome)  # 3.0.6.0 R8: the Mission panel, tests/helpers/studio_ui_mission.py
register_design(test, _json_of, _chrome)  # 3.0.7.0 R3: Design in React, tests/helpers/studio_ui_design.py
register_roles(test, _json_of, _chrome)  # 3.0.7.0 R2: Roles in React, tests/helpers/studio_ui_roles.py
register_team(test, _json_of, _chrome)  # 3.0.8.0 R2: the Team tab, tests/helpers/studio_ui_team.py
register_plan(test, _json_of, _chrome)  # 3.0.9.0 R2: the plan canvas, tests/helpers/studio_ui_plan.py
register_coach(test, _json_of, _chrome)  # 3.0.9.0 R3: the post-run coach, tests/helpers/studio_ui_coach.py
register_order(test, _json_of, _chrome)  # 3.1.6.0 R6: the tab order and the keys, tests/helpers/studio_ui_order.py


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio ui tests"))
