"""tests.test_sched_place -- Halo 3.3.7.0 R3 (G12): the placement solver across machines (local_sched/place.py,
`halo local place`), over tests/helpers/place_rig.PlaceRig: two real halo hosts on 127.0.0.1:0 (pc with the coder
warm, samus with a 10 GB card) and one plain fake Ollama this machine reads directly (box):

1. a host-served host answers with its `route` (via "host"), the plain one from the local reads (via "local");
2. the plan: main and the coder stay on pc (warm, shared weights), the compactor goes to samus (it fits there,
   18 s load: it would pivot beside the coder on pc), the 1.5 B helper to box (pulled there, nowhere else);
   one line per lane with the number behind it;
3. `halo local place --apply` writes host_for on each moved lane's `<host>|<model>|<role>` profile and nothing
   else (no pull, no load: the fakes saw no generate);
4. Studio's GET local/place answers the same plan;
5. 3.3.7.0 R5: the claims are an input -- a lane that would not fit beside a reservation goes elsewhere with one
   `routed` line, the reserved model stays where it is held, and with no other room the claim is named.
Run: python -m tests.test_sched_place
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
CODER, SMALL, TINY = "qwen3-coder:30b", "qwen3.5:9b", "qwen2.5:1.5b"


def _lineup(rig) -> None:
    from halo_harness.theme import set_config_value
    from tests.helpers.sched_lineup import write
    set_config_value("model", f"ol:{CODER}@pc")
    write(rig.rig.peer, "spread", {"coder": f"ol:{CODER}@pc", "compactor": f"ol:{SMALL}@pc", "small": f"ol:{TINY}@pc"})


@test
def test_route_answers_and_local_reads(ctx: Ctx):
    from halo_harness.local_sched.facts import host_named
    from halo_harness.local_sched.place import answer
    from tests.helpers.place_rig import PlaceRig
    with PlaceRig() as rig:
        a = answer(host_named("pc"), {"lane": "coder", "model": CODER, "host": "pc"})
        ctx.check(f"pc answers through its halo host: warm, fits, got {a}", a["via"] == "host" and a["warm"] is True
                  and a["fits"] is True and a["usable_bytes"])
        a = answer(host_named("samus"), {"lane": "compactor", "model": SMALL, "host": "pc"})
        ctx.check(f"samus through its host: fits now, the 18 s load from its profile, got {a}", a["via"] == "host"
                  and a["fits"] is True and a["now"] is True and a["load_s"] == 18.0)
        a = answer(host_named("box"), {"lane": "small", "model": TINY, "host": "pc"})
        ctx.check(f"box from the local reads, got {a}", a["via"] == "local" and a["fits"] is True and a["installed"] is True)
        ctx.check(f"nothing left 127.0.0.1, got {rig.rig.blocked}", not rig.rig.blocked)


@test
def test_the_plan_spreads_the_lanes(ctx: Ctx):
    from halo_harness.local_place_cli import place_lineup
    from tests.helpers.place_rig import PlaceRig
    with PlaceRig() as rig:
        _lineup(rig)
        plan = place_lineup("spread")
        where = {r["lane"]: r["host"] for r in plan["rows"]}
        ctx.check(f"main and the coder on pc, the compactor on samus, the helper on box, got {where} {plan['line']}",
                  where == {"main": "pc", "coder": "pc", "compactor": "samus", "small": "box"})
        rows = {r["lane"]: r for r in plan["rows"]}
        ctx.check(f"the coder's row says warm and shared weights, got {rows['coder']['why']}",
                  "warm" in rows["coder"]["why"] and "shares weights" in rows["coder"]["why"])
        ctx.check(f"the compactor's row says the 18 s load, got {rows['compactor']['why']}",
                  rows["compactor"]["why"].startswith("fits") and "18 s load" in rows["compactor"]["why"]
                  and rows["compactor"]["moved"] is True)
        ctx.check(f"the line, got {plan['line']!r}", plan["line"].startswith("main on pc (fits, warm")
                  and "compactor on samus (fits, fits now, 18 s load)" in plan["line"])


@test
def test_apply_writes_host_for_only(ctx: Ctx):
    from halo_harness.local_place_cli import cmd_place
    from halo_harness.ollama_steward.profiles import all_profiles, lookup
    from tests.helpers.place_rig import PlaceRig
    with PlaceRig() as rig:
        _lineup(rig)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_place(["spread", "--apply"])
        text = out.getvalue()
        ctx.check(f"the plan and what it wrote, got {rc} {text!r}", rc == 0 and text.startswith("halo local place spread: ")
                  and "  compactor: qwen3.5:9b on samus (score 116) -- " in text and "wrote: host_for" in text
                  and "    scores: samus 116 (18 s to load) | pc 75 (evicts qwen3-coder:30b, pivots beside qwen3-coder:30b)"
                  in text)  # 3.3.8.0 R4: every candidate's score and its loading tax
        prof = all_profiles()
        ctx.check(f"host_for on each moved lane's key, got {prof}", prof.get(f"pc|{SMALL}|compactor", {}).get("host_for")
                  == "samus" and prof.get(f"pc|{TINY}|small", {}).get("host_for") == "box"
                  and not any(k.startswith(f"pc|{CODER}") for k in prof))
        ctx.check("the lane reads it", (lookup("pc", SMALL, role="compactor") or {}).get("host_for") == "samus"
                  and not (lookup("pc", SMALL) or {}).get("host_for"))
        ctx.check(f"nothing pulled or loaded, got {rig.samus_mock.generated} {rig.box_mock.generated}",
                  not rig.samus_mock.generated and not rig.box_mock.generated and not rig.pc_mock.generated)


@test
def test_studio_place(ctx: Ctx):
    from halo_harness.studio.api import Request, dispatch
    from tests.helpers.place_rig import PlaceRig
    with PlaceRig() as rig:
        _lineup(rig)
        code, got = dispatch(Request(method="GET", path="local/place", query={"lineup": "spread"}, body={},
                                     cwd=Path(rig.rig.root_p), state_dir=rig.rig.peer, server=None))
        ctx.check(f"GET local/place, got {code} {got.get('line')}", code == 200 and got["local"]
                  and {r["lane"]: r["host"] for r in got["rows"]}["compactor"] == "samus")


@test
def test_lanes_route_around_a_reservation(ctx: Ctx):
    """3.3.7.0 R5 (L4): `solve` takes the claims; a lane that would not fit beside one goes to another host, one line."""
    from halo_harness.local_sched.place import solve
    from halo_harness.providers.ollama import OllamaHost
    pc, samus = OllamaHost(name="pc", url="http://192.0.2.10:11434"), OllamaHost(name="samus", url="http://192.0.2.20:11434")
    gib = 2 ** 30
    room = {"pc": 22 * gib, "samus": 10 * gib}

    def ask(h, ln):
        return {"host": h.name, "via": "local", "fits": 8 * gib <= room[h.name], "now": True, "warm": False, "evicts": [], "installed": True,
                "capable": None, "load_s": 4.0 if h.name == "pc" else 18.0, "need_bytes": 8 * gib, "usable_bytes": room[h.name],
                "verdict": "fits"}
    lanes = [{"lane": "worker", "model": SMALL, "host": "pc"}]
    plan = solve(lanes, hosts=[pc, samus], answers=ask, claims={})
    ctx.check(f"no claim: the worker stays on pc, got {plan['line']}", plan["rows"][0]["host"] == "pc")
    held = {"pc": [{"bundle": "meta-glasses", "model": "lfm3:1.7b", "gb": 15.0}]}
    plan = solve(lanes, hosts=[pc, samus], answers=ask, claims=held)
    row = plan["rows"][0]
    ctx.check(f"the claim holds pc: the worker goes to samus, said, got {row}", row["host"] == "samus"
              and row["routed"] == "meta-glasses holds 15.0 GB on pc; worker goes to samus rather than evicting it"
              and row["says"].endswith(row["routed"]))
    plan = solve([{"lane": "worker", "model": "lfm3:1.7b", "host": "pc"}], hosts=[pc, samus], answers=ask, claims=held)
    ctx.check(f"the reserved model itself stays where it is held, got {plan['rows'][0]}", plan["rows"][0]["host"] == "pc")
    room["samus"] = 4 * gib
    plan = solve(lanes, hosts=[pc, samus], answers=ask, claims=held)
    ctx.check(f"nowhere: the claim named, got {plan['rows'][0]['says']}", plan["rows"][0]["host"] is None
              and "pc: meta-glasses holds 15.0 GB there" in plan["rows"][0]["says"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
