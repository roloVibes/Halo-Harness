"""tests.test_replay_run_time -- Halo 3.4.1.1 defect 60: a goal run's record gives its lanes' states and its costs at
their own times (live/replay_run.py through `GET fleet/replay?run=`). 3.6.0.3 B (Z4 batch 4): Studio's scrubber and its
timeline.ts left, and with them the node half of this file (the scrubber said "unknown at this moment", never $0); the
server half stays until the server batch takes the route.

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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="replay run time"))
