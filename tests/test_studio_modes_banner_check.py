"""tests.test_studio_modes_banner_check -- `tools/studio_modes_banner.py --check` asks what matters (Halo 3.4.1.0 R6).

The check compared pixel bytes; CI got Pillow 13.0.0 (the replay clip's encode) and the committed banner, rendered with
Pillow 10.2.0, came out 42 of 1.79 M pixels apart, by 4 levels at most (the labels' text). It now asks for the same
size and the same pixels within TOLERANCE levels on at most MAX_SHARE of them (`matches`), so:

1. the committed banner matches what the captures render here, whatever Pillow;
2. the same banner a few levels off on a few pixels (another Pillow) still matches;
3. a banner built from another capture (one tile swapped) or with two tiles in each other's place is stale;
4. a banner of another size is stale.
Skipped without Pillow (an optional extra). Run: python -m tests.test_studio_modes_banner_check
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _tool():
    try:
        import studio_modes_banner as B
    except ModuleNotFoundError as e:
        raise SkipTest(f"the banner tool needs {e.name} (pip install Pillow)")
    return B


def _built_with(B, frames) -> "object":
    keep = B.FRAMES
    B.FRAMES = frames
    try:
        return B.build()
    finally:
        B.FRAMES = keep


@test
def test_the_committed_banner_matches_and_another_pillow_still_does(ctx: Ctx):
    B = _tool()
    from PIL import Image
    fresh, current = B.build(), Image.open(B.OUT)
    ok, why = B.matches(fresh, current)
    ctx.check(f"the committed banner is what the captures render here: {why}", ok)
    nudged = fresh.copy()
    px = nudged.load()
    for i in range(60):  # 60 pixels of a label, 4 levels off: what Pillow 10.2 and 13.0 differ by
        x, y = 273 + i * 40, 92
        r, g, b = px[x, y]
        px[x, y] = (min(255, r + 4), g, max(0, b - 4))
    ok, why = B.matches(nudged, current)
    ctx.check(f"a few pixels a few levels off (another Pillow) still match: {why}", ok)


@test
def test_other_captures_or_another_order_are_stale(ctx: Ctx):
    B = _tool()
    from PIL import Image
    current = Image.open(B.OUT)
    swapped = (B.FRAMES[1][:1] + B.FRAMES[0][1:],) + B.FRAMES[1:]  # tile 1 drawn from tile 2's capture
    ok, why = B.matches(_built_with(B, swapped), current)
    ctx.check(f"one capture swapped: stale ({why})", not ok)
    order = (B.FRAMES[3],) + B.FRAMES[1:3] + (B.FRAMES[0],) + B.FRAMES[4:]  # tiles 1 and 4 in each other's place
    ok, why = B.matches(_built_with(B, order), current)
    ctx.check(f"two tiles in each other's place: stale ({why})", not ok)
    ok, why = B.matches(current.crop((0, 0, current.width - 2, current.height)), current)
    ctx.check(f"another size: stale ({why})", not ok and "size" in why)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio modes banner check"))
