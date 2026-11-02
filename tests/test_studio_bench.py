"""tests.test_studio_bench -- Halo 3.3.6.0 R5, Local -> Benchmarks in headless Chrome through
tests/helpers/studio_bench.py (skipped without one), over R1's seeded home (`box` a fake Ollama on 127.0.0.1:0) with two
fixture speed cards and a steward change; no provider request, no model call:

1. the page's three blocks; the speed cards' table: the benched rows, the stale mark ("measured on 0.40.5"), the
   window chips with the spill at the ceiling, the GPU window beside the planner's;
2. the tuning report for box: its lines, Halo-side and server-side options, a server line and its revert;
3. a Halo-side option applied with the scope "until halo exits": its change listed with that scope, the profile
   written; Revert: the line says what it put back and the profile is as it was; the steward's change with its scope;
   Settings -> Local lists the changes too;
4. 3.3.8.1: box as another machine's host with no halo host on it: Bench's confirm carries the link's tail, the via
   and the offer; the run's row carries the over-the-LAN chip with the link.
Run: python -m tests.test_studio_bench
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.driver_got import got as driver_got  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    info = driver_got(ctx, "tests.helpers.studio_bench", why="the Benchmarks checks need headless Chrome",
                      cache=_RUN, timeout=480)
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


@test
def test_a_bench_over_the_lan(ctx: Ctx):
    got = _got(ctx)
    cost, via, offer = (got.get("lan_confirm") or ["", "", ""])[:3]
    ctx.check(f"the confirm: the cost line with the link's tail, the via, the offer, got {got.get('lan_confirm')}",
              cost.endswith("measured over the LAN from mac: includes the link (RTT 1.8 ms, wired)")
              and via == "over the LAN from mac" and offer.startswith("a card without the link: `halo host serve` on 127.0.0.1")
              and "`halo host join 127.0.0.1` here" in offer)
    chip, title = (got.get("lan_row") or ["", ""])[:2]
    ctx.check(f"the row's chip names where and the link, its title the card's first line, got {got.get('lan_row')}",
              chip == "over the LAN from mac · RTT 1.8 ms, wired"
              and title == "measured over the LAN from mac: includes the link (RTT 1.8 ms, wired)")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
