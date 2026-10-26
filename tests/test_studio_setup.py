"""tests.test_studio_setup -- the Setup section in the page (Halo 3.3.0.0 R1).
Headless Chrome through the driver base (tests/helpers/studio_setup.py;
skipped without one), over a seeded home (the shipped lineups,
halo-dev-cycle active) and a stub catalog of two models; no provider, no
model call:

1. `?mode=setup` opens it, and Alt+8 from Roles: the eighth and last tab;
   the strip names the provider, model, lineup, mode and theme; the four
   later blocks say they come with R2 / R3; the rail lists eight blocks;
2. Permissions: plan picked says "1 changed", Save writes it to
   config.json and the strip follows;
3. Terminal theme: six swatches drawn in their own colours, claude-light saved;
4. Default model: grouped by provider, the search narrows it, saved;
5. Team: balanced with its preview, Apply writes team and roles on; One
   model for everything removes team and turns roles off;
6. a config.json write from outside: the strip follows the frame.
Run: python -m tests.test_studio_setup
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
CORE = ["Session", "Team", "Roles", "Fleet", "Design", "Orchestra", "Packs", "Setup"]


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Setup checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_setup"], capture_output=True, encoding="utf-8",
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
def test_setup_opens_by_mode_and_by_alt_8(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"?mode=setup opens it, got {got.get('mode_section')!r}", str(got.get("mode_section")).startswith("Setup"))
    ctx.check(f"the eight tabs, Setup last, got {got.get('tabs')}", got.get("tabs") == CORE)
    ctx.check(f"Alt+1..8, got {got.get('kbds')}", got.get("kbds") == [f"Alt{n}" for n in range(1, 9)])
    ctx.check(f"Alt+8 from Roles opens it, got {got.get('alt8')!r}", str(got.get("alt8")).startswith("Setup"))
    ctx.check(f"its eight blocks, got {got.get('panels')}", got.get("panels") == [
        "Providers", "Local models", "Linux fixes", "Check", "Default model", "Permissions", "Terminal theme", "Team"])
    ctx.check(f"the rail lists the blocks, got {got.get('rail')}", len(got.get("rail") or []) == 8 and str(got["rail"][2]).startswith("Default model"))


@test
def test_the_strip_says_what_is_set(ctx: Ctx):
    got = _got(ctx)
    want = [["provider", "none"], ["model", "not set"], ["lineup", "halo-dev-cycle"], ["permissions", "not set"], ["theme", "claude-dark (default)"]]
    ctx.check(f"provider, model, lineup, permissions, theme, got {got.get('strip')}", got.get("strip") == want)
    ctx.check("the strip is there on ?mode=setup too", got.get("mode_first_strip") == want)


@test
def test_the_later_blocks_say_when_they_come(ctx: Ctx):
    got = _got(ctx)
    later = dict(got.get("later") or [])
    ctx.check(f"Providers and Local models come with R2, got {later}",
              "comes with R2" in later.get("providers", "") and "comes with R2" in later.get("local", ""))
    ctx.check("Linux fixes and Check come with R3", "comes with R3" in later.get("linux", "") and "comes with R3" in later.get("check", ""))


@test
def test_permissions_save(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the four modes, got {got.get('modes')}", got.get("modes") == ["auto", "acceptEdits", "default", "plan"])
    ctx.check("a pick says 1 changed", got.get("mode_word") == "changed")
    ctx.check(f"Save writes config.json, got {got.get('mode_config')!r}", got.get("mode_config") == "plan")
    ctx.check(f"the strip follows, got {got.get('mode_strip')!r}", got.get("mode_strip") == "plan")
    ctx.check(f"the block shows what was written, got {got.get('mode_lines')!r}", str(got.get("mode_lines")).startswith("permission_mode = plan (saved to "))


@test
def test_terminal_theme_save(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"six swatches, got {got.get('swatches')}", len(got.get("swatches") or []) == 6 and "claude-light-ansi" in got["swatches"])
    ctx.check(f"a swatch is drawn in its theme's colours (claude-light's bg #eff1f5), got {got.get('swatch_bg')!r}",
              got.get("swatch_bg") == "rgb(239, 241, 245)")
    ctx.check("the block says Studio's own switch is a browser setting", "setting of this browser" in str(got.get("theme_note")))
    ctx.check(f"Save writes config.json, got {got.get('theme_config')!r}", got.get("theme_config") == "claude-light" and got.get("theme_strip") == "claude-light")


@test
def test_default_model_save(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"grouped by provider, got {got.get('groups')} {got.get('models')}",
              got.get("groups") == ["openrouter"] and got.get("models") == ["or:mock/alpha", "or:mock/beta"])
    ctx.check(f"the search narrows it by best at, got {got.get('searched')}", got.get("searched") == ["or:mock/beta"])
    ctx.check(f"Save writes config.json, got {got.get('model_config')!r}", got.get("model_config") == "or:mock/beta" and got.get("model_strip") == "or:mock/beta")


@test
def test_team_apply(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"One model first, auto, then the lineups, got {got.get('lineups')}",
              (got.get("lineups") or [])[:2] == ["one-model", "auto"] and "balanced" in got["lineups"])
    ctx.check(f"the seeded lineup is in use, got {got.get('in_use')}", got.get("in_use") == ["halo-dev-cycle"])
    ctx.check(f"the preview of the pick, got {got.get('preview')!r}", str(got.get("preview")).startswith("balanced"))
    ctx.check(f"Apply: team and roles on in config.json, the strip follows, got {got.get('team_config')} {got.get('team_strip')!r}",
              got.get("team_config") == ["balanced", True] and got.get("team_strip") == "balanced")
    ctx.check(f"One model for everything: no team, roles off, got {got.get('one_config')} {got.get('one_strip')!r}",
              got.get("one_config") == [False, False] and got.get("one_strip") == "one model for everything")


@test
def test_a_write_from_outside_shows(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"config.json written outside the page: the strip follows, got {got.get('outside_strip')!r}", got.get("outside_strip") == "acceptEdits")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
