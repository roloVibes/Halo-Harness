"""tests.test_work_unit -- Halo 3.1.2.0 R1: the one unit of work and its state
machine (halo_harness/work/unit.py, states.py, store.py and the four
adapters, docs/WORK.md).

1. the state machine: every engine state word of every kind maps onto the
   machine and back (`native(unify(w)) == w`), and every machine state has
   a native word for each kind;
2. a lane, a part, a stage and a step read from each engine's own seeded
   fixture file as a `Unit`, and written back, are byte-identical;
3. `UnitStore` reads the units of a run of each kind and its unit rows.
Run: python -m tests.test_work_unit
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


@test
def test_every_engine_word_round_trips_through_the_alias_tables(ctx: Ctx):
    from halo_harness.work import states as ST
    for kind in ST.KINDS:
        words = ST.words(kind)
        ctx.check(f"{kind} has engine words", words)
        for w in words:
            m = ST.unify(kind, w)
            ctx.check(f"{kind}: {w!r} -> {m!r} -> {ST.native(kind, m)!r}", m in ST.STATES and ST.native(kind, m) == w)
        for m in ST.STATES:
            ctx.check(f"{kind}: machine {m!r} has a native word", ST.native(kind, m) in words)
    bad = []
    for kind in ST.KINDS:
        try:
            ST.unify(kind, "not-a-state")
        except ValueError:
            bad.append(kind)
    ctx.check("an unknown word is a ValueError per kind", bad == list(ST.KINDS))


@test
def test_a_lane_round_trips_byte_identical(ctx: Ctx):
    from halo_harness.orchestra.run import run
    from halo_harness.work.store import UnitStore
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("work-lane-")
    run_dir = F.make_run(repo)
    run(run_dir, model_calls=F.FakeLead(F.split_answer([[f] for f in F.FUNCS])), spawn=F.FakeWorker(), judge=F.FakeJudge())
    store = UnitStore(run_dir)
    ctx.check("the run is a lane run", store.kind == "lane" and store.run_kind == "orchestra")
    units = store.units()
    ctx.check(f"five lanes, each a merged unit, got {[u.state for u in units]}",
              len(units) == 5 and all(u.state == "merged" and u.native == "merged" for u in units))
    u = units[0]
    ctx.check("the unit carries the claim, the hand-offs and the base",
              u.claims["keys"] == ["basket.py#add_item"] and u.base and any(g["kind"] == "summary" for g in u.gives))
    for n in range(1, 6):
        before = (Path(run_dir) / "lanes" / f"{n}.json").read_bytes()
        store.write(store.unit(str(n)))
        ctx.check(f"lane {n} writes back byte-identical", (Path(run_dir) / "lanes" / f"{n}.json").read_bytes() == before)


@test
def test_a_step_a_stage_and_a_part_read_as_units(ctx: Ctx):
    from tests.helpers.coach_seed import flow_run, mission_folder, orchestra_run, team_run
    from tests.helpers import coach_seed as S
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="work-kinds-"))
    from halo_harness.work.store import UnitStore
    # a flow run (steps) and a team run (stages) seeded by coach_seed
    flow_dir = flow_run(root)
    fstore = UnitStore(flow_dir)
    frows = fstore.rows()
    ctx.check(f"flow: three step units, got {[r['unit'] for r in frows]}",
              fstore.kind == "step" and [r["unit"] for r in frows] == ["intake", "render", "approve"]
              and frows[1]["kind"] == "step")
    team_dir = team_run(root)
    tstore = UnitStore(team_dir)
    trows = tstore.rows()
    ctx.check(f"team: two stage units with their states, got {[(r['unit'], r['state']) for r in trows]}",
              tstore.kind == "stage" and {r["unit"] for r in trows} == {"copy", "ship"}
              and all(r["kind"] == "stage" for r in trows))
    mission_dir = mission_folder(root)
    mstore = UnitStore(mission_dir)
    mrows = mstore.rows()
    ctx.check(f"mission: four part units, each a path-claim unit, got {[r['unit'] for r in mrows]}",
              mstore.kind == "part" and [r["unit"] for r in mrows] == ["1", "2", "3", "4"]
              and mstore.need("1").claims["mode"] == "path")
    # a part writes back without changing mission.json's updated stamp
    doc_before = (mission_dir / "mission.json").read_bytes()
    mstore.write(mstore.unit("1"))
    ctx.check("a part written back unchanged leaves mission.json as it was", (mission_dir / "mission.json").read_bytes() == doc_before)


@test
def test_halo_work_and_the_route(ctx: Ctx):
    import io
    from contextlib import redirect_stdout
    from halo_harness.orchestra.run import run
    from halo_harness.studio.api import Request
    from halo_harness.studio.work_api import dispatch_work
    from halo_harness.work_cli import cmd_work
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("work-cli-")
    run_dir = F.make_run(repo)
    run(run_dir, model_calls=F.FakeLead(F.split_answer([[f] for f in F.FUNCS])), spawn=F.FakeWorker(), judge=F.FakeJudge())
    out = io.StringIO()
    with redirect_stdout(out):
        rc = cmd_work([str(run_dir)], repo=repo)
    text = out.getvalue()
    ctx.check(f"halo work prints the five lane units, got rc {rc}", rc == 0 and "orchestra run" in text
              and text.count("lane") >= 5)
    out = io.StringIO()
    with redirect_stdout(out):
        cmd_work([str(run_dir), "--json"], repo=repo)
    import json
    data = json.loads(out.getvalue())
    ctx.check("halo work --json is the shared rows", data["kind"] == "orchestra" and len(data["units"]) == 5)
    ctx.check("an unknown run exits 1", cmd_work(["no-such-run"], repo=repo) == 1)
    req = Request(method="GET", path=f"work/orchestra/{run_dir.name}", query={}, body={}, cwd=repo, state_dir=repo)
    status, body = dispatch_work(req)
    ctx.check(f"GET work/orchestra/<run>: 200 and five units, got {status}",
              status == 200 and body["kind"] == "orchestra" and len(body["units"]) == 5)
    ctx.check("POST is 405, an unknown run 404, a non-work path None",
              dispatch_work(Request("POST", f"work/orchestra/{run_dir.name}", {}, {}, repo, repo))[0] == 405
              and dispatch_work(Request("GET", "work/orchestra/nope", {}, {}, repo, repo))[0] == 404
              and dispatch_work(Request("GET", "roles", {}, {}, repo, repo)) is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="work unit tests"))
