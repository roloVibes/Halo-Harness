"""tests.test_crew_map_api -- Halo 3.6.0.0 R3: the Map tab's routes (halo_harness/studio/crew_map_api.py) and
`halo maps` (halo_harness/maps_cli.py).

1. GET crew/maps: one row per name (yours over a starter), the one in use marked; GET crew/map/<name>: the map, each
   box's facts (an agent's model and what it does, a workflow's steps), the compile's problem lines;
2. PUT: a starter is saved as yours under its name; a new name makes a new map; a line that would make a circle is 422
   with the circle named; every write keeps its before-image (POST builder/undo puts it back byte for byte);
3. POST use {on}: config crew.map (undo puts config back); DELETE yours only; every write needs the owner's proof;
4. `halo maps list / show / use` say the same.
Run: python -m tests.test_crew_map_api
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.crew_rig import CrewRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _bytes(rig) -> dict:
    out = {str(p.relative_to(rig.state)): p.read_bytes() for p in (rig.state / "crew").rglob("*.yaml")} if (rig.state / "crew").is_dir() else {}
    cfg = rig.state / "config.json"
    out["config.json"] = cfg.read_bytes() if cfg.is_file() else b""
    return out


@test
def test_read_the_maps_and_one_map(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        st, r = rig.api("GET", "crew/maps")
        ctx.check(f"the two starters, none in use, got {st} {[m['name'] for m in r['maps']]}",
                  st == 200 and {m["name"] for m in r["maps"]} == {"starter", "ship-it"} and r["in_use"] is None)
        st, m = rig.api("GET", "crew/map/ship-it")
        ctx.check(f"ship-it: its boxes' facts (a workflow's steps), no problem, got {st} {m.get('problems')}",
                  st == 200 and m["problems"] == [] and m["boxes"]["plan"]["kind"] == "workflow"
                  and m["boxes"]["plan"]["facts"][0]["steps"][0]["agents"] == ["planner"] and m["main"]["agent"] == "main")
        st, m = rig.api("GET", "crew/map/starter")
        ctx.check("starter: an agent box's model and what it does", m["boxes"]["coder"]["facts"][0]["model"] == "auto"
                  and "change" in m["boxes"]["coder"]["facts"][0]["does"])
        ctx.check("no such map: 404", rig.api("GET", "crew/map/nope")[0] == 404)


@test
def test_save_a_circle_a_new_map_and_undo(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        before = _bytes(rig)
        _st, m = rig.api("GET", "crew/map/ship-it")
        body = m["map"]
        loop = {**body, "lines": body["lines"] + [{"from": "review", "to": "plan", "when": "always"}]}
        st, r = rig.api("PUT", "crew/map/ship-it", {"map": loop})
        ctx.check(f"a circle: 422 naming it, nothing written, got {st} {r.get('error')!r}",
                  st == 422 and "circle (plan -> code -> review -> plan)" in r["error"] and _bytes(rig) == before)
        two = {**body, "boxes": body["boxes"] + [{"id": "tester", "agent": "tester"}]}
        st, r = rig.api("PUT", "crew/map/ship-it", {"map": two})
        ctx.check(f"saved as yours under its name, got {st} {r.get('scope')}", st == 200 and r["scope"] == "yours" and r["undo_id"])
        st, _ = rig.api("POST", "builder/undo", {"undo_id": r["undo_id"]})
        ctx.check("Undo: byte for byte", st == 200 and _bytes(rig) == before)
        st, r = rig.api("PUT", "crew/map/release-day", {"map": {"boxes": [], "lines": []}})
        ctx.check(f"+ New map: a map with main only, got {st}", st == 200 and r["map"]["main"] == {"agent": "main"} and r["map"]["format"] == "map/1")
        st, r = rig.api("DELETE", "crew/map/release-day")
        ctx.check("delete yours", st == 200 and rig.api("GET", "crew/map/release-day")[0] == 404)
        ctx.check("a starter is not deleted", rig.api("DELETE", "crew/map/starter")[0] == 409)


@test
def test_use_the_owner_and_the_cli(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        before = _bytes(rig)["config.json"]
        st, r = rig.api("POST", "crew/map/ship-it/use", {"on": True})
        ctx.check(f"in use: ship-it, got {st} {r}", st == 200 and r["in_use"] == "ship-it" and rig.api("GET", "crew/maps")[1]["in_use"] == "ship-it")
        rig.api("POST", "builder/undo", {"undo_id": r["undo_id"]})
        ctx.check("Undo puts config.json back byte for byte", _bytes(rig)["config.json"] == before)
        for method, path in (("PUT", "crew/map/ship-it"), ("POST", "crew/map/ship-it/use"), ("DELETE", "crew/map/ship-it")):
            st, _r = rig.api(method, path, {"map": {}, "on": True}, owner=False)
            ctx.check(f"{method} {path} without the owner's proof: 403, got {st}", st == 403)
        from halo_harness.maps_cli import cmd_maps
        import os
        cwd = os.getcwd()
        os.chdir(rig.proj)
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                code = cmd_maps(["use", "starter"]) + cmd_maps(["list"]) + cmd_maps(["show", "ship-it"])
        finally:
            os.chdir(cwd)
        text = out.getvalue()
        ctx.check(f"halo maps use / list / show, got {text[:300]!r}", code == 0 and "New sessions run on the map starter" in text
                  and "* starter" in text and "line main -> plan: always" in text and "in use: starter (config)" in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
