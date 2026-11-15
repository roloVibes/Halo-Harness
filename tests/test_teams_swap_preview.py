"""tests.test_teams_swap_preview -- Halo 3.3.7.0 R3: the switch cost in the plan and the lineup's swap preview
(local_sched/preview.py, `halo teams use`, model_switch.plan's `load_s`), over tests/helpers/sched_rig.SchedHome:

1. `halo teams use` prints the swap preview under the roles: the warm set per card, "this map swaps 2x on one
   card ~ ... of loading a pass", and the hygiene lines (verify and worker on different weights that do not
   co-reside; a lane that never fits beside main);
2. verify and worker on one model: "share weights ...: 0 swaps between them"; all co-reside: "0 swaps a pass";
3. a declared `warm:` that cannot co-reside is one line; a lineup with no local lanes prints nothing extra;
4. model_switch.plan carries `load_s` / `load_source` and its line says "~25 s to load when cold (the ledger)".
(3.6.0.0 R5: 1 and 3 went with `halo teams use`; the preview itself, local_sched/preview.py, stays for R5b.)
Run: python -m tests.test_teams_swap_preview
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.sched_lineup import write  # noqa: E402
from tests.helpers.sched_rig import CODER, SMALL, TINY, SchedHome  # noqa: E402

test, TESTS = new_registry()


@test
def test_shared_weights_and_co_residing_lanes(ctx: Ctx):
    from halo_harness.local_sched.preview import preview
    with SchedHome() as h:
        h.config(model=f"ol:{CODER}@pc")
        write(h.state, "same", {"worker": f"ol:{CODER}@pc", "verify": f"ol:{CODER}@pc"})
        pv = preview("same")
        ctx.check(f"0 swaps a pass, got {pv['lines']}", pv["swaps"] == 0
                  and pv["lines"][-1] == "this map's local models co-reside: 0 swaps a pass")
        ctx.check(f"share weights, got {pv['hygiene']}",
                  "verify and worker share weights (qwen3-coder:30b): 0 swaps between them" in pv["hygiene"])
        write(h.state, "two", {"worker": f"ol:{TINY}@pc", "verify": f"ol:{CODER}@pc"})
        pv = preview("two", main_ref=f"ol:{TINY}@pc")
        ctx.check(f"different weights, both warm: no swap between them, got {pv['hygiene']}", any(
            "run on different weights, both warm on pc: no swap between them" in x for x in pv["hygiene"]))


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
