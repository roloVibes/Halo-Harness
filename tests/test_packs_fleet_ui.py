"""tests.test_packs_fleet_ui -- the packs' fleet capabilities in Studio (Halo
3.2.0.0 R4). Headless Chrome through the driver base
(tests/helpers/studio_packs_fleet.py; skipped without one), over a fresh home
with doc-review (bash granted, a model that calls tools) and fleet-needs-gpu:

1. Fleet's Capabilities card has a "packs" line: docs.review available (the
   model and the grant), gpu.render not available (no GPU here); the chips
   count the available one;
2. the Mission panel's plan names the part's pack need with the harness that
   has it, the head shows the mission's metadata (it was started with the
   pack's lineup), and the selected part shows the pack's inspector line,
   read through the pack's file route.

Run: python -m tests.test_packs_fleet_ui
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
        raise SkipTest("no Chrome found (the Studio fleet-capabilities checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_packs_fleet"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=400, env=driver_env(REPO), cwd=str(REPO), stdin=subprocess.DEVNULL)
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
def test_the_capabilities_card_lists_the_packs_capabilities(ctx: Ctx):
    got = _got(ctx)
    rows = got.get("caps_packs") or []
    ctx.check(f"a packs line on the card, got {got.get('caps_label')}", got.get("caps_label") == ["packs"])
    ctx.check(f"docs.review: available, the model and the grant, got {rows}", bool(rows) and rows[0] ==
              ["docs.review", "yes", "available: tools: or:anthropic/claude-sonnet-4.6; bash granted"])
    ctx.check("gpu.render: not available, no GPU here", len(rows) > 1 and rows[1] == ["gpu.render", "no", "not available: no GPU here"])
    ctx.check(f"the chips count the available one, got {got.get('caps_chips')}", "+1 pack cap" in (got.get("caps_chips") or []))


@test
def test_the_mission_plan_shows_the_pack_need_metadata_and_inspector(ctx: Ctx):
    got = _got(ctx)
    on = got.get("planned_on") or "?"
    ctx.check(f"the part's need names its pack and harness, got {got.get('need_chip')!r}",
              got.get("need_chip") == f"docs.review · pack doc-review on {on}" and got.get("need_pack") == "doc-review")
    ctx.check(f"the head: the pack's mission metadata, got {got.get('metadata')!r}", got.get("metadata") == "pack doc-review · review=docs · style=short")
    ctx.check("no inspector before a part is selected", got.get("inspector_before") is False)
    ctx.check(f"selected: the pack's inspector line, got {got.get('inspector_label')!r}", got.get("inspector_label") == "Review checklist")
    ctx.check(f"its file read through the pack's route, got {str(got.get('inspector_text'))[:80]!r}",
              "Every link in a changed document resolves." in str(got.get("inspector_text")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
