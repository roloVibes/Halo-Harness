"""tests.test_studio_models_ui -- what each model is good at, in Studio (Halo
3.1.9.0 R1). Headless Chrome through the driver base (tests/helpers/
studio_ui_models.py; skipped without one), over a fresh home with the shipped
lineups and a fixture catalog in every provider's cache:

1. the Models panel's Analyze shows the models analyzed, the count per kind
   and each kind's strongest model;
2. the bio form's picker table has a "best at" column: a row's kinds as
   chips and its one honest line, the full line on hover;
3. the "best" sort leads with the model good at the most kinds; a search by
   the line's words finds the rows that say it.
Run: python -m tests.test_studio_models_ui
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
        raise SkipTest("no Chrome found (the Studio models checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_ui_models"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=400, env=driver_env(REPO), cwd=str(REPO))
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
def test_analyze_shows_the_counts_per_kind(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the panel counts the catalog, got {got.get('count')}", isinstance(got.get("count"), (int, float)) and got["count"] >= 10)
    ctx.check(f"Analyze says how many and per kind, got {got.get('analysis')!r}",
              "models analyzed" in str(got.get("analysis")) and "visual" in str(got.get("analysis")))
    ctx.check(f"each kind's strongest model is named, got {got.get('analysis_kinds')}",
              {"visual", "audio", "bulk"} <= set(got.get("analysis_kinds") or []))


@test
def test_the_picker_has_a_best_at_column(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the table lists the catalog, got {got.get('rows')}", (got.get("rows") or 0) >= 10)
    ctx.check(f"the column header says best at, got {got.get('head')!r}", "best at" in str(got.get("head")))
    ctx.check(f"a row's kinds are chips, got {got.get('eyes_kinds')}", "visual" in (got.get("eyes_kinds") or []))
    ctx.check(f"and its one line sits under them, got {got.get('eyes_line')!r}",
              got.get("eyes_line") == "vision+pdf in, tools, reasoning; no audio")
    ctx.check("the full line is on hover", got.get("eyes_title") == got.get("eyes_line"))
    ctx.check("no dialog opened on the way", got.get("dialogs") == 0)


@test
def test_best_sort_and_the_line_search(ctx: Ctx):
    got = _got(ctx)
    first = got.get("best_first") or []
    ctx.check(f"the best sort leads with the most kinds, got {first} (max {got.get('max_chips')})",
              bool(first) and first[0][1] == got.get("max_chips"))
    refs = got.get("pdf_search") or []
    ctx.check(f"a search by the line's words finds the rows that say it, got {refs}", "or:v/eyes" in refs and "or:v/cheap" not in refs)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
