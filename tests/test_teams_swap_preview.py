"""tests.test_teams_swap_preview -- Halo 3.3.7.0 R3: the switch cost in the plan and the lineup's swap preview
(local_sched/preview.py, `halo teams use`, model_switch.plan's `load_s`), over tests/helpers/sched_rig.SchedHome:

1. `halo teams use` prints the swap preview under the roles: the warm set per card, "this lineup swaps 2x on one
   card ~ ... of loading a pass", and the hygiene lines (verify and worker on different weights that do not
   co-reside; a lane that never fits beside main);
2. verify and worker on one model: "share weights ...: 0 swaps between them"; all co-reside: "0 swaps a pass";
3. a declared `warm:` that cannot co-reside is one line; a lineup with no local lanes prints nothing extra;
4. model_switch.plan carries `load_s` / `load_source` and its line says "~25 s to load when cold (the ledger)".
Run: python -m tests.test_teams_swap_preview
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.sched_lineup import write  # noqa: E402
from tests.helpers.sched_rig import BIG, CODER, SMALL, TINY, SchedHome  # noqa: E402

test, TESTS = new_registry()


def _use(name: str) -> "tuple[int, str]":
    from halo_harness.teams_cli import _cmd_use
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        rc = _cmd_use([name])
    return rc, out.getvalue()


@test
def test_teams_use_prints_the_swap_preview_and_the_hygiene(ctx: Ctx):
    with SchedHome() as h:
        h.config(model=f"ol:{TINY}@pc")
        write(h.state, "loc", {"worker": f"ol:{CODER}@pc", "verify": f"ol:{BIG}@pc"})
        rc, text = _use("loc")
        ctx.check(f"applied, the preview under the roles, got {rc} {text!r}", rc == 0
                  and "Local models (the swap preview, one pass of the lineup):" in text)
        ctx.check("the warm-set line", "  warm on pc: qwen2.5:1.5b (main), qwen3-coder:30b (worker) -- " in text
                  and "qwen3.8:27b (verify) pivots; 2 swaps a pass" in text)
        ctx.check("the total", "  this lineup swaps 2x on one card ~ " in text and "of loading a pass" in text)
        ctx.check("verify and worker on weights that do not co-reside", "[!] verify (qwen3.8:27b) and worker "
                  "(qwen3-coder:30b) run on different weights that do not co-reside on pc: each hand-off between them "
                  "is a swap" in text)
        ctx.check("a lane that never fits beside main", "[!] verify (qwen3.8:27b) never fits beside main "
                  "(qwen2.5:1.5b) on pc: does not fit beside" in text)


@test
def test_shared_weights_and_co_residing_lanes(ctx: Ctx):
    from halo_harness.local_sched.preview import preview
    with SchedHome() as h:
        h.config(model=f"ol:{CODER}@pc")
        write(h.state, "same", {"worker": f"ol:{CODER}@pc", "verify": f"ol:{CODER}@pc"})
        pv = preview("same")
        ctx.check(f"0 swaps a pass, got {pv['lines']}", pv["swaps"] == 0
                  and pv["lines"][-1] == "this lineup's local models co-reside: 0 swaps a pass")
        ctx.check(f"share weights, got {pv['hygiene']}",
                  "verify and worker share weights (qwen3-coder:30b): 0 swaps between them" in pv["hygiene"])
        write(h.state, "two", {"worker": f"ol:{TINY}@pc", "verify": f"ol:{CODER}@pc"})
        pv = preview("two", main_ref=f"ol:{TINY}@pc")
        ctx.check(f"different weights, both warm: no swap between them, got {pv['hygiene']}", any(
            "run on different weights, both warm on pc: no swap between them" in x for x in pv["hygiene"]))


@test
def test_a_declared_warm_list_that_cannot_co_reside_and_no_local_lanes(ctx: Ctx):
    from halo_harness.local_sched.preview import preview
    with SchedHome() as h:
        h.config(model=f"ol:{CODER}@pc")
        write(h.state, "both", {"reviewer": f"ol:{BIG}@pc"}, warm=[CODER, "reviewer"])
        pv = preview("both")
        ctx.check(f"the declared set cannot co-reside: one line, got {pv['hygiene']}", any(
            x.startswith("warm: declares qwen3-coder:30b, qwen3.8:27b; they cannot co-reside on pc: qwen3.8:27b does "
                         "not fit beside") for x in pv["hygiene"]))
        write(h.state, "lf", {"small": f"ol:{SMALL}@pc", "judge": f"ol:{SMALL}@pc"})
        pv = preview("lf", main_ref=f"ol:{BIG}@pc")
        ctx.check(f"the VRAM-aware four run on main's model: packed as they run, said, got {pv['lines']} {pv['hygiene']}",
                  pv["swaps"] == 0 and any(x.startswith("judge, small (qwen3.5:9b) do not fit beside main (qwen3.8:27b) "
                                                        "on pc: they run on main's model instead") for x in pv["hygiene"]))
        h.config(model="or:some/cloud")
        rc, text = _use("standard")
        ctx.check(f"no local lanes: nothing extra, got {text!r}", rc == 0 and "swap preview" not in text)


@test
def test_the_switch_plan_carries_the_load(ctx: Ctx):
    from halo_harness.agent.model_switch import line_for, plan
    from halo_harness.model import parse_model_ref
    from types import SimpleNamespace
    with SchedHome() as h:
        h.loads(SMALL, 25.0, 26.0, 24.0)
        s = SimpleNamespace(state_dir=h.state, model_ref=parse_model_ref(f"ol:{CODER}@pc"), settings=None,
                            log=None, effort=None, effort_source=None)
        import halo_harness.agent.model_switch as M
        saved = M.history
        M.history = lambda _s: ("system", [{"role": "user", "content": "hi"}], [])
        try:
            r = plan(s, parse_model_ref(f"ol:{SMALL}@pc"), catalog_row={"size": 6600000000}, profile={},
                     tools_probe=True)
        finally:
            M.history = saved
        ctx.check(f"load_s and its source on the report, got {r.get('load_s')} {r.get('load_source')}",
                  r["load_s"] == 25.0 and r["load_source"] == "the ledger")
        ctx.check(f"the line says it, got {r['line']!r}", " · ~25 s to load when cold (the ledger)" in r["line"])
        r2 = dict(r, load_s=None)
        ctx.check("no load known: nothing said", "to load" not in line_for(r2))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
