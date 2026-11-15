"""tests.test_tryit_round -- Halo 2.0.6 round 14: "Try it" on a bio and a
lineup smoke run from the forms, COST SHOWN FIRST (the item deferred from
2.0.5 round 2).

The cost line is the contract: it appears BEFORE any call runs, names the
model and its real catalog prices (or says the price is unknown), and
never fakes a $0.00. The smoke call itself rides the proven print-mode
subprocess path (`agents_doctor._default_call`), so credentials and the
whole request pipeline are exercised exactly as a real turn. 3.6.0.0 R5: the
bio view's and the lineup view's tests left with those TUI dialogs.
"""

from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

REPO_DIR = Path(__file__).resolve().parent.parent


@test
def test_the_cost_line_is_honest_in_all_three_shapes(ctx: Ctx):
    from halo_harness.smoke_run import smoke_cost_line
    home = Path(tempfile.mkdtemp(prefix="tryit-"))
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    try:
        catalog = {
            "or:vendor/priced": {"price_in_per_m": 0.60, "price_out_per_m": 2.40},
            "or:vendor/free-ish": {"price_in_per_m": 0, "price_out_per_m": 0},
        }
        (home / ".halo").mkdir(parents=True, exist_ok=True)
        (home / ".halo" / "models.json").write_text(json.dumps(catalog), encoding="utf-8")
        line = smoke_cost_line("or:vendor/priced")
        ctx.check(f"a priced model estimates from its real prices, got {line!r}",
                  "or:vendor/priced" in line and "$0.0011" in line and "0.6/$2.4" in line)
        ctx.check("the estimate names its token basis",
                  "600 in / 300 out" in line)
        unknown = smoke_cost_line("or:vendor/not-in-catalog")
        ctx.check(f"an unpriced model says unknown, got {unknown!r}",
                  "cost unknown" in unknown and "$" not in unknown.split("cost unknown")[0])
        ctx.check("...and never a fake price", "$0.00" not in unknown)
        empty = smoke_cost_line("")
        ctx.check(f"no model picked says so, got {empty!r}", "no model picked" in empty)
        free = smoke_cost_line("or:vendor/free-ish")
        ctx.check(f"a genuinely-free model still computes honestly, got {free!r}",
                  "~$0.0000" in free)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
