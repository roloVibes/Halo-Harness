"""tests.test_replay_run -- Halo 3.4.1.0 R2 "Time": a goal run saved as the same replay file a session is
(live/replay_run.py: round trip, its version, the redaction), the record's own figures (live/replay_facts.py: each
call counted once, the unpriced part unknown, tokens, retries, steers) and Studio's Save for a goal run.

Seeds: tests/helpers/replay_seed.py (a session) and tests/helpers/compare_seed.py (a second session with a sub-agent's
rolled-up total and an unpriced call; a goal run with two lanes, a plan review, a fake key, the repo's path).
Run: python -m tests.test_replay_run
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

from tests.helpers.compare_seed import RUN, SID_B, TR, seed_b, seed_run  # noqa: E402
from tests.helpers.replay_seed import FAKE_KEY  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@contextlib.contextmanager
def _home():
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    with tempfile.TemporaryDirectory(prefix="halo-replay-run-") as d:
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ.pop("BRIDGE_STATE_DIR", None)
        try:
            from halo_harness.config.paths import bridge_home
            yield bridge_home()
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


@test
def test_a_sub_agents_cost_counts_once(ctx: Ctx):
    from halo_harness.live import history
    with _home() as state:
        h = history.read(seed_b(state))
        ctx.check(f"main's $0.004 and the reviewer's $0.008, its rolled-up total not again: {h['cost_usd']}", abs(h["cost_usd"] - 0.012) < 1e-9)
        main = next(a for a in h["agents"] if a["agent_id"] == "main")
        ctx.check(f"main's own cost is its own calls: {main['cost_usd']}", abs(main["cost_usd"] - 0.004) < 1e-9)
        ctx.check(f"the running total ends at the session's: {h['costs'][-1]}", abs(h["costs"][-1]["usd"] - 0.012) < 1e-9)


@test
def test_the_records_figures(ctx: Ctx):
    from halo_harness.live import history, replay_facts
    with _home() as state:
        f = replay_facts.session_facts(seed_b(state))
        ctx.check(f"cost from the transcripts, each call once: {f['cost_usd']}", abs(f["cost_usd"] - 0.012) < 1e-9)
        ctx.check(f"the unpriced call's model is unknown, not $0: {f['cost_unknown']}", f["cost_unknown"] == ["or:mock/free"])
        ctx.check(f"tokens in and out (main's two calls + the reviewer's): {f['tokens']}", f["tokens"] == {"in": 4000, "out": 800})
        ctx.check(f"each model's cost: {f['model_cost']}", f["model_cost"] == {"or:mock/glm-5.3": 0.012})
        ctx.check(f"the retries and the steer: {f['retries']} {f['steers']}", f["retries"] == 1 and len(f["steers"]) == 1)
        priced = replay_facts.session_facts(seed_b(state, priced=True))
        ctx.check("a call priced at $0 is known", priced["cost_unknown"] == [] and abs(priced["cost_usd"] - 0.012) < 1e-9)
        ctx.check("the session file is found by id", history.find(state, SID_B) is not None)


@test
def test_a_goal_run_is_one_replay_file(ctx: Ctx):
    from halo_harness.live import replay_file as RF
    from halo_harness.live import replay_run
    with _home() as state:
        repo = state.parent / "repo"
        run_dir = seed_run(repo)
        ctx.check("found by id in the repo", replay_run.find(repo, RUN) == run_dir and replay_run.find(repo, "nope") is None)
        p = replay_run.build_run(state, run_dir)
        ctx.check(f"kind run, format and version unchanged: {p['kind']} {p['version']}", p["kind"] == "run" and p["format"] == "halo-replay" and p["version"] == RF.VERSION == 1)
        ctx.check(f"the lead and its two lanes as agents: {[a['agent_id'] for a in p['agents']]}",
                  [a["agent_id"] for a in p["agents"]] == ["lead", "lane-1", "lane-2"] and p["agents"][1]["parent"] == "lead")
        ctx.check(f"lane 1 done, lane 2 failed: {[a['state'] for a in p['agents']]}", [a["state"] for a in p["agents"]] == ["done", "done", "failed"])
        kinds = [(m["kind"], round(m["t"] - TR)) for m in p["marks"]]
        ctx.check(f"the plan review, two spawns, two hand-offs, the failure and the finishes: {kinds}",
                  ("ask", 8) in kinds and kinds.count(("spawn", 10)) == 2 and ("handoff", 40) in kinds and ("fail", 50) in kinds and ("finish", 90) in kinds)
        ctx.check("each lane's states from its record", any(s["agent_id"] == "lane-1" and s["activity"] == "typing" for s in p["states"]))
        ctx.check(f"the bands: {sorted({b['phase'] for b in p['bands']})}", {"writing"} <= {b["phase"] for b in p["bands"]})
        f = p["facts"]
        ctx.check(f"its figures from the report and the lanes: {f}", f["cost_usd"] == 0.05 and f["how"] == "finished" and f["ok"] is True
                  and f["retries"] == 1 and f["model_cost"] == {"or:mock/lead": 0.01, "or:mock/glm-5.3": 0.03, "or:mock/worker": 0.01})
        ctx.check("its tokens are unknown (no lane session on this disk), never 0", f["tokens"] is None)
        path = RF.save(state, p)
        back = RF.load(path)
        ctx.check("round trip", back == json.loads(json.dumps(p)))
        row = RF.saved(state)[0]
        ctx.check(f"listed as a goal run: {row['kind']} {row['run_id']}", row["kind"] == "run" and row["run_id"] == RUN and row["agents"] == 3)


@test
def test_a_seeded_key_never_reaches_a_goal_runs_file(ctx: Ctx):
    from halo_harness.live import replay_file as RF
    from halo_harness.live import replay_run
    with _home() as state:
        run_dir = seed_run(state.parent / "repo")
        raw = RF.save(state, replay_run.build_run(state, run_dir)).read_bytes().decode("utf-8")
        ctx.check("no key in the file (the goal and a lane's title held one)", FAKE_KEY not in raw and FAKE_KEY[9:] not in raw)
        ctx.check("where it stood, the redactor's mark", "<redacted>" in raw)
        ctx.check("no repo path, worktree or branch", "secret-project" not in raw and '"cwd"' not in raw and "worker-1" not in raw)


@test
def test_studio_saves_a_goal_run(ctx: Ctx):
    from halo_harness.studio.replays_api import dispatch_replays
    with _home() as state:
        repo = state.parent / "repo"
        seed_run(repo)
        server = SimpleNamespace(server_address=("127.0.0.1", 1), token="t")

        def call(method, path, query=None, body=None):
            req = SimpleNamespace(method=method, path=path, query=query or {}, body=body, state_dir=state, cwd=repo, server=server, params={})
            return dispatch_replays(req)
        code, plan = call("GET", "replays/plan", {"run": RUN})
        ctx.check(f"plan says what Save holds for a goal run, nothing written: {code} {plan.get('includes')}",
                  code == 200 and any("goal run" in line for line in plan["includes"]) and not (state / "replays").exists())
        code, saved = call("POST", "replays/save", body={"run": RUN})
        ctx.check(f"save writes it under replays/: {saved.get('path')}", code == 200 and Path(saved["path"]).is_file() and saved["id"].startswith(RUN + "-"))
        code, one = call("GET", f"replays/{saved['id']}")
        ctx.check("the file opens like any other", code == 200 and one["kind"] == "run")
        code, clip = call("GET", f"replays/{saved['id']}/clip", {"from": "0", "to": "90", "speed": "16"})
        ctx.check(f"Export a clip plans from it: {code}", code == 200 and clip["frames"] > 1)
        ctx.check("an unknown goal run is 404", call("POST", "replays/save", body={"run": "nope"})[0] == 404)
        ctx.check("neither named: 422", call("POST", "replays/save", body={})[0] == 422)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="replay run"))
