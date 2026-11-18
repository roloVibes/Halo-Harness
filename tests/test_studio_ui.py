"""tests.test_studio_ui -- Studio in a real browser (headless Chrome; skipped without one).
The shell at / by its data-testid counts (3.6.0.0 R5: the old Orchestra and Roles doors land on Agents -> 3 · Map); a
goal run's report as its own page of the Map's drawer and a planned run on the Map (tools/capture_orchestra.py). Registered here:
3.0.9.0 R2 the plan canvas (studio_ui_plan.py; 3.6.0.0 R5: reached from the Map's line) and the tab order (3.1.6.0 R6:
tests/helpers/studio_ui_order.py reads the tab strip in order). 3.6.0.0 R5: Roles' canvas (studio_ui_roles.py), Live
(studio_ui_live.py) and Cast's panel clicks (studio_clarity.py) went with those views.
"""

from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all
from tests.helpers.studio_ui_order import register as register_order
from tests.helpers.studio_ui_plan import register as register_plan

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
def test_shell_boots_with_its_sections_in_headless_chrome(ctx: Ctx):
    """3.0.3.0: the React shell at / draws the section tabs (six since 3.3.16.0 R2); 3.6.0.0 R5: the old Orchestra
    and Roles doors land on Agents -> 3 · Map, no frame."""
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
    # 3.6.0.0 R5: the old Orchestra and Roles doors land on Agents -> 3 · Map: the starter map, Run a goal on its bar
    # (3.6.0.3 B: History's strip under the map left Studio)
    want = {"section-tab": 6, "orchestra-root": 0, "start-view": 0, "legacy-frame": 0, "map": 1, "map-canvas": 1, "map-run-goal": 1, "map-history": 0}
    ctx.check(f"the old Orchestra door: the Map, Run a goal on its bar, no Start view, got {orch}", orch == want)
    ctx.check(f"the old Roles door: the Map too, no frame, got {roles}", roles == want)
    ctx.check("the title names the section", "Halo Studio" in info.get("title", ""))


@test
def test_a_finished_runs_door_opens_its_own_report_page_in_headless_chrome(ctx: Ctx):
    """3.4.0.0 D "the runs fold": over a seeded finished run (the R2 fixture: five lanes, one judged conflict, eight
    checks) its door `?mode=agents&run=<id>` opens the run's report -- every check, every lane and Run it again (no Replay: 3.6.0.3 B)
    -- and nothing finished is on the Map's line; a run waiting for its plan is the Map's line "A goal run is going", the
    plan panel NOT open (nothing opens by itself); the old Orchestra door is the Map (3.6.0.0 R5). 3.6.0.3 B: the report
    is its own drawer page `report:<id>`, titled "Goal run", History's list not open."""
    if not _chrome():
        raise SkipTest("no Chrome found (the run smoke needs headless Chrome)")
    r, info = _json_of(str(REPO / "tools" / "capture_studio.py"), "--mode", "orchestra", "--dom")
    ctx.check(f"the capture tool ran, got {r.stdout[-300:]!r} {r.stderr[-300:]!r}", r.returncode == 0)
    ctx.check(f"the run's report on its own page, got {info}", info.get("run-report-page") == 1 and info.get("history-report") == 1
              and info.get("report-check") == 8 and info.get("report-lane") == 5)
    ctx.check(f"the capture counts only testids Studio still has (3.6.0.3 B), got {sorted(info)}",
              not {"history-page", "live-history-drawer", "history-report-replay", "orchestra-root", "start-view"} & set(info))
    ctx.check(f"the drawer's page is report:<id>, titled 'Goal run', got {info.get('drawer_page')!r} / {info.get('drawer_title')!r}",
              str(info.get("drawer_page")).startswith("report:") and info.get("drawer_title") == "Goal run")
    ctx.check(f"Run it again on it (its Replay left Studio in 3.6.0.3 B), got {info}", info.get("history-report-again") == 1)
    ctx.check(f"nothing finished on the Map's line, got {info}", info.get("map-lit-run") == 0 and info.get("section-tab") == 6)
    plan, old = info.get("plan") or {}, info.get("old_door") or {}
    ctx.check(f"a planned run: the Map says a goal run is going, nothing open, got {plan}", plan.get("map-lit-run") == 1
              and plan.get("run-review") == 0 and plan.get("orchestra-plan") == 0 and plan.get("run-goal-drawer") == 0)
    ctx.check(f"the old Orchestra door: the Map with Run a goal, got {old}", old.get("map") == 1 and old.get("map-run-goal") == 1
              and old.get("history-report") == 0)


register_plan(test, _json_of, _chrome)  # 3.0.9.0 R2: the plan canvas, tests/helpers/studio_ui_plan.py
register_order(test, _json_of, _chrome)  # 3.1.6.0 R6: the tab order and the keys, tests/helpers/studio_ui_order.py


@test
def test_the_order_test_expects_the_key_labels_the_page_draws(ctx: Ctx):
    """join batch 1: Kbd.tsx draws Alt as the option sign (and Mod as the command sign) when the PAGE's
    navigator.platform is a Mac's; the tab-order test expected 'Alt 1' everywhere and went red on macOS. Its
    expectation now comes from the page's platform, the way Kbd.tsx decides, never from the test's own OS."""
    from tests.helpers import studio_ui_order as O
    src = (REPO / "halo_harness" / "studio" / "ui" / "src" / "lib" / "ui" / "Kbd.tsx").read_text(encoding="utf-8")
    ctx.check("Kbd.tsx still decides by navigator.platform matching Mac|iPhone|iPad (else this mirror is stale)",
              "/Mac|iPhone|iPad/.test(navigator.platform" in src)
    for plat in ("Win32", "Linux x86_64", ""):
        ctx.check(f"{plat!r}: Alt 1 .. Alt 6, got {O.expected_goto(plat)}", O.expected_goto(plat) == O.ORDER)
        ctx.check(f"{plat!r}: Mod+K reads Ctrl K", O.kbd_aria("Mod+K", plat) == "Ctrl K")
    for plat in ("MacIntel", "iPad"):
        ctx.check(f"{plat!r}: the option sign, got {O.expected_goto(plat)}",
                  O.expected_goto(plat)[0] == ("Session", "⌥ 1") and O.expected_goto(plat)[-1] == ("Settings", "⌥ 6"))
        ctx.check(f"{plat!r}: Mod+Shift+K reads with the command and shift signs",
                  O.kbd_aria("Mod+Shift+K", plat) == "⌘ ⇧ K")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio ui tests"))
