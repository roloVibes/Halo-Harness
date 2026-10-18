"""tests.test_work_states -- Halo 3.1.2.0 round R2: the state machine is
enforced (halo_harness/work/states.py, work/unit.py `Unit.move`): every
legal edge moves, three illegal ones raise IllegalMove naming the unit,
from and to (and an engine setter that meets one writes nothing), and each
engine's real fixture history -- an Orchestra run with a hand-off, a team
run through its gate, a local mission and a flow run with a redo -- replays
through `Unit.move` from its first word to its last. No model is called.

Run: python -m tests.test_work_states
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _replay(kind: str, uid, words: list):
    """Move a fresh unit through `words` (engine words); the unit, or the IllegalMove text."""
    from halo_harness.work.states import IllegalMove
    from halo_harness.work.unit import Unit
    u = Unit.from_native(kind, uid, "" if kind == "lane" else "pending")
    try:
        for w in words:
            u.move_native(w)
    except IllegalMove as e:
        return str(e)
    return u


@test
def test_every_legal_edge_moves_and_the_added_ones_are_named(ctx: Ctx):
    from halo_harness.work import states as ST
    from halo_harness.work.unit import Unit
    moved = 0
    for a, outs in ST.EDGES.items():
        for b in outs:
            u = Unit(kind="lane", id="1", state=a)
            u.move(b)
            moved += u.state == b
    ctx.check(f"every edge moves, got {moved}", moved == sum(len(v) for v in ST.EDGES.values()))
    same = Unit(kind="stage", id="s", state="waiting").move("waiting")
    ctx.check("a move to the state it is in is the state said again", same.state == "waiting")
    ctx.check(f"R2's added edges are edges, got {ST.ADDED}", all(ST.can(a, b) for a, b in ST.ADDED) and len(ST.ADDED) == 5)
    ctx.check("stopped is the one state with no way out", ST.EDGES["stopped"] == () and ST.can("merged", "waiting")
              and not ST.can("merged", "ready"))


@test
def test_three_illegal_moves_raise_naming_the_unit_from_and_to(ctx: Ctx):
    from halo_harness.work.states import IllegalMove
    from halo_harness.work.unit import Unit, move_word
    cases = [(Unit(kind="lane", id="2", run_id="r1", state="merged"), "ready"),
             (Unit(kind="stage", id="draft", state="stopped"), "running"),
             (Unit(kind="part", id="3", state="pending"), "merged")]
    texts = []
    for u, to in cases:
        try:
            u.move(to)
            texts.append(None)
        except IllegalMove as e:
            texts.append(str(e))
    ctx.check(f"each raises with the unit, from and to, got {texts}",
              texts[0] == "lane 2 of run r1 cannot move from merged to ready (from merged it moves to waiting)"
              and texts[1] == "stage draft cannot move from stopped to running (from stopped it moves to nothing: it is over)"
              and texts[2].startswith("part 3 cannot move from pending to merged"))
    ctx.check("IllegalMove is a ValueError, and the engine-word helper raises it too",
              isinstance(IllegalMove("x", "a", "b"), ValueError) and _raises(lambda: move_word("step", "s", "done", "pending")))
    from tests.helpers import team_rig as R
    from halo_harness.team import board as BD
    from halo_harness.team import spec as S
    from halo_harness.team.run import open_run
    root, state = R.repo()
    run_dir = open_run(S.load_team(root, state), cwd=root, state_dir=state)
    BD.set_stage(run_dir, "draft", "running")
    BD.set_stage(run_dir, "draft", "done")
    before = (run_dir / "board.json").read_text(encoding="utf-8")
    ctx.check("the board's setter refuses done -> pending and writes nothing",
              _raises(lambda: BD.set_stage(run_dir, "draft", "pending"))
              and (run_dir / "board.json").read_text(encoding="utf-8") == before)


def _raises(fn) -> bool:
    from halo_harness.work.states import IllegalMove
    try:
        fn()
    except IllegalMove:
        return True
    return False


@test
def test_an_orchestra_runs_lanes_replay_through_move(ctx: Ctx):
    from tests.helpers.orchestra_studio_rig import finished_run
    _repo, run_dir = finished_run(chain=True)
    ok, seen = True, {}
    for path in sorted((run_dir / "lanes").glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        words = [h["state"] for h in rec.get("history") or []]
        got = _replay("lane", rec["lane"], words)
        seen[rec["lane"]] = words
        ok = ok and not isinstance(got, str) and got.native == rec["state"] == "merged"
    ctx.check(f"every lane's history replays to merged, got {seen}", ok and len(seen) == 5
              and seen[2][0] == "waiting" and "joined" in seen[2])


@test
def test_a_team_run_and_a_flow_run_replay_through_move(ctx: Ctx):
    from tests.helpers import team_rig as R
    from halo_harness.team import spec as S
    from halo_harness.team import stages as TS
    from halo_harness.team.board import read_events
    from halo_harness.team.run import TeamRunner, open_run
    root, state = R.repo()
    team = S.load_team(root, state)
    fakes = R.Fakes()
    runner = TeamRunner(team, open_run(team, cwd=root, state_dir=state), **fakes.seams())
    runner.request("draft")
    runner.tick()
    TS.write_answer(runner.run_dir, "draft", "redo", "again")
    runner.tick()
    TS.write_answer(runner.run_dir, "draft", "accept")
    runner.tick()
    per: dict = {}
    for e in read_events(runner.run_dir):
        d = e.get("data") or {}
        if e["kind"] == "state" and d.get("state") and not d.get("member"):
            per.setdefault(e["stage"], []).append(d["state"])
    bad = {sid: got for sid, words in per.items() if isinstance(got := _replay("stage", sid, words), str)}
    ctx.check(f"every stage's state lines replay, got {per} {bad}", not bad and per["draft"][:4] == ["ready", "running", "gated", "ready"]
              and per["draft"][-1] == "done" and per["review"][-1] == "done")
    from halo_harness.flows.state import read_events as flow_events
    from tests.helpers.fake_comfy import FakeComfy
    from tests.helpers.fake_flow import Answers, FakeOrg, make_adapters, new_run, template_spec
    from halo_harness.flows.run import run
    with FakeComfy() as fake:
        run_dir = new_run(template_spec(), project="flow-replay")
        report = run(run_dir, adapters=make_adapters(fake.url, run_org=FakeOrg(gate=False),
                                                     answers=Answers({"approve": [("redo", "warmer"), ("accept", "")]})))
    steps: dict = {}
    for e in flow_events(run_dir):
        if e["kind"] == "state" and (e.get("data") or {}).get("state"):
            steps.setdefault(e["step"], []).append(e["data"]["state"])
    bad = {sid: got for sid, words in steps.items() if isinstance(got := _replay("step", sid, words), str)}
    ctx.check(f"the flow finished and every step replays (a redo: done -> running), got {report['status']} {bad}",
              report["status"] == "finished" and not bad and "waiting" in steps["approve"]
              and steps["render"].count("running") == 2)


@test
def test_a_local_missions_parts_replay_through_move(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.fleet import mission_api as A
    from halo_harness.fleet import mission_store as S
    from halo_harness.fleet import mission_worker as W
    from halo_harness.fleet.identity import harness
    from tests.helpers.fleet_caps_seed import seed
    from tests.helpers.mission_seed import FakeLead, reset_fakes, wait_state, windows_host, worker
    home = bridge_home()
    seed(home, windows_host(harness()))
    answer = json.dumps({"parts": [{"id": "a", "title": "One", "brief": "Write one.", "kind": "files", "outputs": ["one.txt"]},
                                   {"id": "b", "title": "Two", "brief": "Then two.", "kind": "files", "depends_on": ["a"]}],
                         "merge_order": []})
    A.LEAD = FakeLead(answer)
    W.BUILD = worker({"1": {"writes": ["artifacts/1/one.txt"]}}, [])
    try:
        mctx = A.Ctx(home, None, by="owner", cwd=None)
        mid = A.create(mctx, {"goal": "Write one, then two", "repo": False})[1]["mission"]["id"]
        A.run(mctx, mid)
        doc = wait_state(home, mid, ("done", "failed", "stopped"), 60)
    finally:
        reset_fakes()
    parts: dict = {}
    for e in S.read_log(home, mid, ("part",)):
        parts.setdefault(e["part"], []).append(e["state"])
    bad = {pid: got for pid, words in parts.items() if isinstance(got := _replay("part", pid, words), str)}
    ctx.check(f"the mission finished and each part's log replays, got {doc['state']} {parts} {bad}",
              doc["state"] == "done" and not bad and parts and all(w[-1] == "done" for w in parts.values()))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="work state machine tests"))
