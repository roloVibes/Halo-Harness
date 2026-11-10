"""tests.test_studio_team -- what is left of Studio's Team routes (Halo 3.0.8.0 R1; 3.3.16.0 R1 "Agents: one section":
Team's board went into Agents -> Runs) through tests/test_studio_api.py's `_Studio` rig (an in-process server over a
scoped home; the repo is built in the Studio's own folder): every route the board read or wrote answers 410 with the
line saying where it went; a team stage at its gate is still a `team_gate` row of the Fleet attention queue, whose
`o` opens Agents on Runs and whose `a` accepts through team_api.post_answer (Studio drives the run on); GET team/coach
still reads a team run's card. The run is started the way `halo team run` starts it (team_live with team_rig's fakes);
no model is ever called.

Run: python -m tests.test_studio_team
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers import team_rig as R  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_studio_api import _Studio  # noqa: E402

test, TESTS = new_registry()
BOARD = [("GET", "/api/team"), ("POST", "/api/team/validate"), ("GET", "/api/team/board"), ("POST", "/api/team/run"),
         ("POST", "/api/team/answer"), ("POST", "/api/team/stop"), ("GET", "/api/team/blocks"),
         ("GET", "/api/team/blocks/copy/changes"), ("GET", "/api/team/events"), ("POST", "/api/team/init"),
         ("POST", "/api/team/budget")]


def _until(pred, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.05)
    return False


@test
def test_the_board_routes_answer_410_with_where_it_went(ctx: Ctx):
    from halo_harness.studio.team_api import MOVED
    with _Studio() as s:
        R.repo(at=s.state.parent / "proj")
        for method, path in BOARD:
            status, body, _ = s.call(method, path, {} if method == "POST" else None)
            ctx.check(f"{method} {path}: 410 and the line, got {status} {body}", status == 410 and body.get("error") == MOVED
                      and body.get("moved") == "agents/runs")
        ctx.check("the line says where it went and what stays", MOVED.startswith("Team's board moved into Agents -> Runs")
                  and "halo team" in MOVED)
        ctx.check("no token, no answer", s.call("GET", "/api/team", token="")[0] == 401)


@test
def test_the_team_gate_attention_row_opens_runs_and_accepts(ctx: Ctx):
    """A stage at its gate is a `team_gate` row: `o` opens Agents on Runs, `r` needs a text, `a` accepts through
    team_api.post_answer and the next stage runs."""
    from halo_harness.studio import team_api, team_live
    from halo_harness.team import board as BD
    from halo_harness.team import spec as S
    from halo_harness.team.run import open_run
    fakes = R.Fakes()
    saved = team_api.RUNNER
    team_api.RUNNER = fakes.seams
    try:
        with _Studio() as s:
            root, _state = R.repo(at=s.state.parent / "proj")
            ctx.check("no gate, no team row", not [r for r in s.call("GET", "/api/fleet/attention")[1]["rows"] if r["kind"] == "team_gate"])
            team = S.load_team(root, s.state)
            run_dir = open_run(team, cwd=root, state_dir=s.state)
            team_live.start(team, run_dir, stage="draft", seams=fakes.seams())  # what `halo team run draft` drives
            stages = lambda: [r.get("state") for r in BD.read_board(run_dir).get("stages") or []]  # noqa: E731
            ctx.check("draft gated", _until(lambda: stages()[:1] == ["gated"]))
            rows = []
            ctx.check("the team_gate row lands", _until(lambda: rows.extend(r for r in s.call("GET", "/api/fleet/attention")[1]["rows"]
                                                                            if r["kind"] == "team_gate") or bool(rows)))
            row = rows[0] if rows else {"id": "", "keys": {}, "what": "", "target": {}}
            ctx.check(f"its what, keys and target, got {row}", "stage draft waits at its gate" in row["what"]
                      and row["keys"] == {"a": "accept", "r": "redo", "s": "stop", "o": "open Agents: Runs"} and row["text_for"] == "r"
                      and row["target"]["stage"] == "draft")
            status, got, _ = s.call("POST", "/api/fleet/attention/answer", {"id": row["id"], "key": "o"})
            ctx.check(f"o opens Agents on Runs, got {got}", status == 200
                      and got["open"] == {"section": "agents", "view": "runs", "run": row["target"]["run"], "stage": "draft"})
            ctx.check("r without a text answers 422 (redo takes the instruction)",
                      s.call("POST", "/api/fleet/attention/answer", {"id": row["id"], "key": "r"})[0] == 422)
            status, got, _ = s.call("POST", "/api/fleet/attention/answer", {"id": row["id"], "key": "a"})
            ctx.check(f"a accepts the gate, got {status} {got}", status == 200)
            ctx.check("review runs after it", _until(lambda: stages() == ["done", "done", "pending"]))
            BD.request_stop(run_dir, "enough")
            ctx.check("the runner ends", team_live.wait(root, 8.0))
    finally:
        team_api.RUNNER = saved


@test
def test_the_coach_route(ctx: Ctx):
    """3.0.9.0 R3: GET team/coach?run= -> the coach's card for a team run (the latest when run is empty);
    404 when the repo has no team run. It stays: the coach reads a run, not the board."""
    from tests.helpers.coach_seed import team_run
    with _Studio() as s:
        ctx.check("no team run yet: 404", s.call("GET", "/api/team/coach")[0] == 404)
        run_dir = team_run(s.state.parent / "proj")
        for path in ("/api/team/coach", f"/api/team/coach?run={run_dir.name}"):
            status, data, _ = s.call("GET", path)
            ids = [x["id"] for x in data.get("suggestions") or []]
            ctx.check(f"{path}: the team's cards, got {status} {ids}", status == 200 and data["kind"] == "team"
                      and data["run"] == run_dir.name and "coordination-copy-loops" in ids)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio team tests"))
