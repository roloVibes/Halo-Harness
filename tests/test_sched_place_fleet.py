"""tests.test_sched_place_fleet -- Halo 3.3.8.0 R4 deliverable 4: placement scores and the loading tax for the adviser
(local_sched/place_advice.py; models_library/advise_rules.placement; `halo local advise`, `halo local place`),
fleet-wide candidates, and the re-check when a far card changes. Over tests/helpers/place_rig.PlaceRig (two real halo
hosts on 127.0.0.1:0 and one plain fake Ollama; every address a 192.0.2.x placeholder or 127.0.0.1):

1. the candidates are fleet-wide: a paired host's served card this machine has no ollama.hosts entry for is one;
2. `halo local advise --lineup spread` says what each lane costs to place and points at the cheaper placement (a
   `placement` suggestion with both scores); the scores block under it;
3. the re-check: a far card's residency changes, the lanes it carries are placed again; a lane whose best host moved
   is one stated line, nothing moves (no host_for written).
Run: python -m tests.test_sched_place_fleet
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_sched_place import CODER, SMALL, _lineup  # noqa: E402

test, TESTS = new_registry()


@test
def test_the_candidates_are_fleet_wide(ctx: Ctx):
    from halo_harness.local_sched.place_advice import candidates
    from halo_harness.theme import set_config_value
    from tests.helpers.place_rig import PlaceRig
    with PlaceRig() as rig:
        set_config_value("ollama.hosts", [{"name": "pc", "url": rig.pc_url}, {"name": "box", "url": rig.box_mock.base_url}])
        got = {h.name: h.url for h in candidates(rig.rig.peer)}
        ctx.check(f"samus (no entry here) comes from its paired host's served card, got {got}",
                  got.get("samus") == rig.samus_url and got.get("pc") == rig.pc_url and "box" in got)


@test
def test_advise_says_the_placement_scores(ctx: Ctx):
    from halo_harness.local_advise_cli import cmd_advise
    from halo_harness.models_library.advise import advise
    from tests.helpers.place_rig import PlaceRig
    with PlaceRig() as rig:
        _lineup(rig)
        got = advise(rig.rig.peer, lineup="spread")
        place = [s for s in got["suggestions"] if s["kind"] == "placement"]
        comp = next((s for s in place if s.get("lane") == "compactor"), None)
        ctx.check(f"the compactor: its cost on pc and the cheaper samus, both scores, got {[s['line'] for s in place]}",
                  comp is not None and comp["says"] == f"compactor ({SMALL}) on pc scores 75 (evicts {CODER}, pivots "
                  f"beside {CODER}); samus scores 116 (18 s to load)" and comp["action"]["cli"] == "halo local place --apply"
                  and got["kinds"]["placement"] == len(place))
        ctx.check(f"the scores block, got {got['placement']['lines']}", any(
            x.startswith(f"compactor ({SMALL}): samus 116 (18 s to load) | pc 75") for x in got["placement"]["lines"]))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_advise(["--lineup", "spread"])
        text = out.getvalue()
        ctx.check(f"halo local advise prints both, got {rc} {text!r}", rc == 0 and "[placement] compactor" in text
                  and "placement scores (the chosen host first; halo local place --apply moves a lane):" in text)


@test
def test_a_far_cards_change_is_one_stated_line(ctx: Ctx):
    from halo_harness.local_sched.place_advice import recheck
    from halo_harness.ollama_steward.profiles import all_profiles
    from halo_harness.providers.ollama import OllamaHost
    from tests.helpers.pool_rig import PoolHome
    pc, samus = OllamaHost(name="pc", url="http://192.0.2.10:11434"), OllamaHost(name="samus", url="http://192.0.2.20:11434")
    gib, busy = 2 ** 30, {"samus": False}

    def ask(h, ln):
        fits = not (h.name == "samus" and busy["samus"])
        return {"host": h.name, "via": "host", "fits": fits, "now": fits, "warm": False, "evicts": [], "installed": True,
                "capable": None, "load_s": 30.0 if h.name == "pc" else 4.0, "need_bytes": 8 * gib,
                "usable_bytes": 22 * gib, "verdict": "fits" if fits else "does not fit (a model loaded there)"}
    lanes = [{"lane": "worker", "model": SMALL, "host": "pc"}]
    with PoolHome() as h:
        first = recheck(h.state, now=1000.0, lanes=lanes, hosts=[pc, samus], answers=ask, residency={})
        ctx.check(f"the first look remembers where each lane goes, says nothing, got {first}", first == [])
        busy["samus"] = True
        moved = recheck(h.state, now=1100.0, lanes=lanes, hosts=[pc, samus], answers=ask,
                        residency={"samus": {"qwen3.8:27b": 1090.0}})
        ctx.check(f"samus's card changed: the worker's lane moves, one stated line, got {moved}", len(moved) == 1
                  and moved[0]["say"] == "samus's card changed (qwen3.8:27b loaded or unloaded there): worker would go to "
                                         "pc now (score 115) -- halo local place --apply moves it; nothing moved")
        again = recheck(h.state, now=1200.0, lanes=lanes, hosts=[pc, samus], answers=ask,
                        residency={"samus": {"qwen3.8:27b": 1090.0}})
        ctx.check(f"nothing changed since: no line, got {again}", again == [])
        ctx.check("nothing moved: no host_for written", not any("host_for" in (p or {}) for p in all_profiles().values()))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
