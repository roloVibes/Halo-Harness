"""tests.test_studio_switch_lists -- Halo 3.3.5.0 R0 (f), (g), (h) in the page.
Headless Chrome through the driver base (tests/helpers/studio_switch_lists.py;
skipped without one), over a seeded home with a stub catalog of 300
OpenRouter rows and a fake Claude Code settings.json naming a Databricks host
(the placeholder) with no token; no provider request, no model call:

1. Setup -> Default model shows all 300 rows and says "300 models"; the
   search still narrows;
2. the Databricks card says where the host came from and never prints it;
3. a Save raises no toast, and the toasts layer sits top right, clear of Next;
4. the Roles picker lists all 300 rows with its count line.
Run: python -m tests.test_studio_switch_lists
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
        raise SkipTest("no Chrome found (these checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_switch_lists"], capture_output=True, encoding="utf-8",
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
def test_setup_default_model_shows_every_model(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"all 300 rows in the page, got {got.get('rows')} ({got.get('refs_unique')} distinct)",
              got.get("rows") == 300 and got.get("refs_unique") == 300)
    ctx.check(f"the count line, got {got.get('count_line')!r}", got.get("count_line") == "300 models")
    ctx.check(f"the search still narrows, got {got.get('searched')}", got.get("searched") == ["or:mock/m007"])


@test
def test_the_card_names_where_the_host_came_from(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the Databricks card's line, got {got.get('dbx_state')!r}",
              got.get("dbx_state") == "host from Claude Code's settings.json · token not set")
    ctx.check("and no host value beside it", got.get("host_in_state") is False)


@test
def test_no_toast_over_next(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"a Save on Setup raises no toast, got {got.get('toasts_after_save')}", got.get("toasts_after_save") == 0)
    ctx.check(f"a toast sits clear of the foot's Next, got overlap={got.get('overlap')}", got.get("overlap") is False)
    ctx.check(f"the toasts layer is at the top, under the header, got {got.get('toast_top')} (header {got.get('topbar')})",
              isinstance(got.get("toast_top"), int) and got["toast_top"] < 200)


@test
def test_the_roles_picker_shows_every_model(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"all 300 rows in the picker, got {got.get('picker_rows')}", got.get("picker_rows") == 300)
    ctx.check(f"its count line, got {got.get('picker_count')!r}", got.get("picker_count") == "300 models")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
