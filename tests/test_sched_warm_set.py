"""tests.test_sched_warm_set -- Halo 3.3.7.0 R3: the warm set (local_sched/warm_set.py) and the switch cost
(local_sched/swap_cost.py), over tests/helpers/sched_rig.SchedHome (a fake Ollama on 127.0.0.1:0 for /api/ps, the
fixture card and catalog through ollama_hosts_view.READERS):

1. the brief's shape: the coder and a 1.5 B helper co-reside on a 21.5 GB card, any 27 B means a pivot; one pass
   of the lineup (main, each lane, back to main) swaps twice, the seconds from the weights, the line says it all;
2. the duty steward's helper, resident in /api/ps, is subtracted from the card (R2's invariant) and named;
3. a lineup's own `warm:` list goes first; a lane with no catalog row (or no card read) is not judged;
4. verify and worker on one model: 0 swaps; the eviction keeps the model used next (one pass, fewest loads);
5. load_s: the ledger's median first, the speed card second, the weights third -- each source named;
6. lanes_of: `ol:` lanes only, main first, `{model, effort}` values read.
Run: python -m tests.test_sched_warm_set
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.sched_rig import BIG, CODER, SMALL, TINY, SchedHome, ps_row  # noqa: E402

test, TESTS = new_registry()


def _lanes(**table):
    from halo_harness.local_sched.warm_set import lanes_of
    main = table.pop("main", None)
    return lanes_of({k: f"ol:{v}@pc" for k, v in table.items()}, f"ol:{main}@pc" if main else None)


@test
def test_the_coder_and_a_helper_co_reside_a_27b_pivots(ctx: Ctx):
    from halo_harness.local_sched.warm_set import pack
    with SchedHome() as h:
        ws = pack(h.host, _lanes(main=CODER, coder=CODER, small=TINY, reviewer=BIG))
        warm = [m["model"] for m in ws["warm"]]
        ctx.check(f"coder + the 1.5 B helper warm, got {warm}", warm == [CODER, TINY])
        ctx.check(f"the 27 B pivots, got {[m['model'] for m in ws['pivots']]}", [m["model"] for m in ws["pivots"]] == [BIG]
                  and "does not fit beside qwen3-coder:30b, qwen2.5:1.5b" in ws["pivots"][0]["why"])
        ctx.check(f"one pass swaps twice (to the 27 B, back to main), got {ws['swaps']} {ws['loads']}",
                  ws["swaps"] == 2 and ws["loads"] == [BIG, CODER])
        ctx.check(f"the used share under the usable, got {ws['used']} of {ws['usable']}", 0 < ws["used"] <= ws["usable"])
        ctx.check(f"the line, got {ws['line']!r}", ws["line"].startswith(
            "warm on pc: qwen3-coder:30b (main, coder), qwen2.5:1.5b (small) -- 20.8 of 21.5 GB; qwen3.8:27b (reviewer) "
            "pivots; 2 swaps a pass, ~50 s of loading"))
        ctx.check(f"the seconds come from the weights, named, got {ws['pivots'][0]['load_from']}",
                  ws["pivots"][0]["load_from"].startswith("an estimate from the weights"))


@test
def test_the_helpers_footprint_is_subtracted(ctx: Ctx):
    from halo_harness.local_sched.warm_set import pack
    with SchedHome(loaded=[ps_row(SMALL, 2.0)]) as h:
        h.config(**{"host.steward.enabled": True, "host.steward.model": f"ol:{SMALL}@pc"})
        ws = pack(h.host, _lanes(main=CODER, small=TINY))
        ctx.check(f"the helper named with its GB, got {ws['helper']}", ws["helper"] == {"model": SMALL,
                                                                                        "bytes": 2 * 2 ** 30})
        ctx.check(f"usable = budget - the helper, got {ws['usable']} {ws['budget']}",
                  ws["usable"] == ws["budget"] - 2 * 2 ** 30)
        ctx.check(f"with 2 GB held the coder alone is warm, the 1.5 B pivots, got {ws['line']!r}",
                  [m["model"] for m in ws["warm"]] == [CODER] and [m["model"] for m in ws["pivots"]] == [TINY]
                  and "(the helper qwen3.5:9b holds 2.0 GB)" in ws["line"])


@test
def test_a_declared_warm_list_goes_first_and_unknown_is_said(ctx: Ctx):
    from halo_harness.local_sched.warm_set import pack
    with SchedHome() as h:
        ws = pack(h.host, _lanes(main=CODER, reviewer=BIG), declared=[BIG])
        ctx.check(f"the declared 27 B is warm, the coder pivots, got {ws['line']!r}",
                  [m["model"] for m in ws["warm"]] == [BIG] and [m["model"] for m in ws["pivots"]] == [CODER])
        ws = pack(h.host, _lanes(main=CODER, small="nosuch:7b"))
        ctx.check(f"no catalog row: not judged, said, got {ws['unknown']}", [m["model"] for m in ws["unknown"]]
                  == ["nosuch:7b"] and "no catalog row" in ws["unknown"][0]["why"])
        ws = pack(h.host, _lanes(main=CODER), card={})
        ctx.check(f"no card read: not judged, got {ws['line']!r}", ws["line"].startswith("warm on pc: not judged")
                  and "no card read" in ws["line"])


@test
def test_shared_weights_and_the_eviction_order(ctx: Ctx):
    from halo_harness.local_sched.warm_set import pack, sequence
    with SchedHome() as h:
        ws = pack(h.host, _lanes(main=CODER, worker=CODER, verify=CODER))
        ctx.check(f"verify and worker on main's weights: 0 swaps, got {ws['swaps']} {ws['line']!r}",
                  ws["swaps"] == 0 and ws["line"].endswith("no swaps a pass"))
        lanes = _lanes(worker=CODER, verify=BIG)
        ctx.check(f"no local main: the lanes in order, got {sequence(lanes)}", sequence(lanes) == [CODER, BIG])
        ws = pack(h.host, _lanes(main=TINY, worker=CODER, verify=BIG))
        ctx.check(f"main + worker warm; in the steady state the coder comes back and the 27 B evicts it again, main "
                  f"stays (the 1.5 B fits beside either): two loads a pass, got {ws['loads']}", ws["loads"] == [CODER, BIG])


@test
def test_load_s_sources_in_order(ctx: Ctx):
    from halo_harness.local_sched.swap_cost import load_s_for, words
    with SchedHome() as h:
        got = load_s_for(h.host, CODER, row={"size": 18554258719})
        ctx.check(f"the weights third, said, got {got}", got["source"].startswith("an estimate from the weights (18.6 GB")
                  and got["s"] == 26.5)
        from halo_harness.providers.local_bench_runs import save
        save(h.state, {"model": CODER, "host": "pc", "digest": "sha256:c0de", "cold_load_s": 21.0, "windows": [], "at": 1})
        got = load_s_for(h.host, CODER)
        ctx.check(f"the speed card second, got {got}", got["s"] == 21.0 and got["source"] == "the speed card (the bench)")
        h.loads(CODER, 30.0, 24.0, 25.0, 1.0)
        got = load_s_for(h.host, CODER)
        ctx.check(f"the ledger first: the median of the loads over 2 s, got {got}", got["s"] == 25.0
                  and got["source"] == "the ledger" and got["n"] == 3 and got["line"] == "~25 s to load (the ledger, 3 loads)")
        ctx.check("model_switch's phrase", words({"load_s": 25.0, "load_source": "the ledger"})
                  == " · ~25 s to load when cold (the ledger)")
        ctx.check("unknown when nothing says", load_s_for(h.host, "nosuch:1b", fetch=False)["s"] is None)


@test
def test_lanes_of_reads_ol_lanes_main_first(ctx: Ctx):
    from halo_harness.local_sched.warm_set import lanes_of
    with SchedHome():
        got = lanes_of({"coder": {"model": f"ol:{CODER}@pc", "effort": "high"}, "small": "or:x/y", "judge": f"ol:{TINY}"},
                       f"ol:{BIG}@pc")
        ctx.check(f"main first, the cloud lane left out, the bare host is the default, got {got}",
                  [(x["lane"], x["model"], x["host"]) for x in got]
                  == [("main", BIG, "pc"), ("coder", CODER, "pc"), ("judge", TINY, "pc")])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
