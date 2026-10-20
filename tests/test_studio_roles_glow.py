"""tests.test_studio_roles_glow -- the Roles card glow, explained by the card
and timed, in a real browser (Halo 3.1.5.0 R3, the owner: "more info how
that glow looks and goes"; headless Chrome through the driver base,
tests/helpers/studio_roles_glow.py `glow`; skipped without one).

Over the rig's halo-dev-cycle lineup (one tier, its agents mid-work) plus
extra agents on the verifier and reviewer cards
(tests/helpers/studio_live_rig.py):

1. hovering a working card's state glyph, or its live badge, shows the
   legend: working cyan, waiting amber, done green, failed red, each with
   when it comes and goes, the card's own state marked; it goes when the
   pointer leaves;
2. the glow comes on with the running state (the card and the edges into it
   working); done turns it green and it fades out: ten seconds later the
   card has no glow;
3. failed turns it red and it stays past those ten seconds, until the card
   is clicked (the motion media is pinned to no-preference through CDP, so a
   runner with animations off reads the same; under reduce a done card stays
   green with no fade, the product rule);
4. a one-tier lineup lays its members out as a fan under main (main centred
   over the first row), the tier box wears the HUD brackets;
5. a lineup with no cards invites: "Drag a bio here, or New lineup", in
   brackets, with the New lineup button.
Run: python -m tests.test_studio_roles_glow
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
_RUNS: dict = {}
LEGEND = [["working", "cyan"], ["waiting", "amber"], ["done", "green"], ["failed", "red"]]


def _driver(*argv: str) -> "tuple[subprocess.CompletedProcess, dict]":
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Roles glow needs headless Chrome)")
    if argv not in _RUNS:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_roles_glow", *argv], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=500, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUNS[argv] = (r, info)
    r, info = _RUNS[argv]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    return r, info


def _ran(ctx: Ctx, r, got) -> None:
    ctx.check(f"the driver ran, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in got)


@test
def test_the_legend_on_hovering_the_glow(ctx: Ctx):
    r, got = _driver("glow")
    _ran(ctx, r, got)
    ctx.check(f"the implementer's card glows working, got {got.get('impl_glow')}", got.get("impl_glow") == "working")
    for key in ("legend_glyph", "legend_badge"):
        lg = got.get(key) or [None, []]
        ctx.check(f"{key}: the four states in their colours, got {lg}", [[x[0], x[2]] for x in lg[1]] == LEGEND)
        ctx.check(f"{key}: the card's own state marked, got {lg}", lg[0] == "working" and [x[0] for x in lg[1] if x[1]] == ["working"])
    ctx.check(f"it goes when the pointer leaves, got {got.get('legend_gone')!r}", got.get("legend_gone") == "gone")


@test
def test_done_fades_out_ten_seconds_after(ctx: Ctx):
    r, got = _driver("glow")
    _ran(ctx, r, got)
    ctx.check(f"the glow comes on with the running state, on the card and the edges into it, got {got.get('working')} {got.get('edge_working')}",
              got.get("working") == ["working", "working"] and got.get("edge_working") and set(got["edge_working"]) == {"working"})
    ctx.check(f"done: green, fading, got {got.get('done')}", got.get("done") == ["done", "rc-done-fade"] and got.get("done_mid") == "done")
    ctx.check(f"ten seconds later the card has no glow, got {got.get('done_after')!r}", got.get("done_after") == "off")


@test
def test_under_reduced_motion_done_is_green_with_no_fade(ctx: Ctx):
    r, got = _driver("glow")
    _ran(ctx, r, got)
    rd = got.get("reduced_done") or ["", "", False]
    ctx.check(f"prefers-reduced-motion: reduce: the done card glows green, no fade animation, got {rd}",
              rd[0] == "done" and rd[1] == "none" and rd[2] is True)


@test
def test_failed_stays_until_the_card_is_clicked(ctx: Ctx):
    r, got = _driver("glow")
    _ran(ctx, r, got)
    ctx.check(f"failed: red, got {got.get('red')!r}", got.get("red") == "failed")
    ctx.check(f"still red past ten seconds, got {got.get('failed_after')!r}", got.get("failed_after") == "failed")
    ctx.check(f"a click on the card puts it out, got {got.get('failed_clicked')!r}", got.get("failed_clicked") == "off")


@test
def test_a_one_tier_lineup_fans_out_under_main(ctx: Ctx):
    r, got = _driver("glow")
    _ran(ctx, r, got)
    fan = got.get("fan") or []
    main = next((f for f in fan if f[1] == "main"), None)
    rest = [f for f in fan if f is not main]
    ctx.check(f"one tier box, in brackets, got {got.get('tiers')} {got.get('tier_brackets')}", got.get("tiers") == 1 and got.get("tier_brackets") is True)
    ctx.check(f"main on top, every member below it, got {fan}", main is not None and rest and all(f[3] > main[3] for f in rest))
    first = sorted([f for f in rest if f[3] == min(x[3] for x in rest)], key=lambda f: f[2]) if rest else []
    ctx.check(f"the first row side by side, got {first}", len(first) >= 2 and len({f[2] for f in first}) == len(first))
    if main and first:
        mid = (first[0][2] + first[-1][2]) / 2
        ctx.check(f"main centred over it, got main x {main[2]} row middle {mid}", abs(main[2] - mid) <= 2)


@test
def test_an_empty_lineup_invites(ctx: Ctx):
    r, got = _driver("glow")
    _ran(ctx, r, got)
    ctx.check(f"'Drag a bio here, or New lineup', bracketed, with New lineup, got {got.get('invite')}",
              got.get("invite") == ["Drag a bio here, or New lineup", True, True, True])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
