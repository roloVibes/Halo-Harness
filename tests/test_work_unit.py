"""tests.test_work_unit -- Halo 3.1.2.0 R1: the one unit of work and its state
machine (halo_harness/work/unit.py, states.py, store.py and the three
adapters, docs/WORK.md).

1. the state machine: every engine state word of every kind maps onto the
   machine and back (`native(unify(w)) == w`), and every machine state has
   a native word for each kind;
2. a lane, a part and a stage read from each engine's own seeded
   fixture file as a `Unit`, and written back, are byte-identical;
3. `UnitStore` reads the units of a run of each kind and its unit rows;
4. (3.1.2.0 R3) a delegated unit's `refs.harness`: a mission part's harness,
   a team stage's member (its row or its remote run), in the report row,
   `halo work`'s table and `GET work/...`; a local unit reads "here".
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


def _not_a_run(store_cls, folder) -> bool:
    try:
        store_cls(folder)
    except ValueError:
        return True
    return False


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
def test_a_stage_and_a_part_read_as_units(ctx: Ctx):
    from tests.helpers.coach_seed import mission_folder, orchestra_run, team_run
    from tests.helpers import coach_seed as S
    import tempfile
    root = Path(tempfile.mkdtemp(prefix="work-kinds-"))
    from halo_harness.work.store import UnitStore
    # a team run (stages) seeded by coach_seed; 3.1.4.0: a flow run folder is no run kind any more
    flows = root / "flows" / "runs" / "20261017-120500-f10a"
    flows.mkdir(parents=True)
    (flows / "flow.json").write_text("{}", encoding="utf-8")
    ctx.check("a leftover flow run folder is no unit store", _not_a_run(UnitStore, flows))
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


@test
def test_a_delegated_units_harness_is_in_the_row_the_table_and_the_route(ctx: Ctx):
    import io
    import tempfile
    from contextlib import redirect_stdout
    from halo_harness.studio.api import Request
    from halo_harness.studio.work_api import dispatch_work
    from halo_harness.team import board as BD
    from halo_harness.work.report import table
    from halo_harness.work.store import UnitStore
    from tests.helpers.coach_seed import mission_folder, team_run
    root = Path(tempfile.mkdtemp(prefix="work-harness-"))
    mission_dir = mission_folder(root)
    mrows = {r["unit"]: r for r in UnitStore(mission_dir).rows()}
    ctx.check(f"a part names the harness it ran on, got {[(k, r['harness']) for k, r in mrows.items()]}",
              mrows["2"]["harness"] == "kali" and mrows["1"]["harness"] == "hub"
              and UnitStore(mission_dir).need("2").refs["harness"] == "h-kali")
    team_dir = team_run(root)
    board_before = (Path(team_dir) / "board.json").read_bytes()

    def delegate(board):
        BD.row(board, "copy")["harness"] = "kali"
        BD.row(board, "ship")["remote"] = {"harness": "box-2", "kind": "orchestra", "mission": "m1", "part_state": "done",
                                           "run": "r1"}
    BD.update_board(team_dir, delegate)
    store = UnitStore(team_dir)
    trows = {r["unit"]: r for r in store.rows()}
    ctx.check(f"a stage names its member (the row, else the remote run), got {[(k, r['harness']) for k, r in trows.items()]}",
              trows["copy"]["harness"] == "kali" and trows["ship"]["harness"] == "box-2")
    refs_file = Path(team_dir) / "stages" / "copy" / "refs.json"
    had = refs_file.read_bytes() if refs_file.exists() else None
    store.write(store.unit("copy"))
    ctx.check("the derived harness is not written into refs.json",
              (refs_file.read_bytes() if refs_file.exists() else None) == had)
    text = table(list(trows.values()) + [dict(mrows["1"], harness=None)])
    ctx.check(f"halo work's table has a harness column, a local unit reads here: {text!r}",
              "harness" in text.splitlines()[0] and "kali" in text and "box-2" in text and " here " in text)
    from halo_harness.work_cli import cmd_work
    out = io.StringIO()
    with redirect_stdout(out):
        rc = cmd_work([str(team_dir), "--json"], repo=root)
    import json
    units = {u["unit"]: u for u in json.loads(out.getvalue())["units"]}
    ctx.check("halo work --json carries it", rc == 0 and units["copy"]["harness"] == "kali")
    status, body = dispatch_work(Request("GET", f"work/mission/{Path(mission_dir).name}", {}, {}, root,
                                         Path(mission_dir).parent.parent.parent))
    got = {u["unit"]: u["harness"] for u in body.get("units") or []}
    ctx.check(f"GET work/mission/<id> carries it, got {status} {got}", status == 200 and got.get("2") == "kali")
    status, body = dispatch_work(Request("GET", f"work/team/{Path(team_dir).name}", {}, {}, root, root))
    got = {u["unit"]: u["harness"] for u in body.get("units") or []}
    ctx.check(f"GET work/team/<run> carries it, got {status} {got}", status == 200 and got == {"copy": "kali", "ship": "box-2"})
    ctx.check("the seeded board was read, then delegated", board_before != (Path(team_dir) / "board.json").read_bytes())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="work unit tests"))
