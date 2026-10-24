"""tests.test_studio_roles_auto -- the Auto lineup in Studio (Halo 3.1.9.0
R2): headless Chrome through the driver base (tests/helpers/
studio_roles_auto.py; skipped without one), over the fleet rig with no
`team:` set, so the default `auto` lineup is the one in use:

1. `GET state` says so (`lineup_in_use: auto`, `lineup_default: true`);
   Roles names it and opens its pool (main and seven cards) with the chip
   "active (default)" (the panels, with nothing applied, open on it too; an
   applied lineup's chip says "active");
2. an idle pool card's pill reads `auto` ("picked when it spawns" on hover);
   a live coder's pill names the model it was picked for, with "auto:
   <model> -- <reason>" on hover;
3. the Inspector's Live tab prints the same line;
4. the Session Live column's spawn line carries it ("main spawned media on
   <model>: <reason>");
5. a lineup without auto shows no pick, even for an agent whose row has one.
Run: python -m tests.test_studio_roles_auto
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}
CODER = "auto: or:mock/cheap-coder -- the bio asks for tools, the best tools model within 3x the cheapest ($0.05/$0.20 per 1M)"


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Auto lineup's Studio checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_roles_auto", "auto"], capture_output=True,
                           encoding="utf-8", errors="replace", timeout=500, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"] = (r, info)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in info)
    return info


@test
def test_roles_names_the_default_and_shows_its_pool(ctx: Ctx):
    got = _got(ctx)
    state = got.get("state") or {}
    ctx.check(f"GET state: the default auto lineup, got {state.get('lineup_in_use')!r} {state.get('lineup_default')!r} "
              f"{state.get('active_team')!r}", state.get("lineup_in_use") == "auto" and state.get("lineup_default") is True
              and state.get("active_team") == "")
    start = got.get("start_in_use") or ""
    ctx.check(f"the Start view (when it shows) names it, got {start!r}", not start or "In use now: auto (the default)" in start)
    cards = sorted(got.get("cards") or [])
    ctx.check(f"the canvas shows main and the pool, got {cards}",
              cards == sorted(["default-model", "auto-planner", "auto-researcher", "auto-coder", "auto-reviewer", "auto-media",
                               "auto-writer", "auto-ops"]))
    ctx.check(f"the chip says active (default), got {got.get('chip')}", got.get("chip") == [["active (default)", "1"]])
    ctx.check(f"the panels with nothing applied open on it, got {got.get('workspace_opens')!r}", got.get("workspace_opens") == "auto")
    ctx.check(f"an applied lineup's chip says active, got {got.get('chip_applied')}", got.get("chip_applied") == [["active", ""]])


@test
def test_the_pill_reads_the_pick_with_its_reason(ctx: Ctx):
    got = _got(ctx)
    idle = got.get("idle_pill") or ["", "", ""]
    ctx.check(f"an idle pool card's pill reads auto, picked at spawn on hover, got {idle}",
              idle[0] == "auto" and "picked when it spawns, for its task" in idle[1] and not idle[2])
    live = got.get("live_pill") or ["", "", ""]
    ctx.check(f"a live coder's pill names its picked model, the reason on hover, got {live}",
              live[0] == "cheap-coder" and live[1] == CODER and live[2] == "or:mock/cheap-coder")


@test
def test_the_live_tab_and_the_spawn_line_carry_the_reason(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the Inspector's Live tab prints the line, got {got.get('live_tab')!r}", (got.get("live_tab") or "").strip() == CODER)
    line = got.get("spawn_line") or ""
    ctx.check(f"the Session Live column's spawn line carries the reason, got {line!r}",
              "main spawned media on or:mock/vision-eyes: an image in the task, the cheapest vision model ($0.30/$1.20 per 1M)"
              in line and "Describe shot.png" in line)


@test
def test_a_lineup_without_auto_shows_no_pick(ctx: Ctx):
    got = _got(ctx)
    plain = got.get("plain") or ["", "", -1]
    ctx.check(f"halo-dev-cycle's verifier pill keeps its own model, no card shows a pick, got {plain}",
              plain[2] == 0 and not plain[1].startswith("auto:") and "a reason a pinned card ignores" not in plain[1])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
