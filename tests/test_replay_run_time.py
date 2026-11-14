"""tests.test_replay_run_time -- Halo 3.4.1.1 defect 60: a goal run on the scrubber is the canvas AS IT WAS. Its lanes'
states and its costs at a past moment come from its record's own times (live/replay_run.py through `GET
fleet/replay?run=`), and where the record cannot give a figure at a moment the page says "unknown at this moment",
never $0 (routes/agents/live/timeline.ts, run in node through tests/helpers/node_ts.py).

Seed: tests/helpers/compare_seed.py's goal run, lane 1 written at +70 and merged at +80 (its `ended` says +70, as a
real lane's does: the end of its last piece, before the review). Run: python -m tests.test_replay_run_time
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.compare_seed import RUN, TR, seed_run  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
LIVE = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes" / "agents" / "live"


@contextlib.contextmanager
def _run():
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    with tempfile.TemporaryDirectory(prefix="halo-run-time-") as d:
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ.pop("BRIDGE_STATE_DIR", None)
        try:
            from halo_harness.config.paths import bridge_home
            state, repo = bridge_home(), Path(d) / "repo"
            run_dir = seed_run(repo)
            lane = run_dir / "lanes" / "1.json"
            lane.write_text(json.dumps(dict(json.loads(lane.read_text(encoding="utf-8")), ended=TR + 70)), encoding="utf-8")
            yield state, repo
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _payload(state: Path, repo: Path):
    from halo_harness.studio.live_recording_api import get_replay
    req = SimpleNamespace(query={"run": RUN}, cwd=repo, state_dir=state, params={})
    return get_replay(req)


@test
def test_studio_draws_a_goal_run_from_its_record(ctx: Ctx):
    with _run() as (state, repo):
        code, p = _payload(state, repo)
        ctx.check(f"GET fleet/replay?run= answers the run's axis, kind run: {code} {p.get('kind')}", code == 200 and p["kind"] == "run")
        lane1 = next(a for a in p["agents"] if a["agent_id"] == "lane-1")
        ctx.check(f"lane 1 ends when it merged (+80), not when its piece was written (+70): {lane1['ended'] - TR}",
                  round(lane1["ended"] - TR) == 80)
        ends = {s["agent_id"]: round(s["t"] - TR) for s in p["states"] if s["state"] == "done"}
        ctx.check(f"its done state is at +80: {ends}", ends.get("lane-1") == 80)
        costs = [(round(c["t"] - TR), c["usd"]) for c in p["costs"]]
        ctx.check(f"its costs come at each end (the record's only times for them): {costs}", costs and costs[-1] == (90, 0.05))
        bad = SimpleNamespace(query={"run": "nope"}, cwd=repo, state_dir=state, params={})
        from halo_harness.studio.live_recording_api import get_replay
        ctx.check("an unknown run is 404", get_replay(bad)[0] == 404)


@test
def test_a_role_word_is_never_named_as_the_model(ctx: Ctx):
    """3.4.1.1 defect 59: a goal run with `lead: main` (the lead role) read "MODELS USED ... main: 2 % of cost" and the
    lead's box MODEL main. The lead's model is its own session's record's, else said as not recorded."""
    from halo_harness.live import replay_run
    with _run() as (state, repo):
        run_dir = repo / ".halo" / "orchestra" / RUN
        goal = json.loads((run_dir / "goal.json").read_text(encoding="utf-8"))
        (run_dir / "goal.json").write_text(json.dumps(dict(goal, lead="main", worker="subagent")), encoding="utf-8")
        p = replay_run.build_run(state, run_dir)
        ctx.check(f"no session on disk: the lead's model is not recorded, never `main`: {p['agents'][0]['model']} {p['facts']['model_cost']}",
                  p["agents"][0]["model"] is None and "main" not in p["facts"]["model_cost"]
                  and replay_run.LEAD_UNKNOWN in p["facts"]["model_cost"])
        split = json.loads((run_dir / "split.json").read_text(encoding="utf-8"))
        (run_dir / "split.json").write_text(json.dumps(dict(split, lead_sessions=["leadsess0001"])), encoding="utf-8")
        sess = state / "sessions" / "repo" / "leadsess0001.jsonl"
        sess.parent.mkdir(parents=True, exist_ok=True)
        sess.write_text(json.dumps({"type": "meta", "ts": TR, "model": "or:deepseek/deepseek-v4.1-flash"}) + "\n", encoding="utf-8")
        p = replay_run.build_run(state, run_dir)
        ctx.check(f"its session's record names it: {p['agents'][0]['model']} {sorted(p['facts']['model_cost'])}",
                  p["agents"][0]["model"] == "or:deepseek/deepseek-v4.1-flash" and "or:deepseek/deepseek-v4.1-flash" in p["facts"]["model_cost"])


JS = """const m = await import(%s);
const p = %s;
const tl = m.fromSession(p, "run");
const at = (s) => { const t = p.started + s; const ns = m.nodesAt(tl, t);
  const l1 = ns.find((n) => n.id === "lane-1"); return { cost: m.costAt(tl, t), l1: l1 && l1.state, l1cost: l1 && l1.cost, unk: !!(l1 && l1.costUnknown) }; };
const s = m.fromSession({ ...p, kind: "session" }, "s");
console.log(JSON.stringify({ ends: tl.endsOnly, mid: at(%s), late: at(%s), end: at(%s), session: m.costAt(s, p.started + %s) }));
"""


@test
def test_the_scrubber_says_unknown_never_zero(ctx: Ctx):
    from tests.helpers import node_ts
    with _run() as (state, repo):
        _code, p = _payload(state, repo)
        mid, late, end = TR + 60 - p["started"], TR + 75 - p["started"], TR + 90 - p["started"]
        got = node_ts.run(JS % (json.dumps((LIVE / "timeline.ts").resolve().as_uri()), json.dumps(p), mid, late, end, mid))
        ctx.check(f"a goal run's axis gives costs at ends only: {got['ends']}", got["ends"] is True)
        ctx.check(f"mid-run: the cost and lane 1's are unknown at this moment, never $0: {got['mid']}",
                  got["mid"]["cost"] is None and got["mid"]["l1cost"] is None and got["mid"]["unk"] is True)
        ctx.check(f"at +75 lane 1 is still at work (written at +70, merged at +80): {got['late']['l1']}",
                  got["late"]["l1"] not in ("done", "failed"))
        ctx.check(f"at the end: the run's $0.05 and lane 1 done: {got['end']}",
                  abs((got["end"]["cost"] or 0) - 0.05) < 1e-9 and got["end"]["l1"] == "done" and got["end"]["unk"] is False)
        ctx.check(f"a session's axis is unchanged (its usage lines price each call when it lands): {got['session']}",
                  isinstance(got["session"], (int, float)))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="replay run time"))
