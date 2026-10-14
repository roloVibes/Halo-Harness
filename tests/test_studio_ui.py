"""tests.test_studio_ui -- the Studio page boots in a real browser (Halo
2.1.0 round B3): headless Chrome loads the page over a seeded scratch home,
the lineup draws its node cards, and docs/media/studio.png (the README's
capture) exists and is a PNG. 3.0.3.0: the classic page is the one at
/legacy/, and the React shell at / is checked by its data-testid counts. Skipped when no Chrome is found, like the
front-page PNG step.
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
    ctx.check(f"Orchestra: five section tabs and the console, got {orch}", orch == {"section-tab": 5, "orchestra-root": 1, "legacy-frame": 0})
    ctx.check(f"Roles: five section tabs and the framed classic page, got {roles}", roles == {"section-tab": 5, "orchestra-root": 0, "legacy-frame": 1})
    ctx.check("the title names the section", "Halo Studio" in info.get("title", ""))


@test
def test_orchestra_run_console_draws_a_finished_run_in_headless_chrome(ctx: Ctx):
    """3.0.3.0 R4: over a seeded finished run (the R2 fixture: five lanes, one
    judged conflict, eight checks) the Orchestra section draws the graph with
    its gate, five lanes, five claimed bands, every check and five tiles."""
    if not _chrome():
        raise SkipTest("no Chrome found (the Orchestra smoke needs headless Chrome)")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_"))}
    env["PYTHONPATH"] = str(REPO)
    env["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
    r = subprocess.run([sys.executable, str(REPO / "tools" / "capture_studio.py"), "--mode", "orchestra", "--dom"], capture_output=True, text=True, timeout=240, env=env, cwd=str(REPO))
    ctx.check(f"the capture tool ran, got {r.stdout[-300:]!r} {r.stderr[-300:]!r}", r.returncode == 0)
    try:
        info = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        info = {}
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
def test_readme_capture_exists(ctx: Ctx):
    png = REPO / "docs" / "media" / "studio.png"
    ctx.check("docs/media/studio.png exists", png.is_file())
    if png.is_file():
        ctx.check("it is a PNG under 1 MB", png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and png.stat().st_size < 1024 * 1024)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio ui tests"))
