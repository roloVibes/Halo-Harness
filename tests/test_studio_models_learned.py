"""tests.test_studio_models_learned -- Auto learns, in Studio (Halo 3.1.9.0
R3): headless Chrome through the driver base (tests/helpers/
studio_models_learned.py; skipped without one), over the fleet rig with the
default `auto` lineup in use, R1's fixture catalog and the seeded outcomes
fixture learn-roster.jsonl:

1. the pill: a live coder the real pick moved off or:v/ears (code 1/4) onto
   or:v/eyes -- its card's pill on hover, the Inspector's Live tab line and
   the Session Live spawn line all say "(learned: code 1/4 on or:v/ears, so
   or:v/eyes instead)";
2. the chips: the picker table's rows carry "learned" chips per task kind,
   the rate and n ("code 1/4"), muted under 3 tasks, struck when dropped,
   the numbers on hover;
3. the strike: "learned for code" strikes or:v/ears' row and no other,
   "learned for plan" or:v/cheap's, "any kind" none.
Run: python -m tests.test_studio_models_learned
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
WORDS = "(learned: code 1/4 on or:v/ears, so or:v/eyes instead)"


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Studio learned checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_models_learned"], capture_output=True,
                           encoding="utf-8", errors="replace", timeout=500, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"] = (r, info)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-500:]!r}", r.returncode == 0 and "failed" not in info)
    return info


@test
def test_the_pill_the_live_tab_and_the_spawn_line_say_what_was_learned(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the real pick over the seeded outcomes moved the choice, got {got.get('picked')!r} {got.get('reason')!r}",
              got.get("picked") == "or:v/eyes" and str(got.get("reason")).endswith(WORDS))
    text, title = (got.get("pill") or ["", ""])[:2]
    ctx.check(f"the pill names the picked model, the learned words on hover, got {got.get('pill')!r}",
              text == "eyes" and title.startswith("auto: or:v/eyes -- ") and title.endswith(WORDS))
    ctx.check(f"the Live tab line, got {got.get('live_tab')!r}", WORDS in str(got.get("live_tab")))
    ctx.check(f"the Session Live spawn line, got {got.get('spawn_line')!r}",
              "on or:v/eyes" in str(got.get("spawn_line")) and WORDS in str(got.get("spawn_line")))


@test
def test_the_picker_shows_learned_chips(ctx: Ctx):
    got = _got(ctx)
    chips = {ref: {t: (dropped, counted, deco, title) for t, dropped, counted, deco, title in items}
             for ref, items in got.get("chips") or []}
    ctx.check(f"the table lists the catalog, got {got.get('rows')}", (got.get("rows") or 0) >= 10)
    ears = chips.get("or:v/ears", {}).get("code 1/4")
    ctx.check(f"or:v/ears: code 1/4, dropped and struck, got {ears}", ears and ears[0] and ears[1] and "line-through" in ears[2])
    ctx.check("its hover says the numbers and the weight",
              ears and "1/4 checked tasks passed first time (the last 30 days)" in ears[3] and "weighs it 0.625" in ears[3])
    eyes = chips.get("or:v/eyes", {}).get("code 4/4")
    ctx.check(f"or:v/eyes: code 4/4, counted, not struck, got {eyes}", eyes and not eyes[0] and eyes[1] and "line-through" not in eyes[2])
    cheap = chips.get("or:v/cheap", {})
    ctx.check(f"or:v/cheap: code 2/2 muted (too few), plan 1/3 struck, got {cheap}",
              cheap.get("code 2/2") and not cheap["code 2/2"][1] and "too few" in cheap["code 2/2"][3]
              and cheap.get("plan 1/3") and cheap["plan 1/3"][0])
    ctx.check(f"a model nothing was learned for has no chip, got {sorted(chips)}", "or:v/painter" not in chips)
    ctx.check(f"the learned-for select lists the kinds, got {got.get('kinds')}",
              [v for v, _t in got.get("kinds") or []] == ["", "code", "media", "plan", "research"])


@test
def test_learned_for_a_kind_strikes_the_dropped(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"any kind: no row struck, got {got.get('struck_any')}", got.get("struck_any") == [])
    ctx.check(f"code: or:v/ears and only it, its ref struck through, got {got.get('struck_code')}",
              got.get("struck_code") == [["or:v/ears", "line-through"]])
    ctx.check(f"the struck row says why on hover, got {got.get('ears_title')!r}",
              got.get("ears_title") == "or:v/ears: dropped for code (1/4 checked tasks)")
    ctx.check(f"a kind narrows the chips to it, got {got.get('code_chips')}", got.get("code_chips") == 1)
    ctx.check(f"plan: or:v/cheap, got {got.get('struck_plan')}", got.get("struck_plan") == [["or:v/cheap", "line-through"]])
    ctx.check(f"back to any kind: none, got {got.get('struck_none')}", got.get("struck_none") == [])
    ctx.check("no dialog opened on the way", got.get("dialogs") == 0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
