"""tests.test_history_owner -- Halo 3.4.0.1 "Found live" (defect 22): History folds a goal run's and a mission's own
sessions under their row. The live check listed "You are the lead orchestrator ...", "You are worker 1 of an
Orchestra run ..." and a mission's lead and part sessions beside their runs: 24 rows for 2 runs, 2 missions, 3 sessions.

`GET fleet/history?role=main` names each such session's owner (`part_of`, live/history_owner.py, read from the run's
split.json and lanes and the mission's plan.json and mission.json); the page (historyStore.historyRows) leaves them out
of its list and counts them on the owner's row.
Run: python -m tests.test_history_owner
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
UI = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src"


def _w(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _session(state: Path, sid: str, text: str) -> None:
    lines = [{"type": "meta", "ts": time.time() - 60}, {"type": "user", "content": text},
             {"type": "usage", "usage": {}, "cost_usd": 0.0015, "model": "or:x"}]
    p = state / "sessions" / "proj" / f"{sid}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")


@test
def test_a_runs_and_a_missions_sessions_name_their_owner(ctx: Ctx):
    from halo_harness.studio.live_agents_api import get_history
    root = Path(tempfile.mkdtemp(prefix="hist-owner-"))
    state, repo = root / ".halo", root / "repo"
    run = repo / ".halo" / "orchestra" / "20261112-000750-5483"
    _w(run / "goal.json", {"what": "x"})
    _w(run / "split.json", {"lead_cost_usd": 0.003, "lead_sessions": ["lead-1", "lead-2"], "jobs": []})
    _w(run / "lanes" / "1.json", {"lane": 1, "session_ids": ["worker-1"]})
    _w(state / "fleet" / "missions" / "m-20261112-dd68" / "plan.json", {"lead_sessions": ["m-lead"]})
    _w(state / "fleet" / "missions" / "m-20261112-dd68" / "mission.json", {"parts": {"1": {"session_id": "m-part"}}})
    for sid, text in (("lead-1", "You are the lead orchestrator."), ("lead-2", "You are the lead orchestrator."),
                      ("worker-1", "You are worker 1 of an Orchestra run"), ("m-lead", "You are the lead of a fleet mission"),
                      ("m-part", "# Mission m-20261112-dd68, part 1"), ("mine", "fix the basket")):
        _session(state, sid, text)
    req = SimpleNamespace(query={"role": "main", "n": "20"}, cwd=repo, state_dir=state)
    status, body = get_history(req)
    own = {r["session_id"]: r.get("part_of") for r in body["runs"]}
    ctx.check(f"each run or mission session names its owner, the owner's own session none, got {own}", status == 200
              and own["lead-1"] == own["lead-2"] == own["worker-1"] == {"kind": "run", "id": "20261112-000750-5483"}
              and own["m-lead"] == own["m-part"] == {"kind": "mission", "id": "m-20261112-dd68"} and own["mine"] is None)
    store = (UI / "routes" / "agents" / "live" / "historyStore.ts").read_text(encoding="utf-8")
    ctx.check("the page leaves them out of its list and counts them on the owner's row",
              "s.part_of) continue;" in store and "r.inside = inside.get(" in store)
    row = (UI / "routes" / "agents" / "live" / "History.tsx").read_text(encoding="utf-8")
    ctx.check("the owner's row says how many sessions it holds", "r.inside ? `${r.inside} session" in row)


@test
def test_a_goal_run_of_another_repo_folds_too(ctx: Ctx):
    """3.4.1.0 R5 (live re-check defect 35): Studio started in krepo listed grepo's lead ("You are the lead
    orchestrator ...") and worker sessions as rows: the owners were read from Studio's folder only. Each session's
    record names its own folder (meta `cwd`): the lead's is the repo, a worker's is the run's worktree."""
    from halo_harness.studio.live_agents_api import get_history
    root = Path(tempfile.mkdtemp(prefix="hist-other-"))
    state, krepo, grepo = root / ".halo", root / "krepo", root / "grepo"
    krepo.mkdir()
    rid = "20261112-031802-0776"
    run = grepo / ".halo" / "orchestra" / rid
    _w(run / "goal.json", {"what": "x"})
    _w(run / "split.json", {"lead_cost_usd": 0.0085, "lead_sessions": ["g-lead"], "jobs": []})
    _w(run / "lanes" / "1.json", {"lane": 1, "session_ids": ["g-worker"]})
    for sid, cwd, text in (("g-lead", grepo, "You are the lead orchestrator."),
                           ("g-worker", run / "wt" / "worker-1", "You are worker 1 / 2 of an Orchestra run"),
                           ("k-mine", krepo, "fix the basket")):
        p = state / "sessions" / "proj" / f"{sid}.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(json.dumps(x) for x in [{"type": "meta", "ts": time.time() - 60, "cwd": str(cwd)},
                                                       {"type": "user", "content": text}]) + "\n", encoding="utf-8")
    status, body = get_history(SimpleNamespace(query={"role": "main", "n": "20"}, cwd=krepo, state_dir=state))
    own = {r["session_id"]: r.get("part_of") for r in body["runs"]}
    ctx.check(f"grepo's lead and worker are its run's, whatever Studio's folder; krepo's own session none, got {own}",
              status == 200 and own["g-lead"] == own["g-worker"] == {"kind": "run", "id": rid} and own["k-mine"] is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="history owner tests"))
