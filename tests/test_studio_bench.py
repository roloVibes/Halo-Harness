"""tests.test_studio_bench -- Halo 3.3.6.0 R5, Local -> Benchmarks in headless Chrome through
tests/helpers/studio_bench.py (skipped without one), over R1's seeded home (`box` a fake Ollama on 127.0.0.1:0) with two
fixture speed cards and a steward change; no provider request, no model call:

1. the page's three blocks; the speed cards' table: the benched rows, the stale mark ("measured on 0.40.5"), the
   window chips with the spill at the ceiling, the GPU window beside the planner's;
2. the tuning report for box: its lines, Halo-side and server-side options, a server line and its revert;
3. a Halo-side option applied with the scope "until halo exits": its change listed with that scope, the profile
   written; Revert: the line says what it put back and the profile is as it was; the steward's change with its scope;
   Settings -> Local lists the changes too.
Run: python -m tests.test_studio_bench
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


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Benchmarks checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_bench"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=480, env=driver_env(REPO), cwd=str(REPO), stdin=subprocess.DEVNULL)
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"] = (r, info)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-800:]!r}", r.returncode == 0 and "failed" not in info)
    return info


@test
def test_the_table_and_the_stale_mark(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"three blocks, got {got.get('blocks')}", got.get("blocks") == ["cards", "tune", "changes"])
    rows = {m: (b, s) for m, b, s in got.get("rows") or []}
    ctx.check(f"the benched rows and the stale one, got {rows}", rows.get("qwen3.5:9b") == (True, "")
              and rows.get("qwen3-coder:30b") == (True, "measured on 0.40.5") and rows.get("nomic-embed-text") == (False, ""))
    ctx.check(f"the stale chip, got {got.get('stale')!r}", got.get("stale") == "measured on 0.40.5")
    ctx.check(f"the window chips, the spill at the ceiling, got {got.get('windows')}",
              [w[1] for w in got.get("windows") or []] == ["true", "true", "false"] and "(spills)" in got["windows"][-1][0])
    ctx.check(f"the GPU window beside the planner's, got {got.get('gpu')!r}", got.get("gpu") == "32k (plan 120k)")


@test
def test_the_tuning_report(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the report's says and model lines, got {got.get('says')!r} {got.get('models')}",
              "stay warm together on box" in str(got.get("says")) and any(" alone " in m for m in got.get("models") or []))
    ctx.check(f"Halo-side and server-side options, got {got.get('kinds')}", {"halo", "server"} <= set(got.get("kinds") or []))
    ctx.check(f"a server line and its revert, got {got.get('server_line')!r} {got.get('server_revert')!r}",
              got.get("server_line") and got.get("server_revert"))


@test
def test_a_scoped_change_and_its_revert(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"applied with its scope, got {got.get('applied')!r}", str(got.get("applied")).endswith("(undone when this halo exits)"))
    ctx.check(f"listed with that scope, got {got.get('change')}", (got.get("change") or [""])[0] == "until-restart"
              and "(by user, until-restart" in got["change"][1])
    ctx.check(f"the profile written, got {got.get('written')}", len(got.get("written") or {}) == 1)
    ctx.check(f"Revert says what it put back, got {got.get('reverted')!r}",
              any(w in str(got.get("reverted")) for w in ("put ", "took ")) and "(reverted from Studio)" in str(got.get("reverted")))
    ctx.check(f"the profile as it was, got {got.get('after')}", not got.get("after"))
    ctx.check(f"the steward's change with its scope, got {got.get('steward')}", got.get("steward") == ["until-restart", "steward"])
    ctx.check(f"Settings -> Local lists them, got {got.get('settings')}", (got.get("settings") or 0) >= 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
