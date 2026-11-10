"""halo_harness.studio.team_api -- what is left of `/api/team/...` (Halo 3.0.8.0 R1; 3.3.16.0 R1 "Agents: one section").

The Team section's board went in 3.3.16.0 R1: Team, Roles and Orchestra folded into Agents, and who owns what is a run
plan's detail there (Agents -> Runs: each lane's owns line and its claims). Every route only the board read or wrote --
GET team, POST team/validate, GET team/board, POST team/run, POST team/answer, POST team/stop, GET team/blocks,
GET team/blocks/<id>/changes, GET team/events, POST team/init, POST team/budget -- answers 410 with the line `MOVED`.
`halo team` (team/cli.py: init, validate, status, run, answer, stop, the blocks) runs the team file as before, and
GET team/coach (studio/coach_api.py) still reads a team run's coach card.

What stays here is what the Fleet attention queue answers through (fleet/team_attention.py): a stage at its gate
(`post_answer`, accept / redo / stop, and the runner driven on in Studio's process when none drives the run) and a
stage held at its budget line (studio/team_budget_api.py `post_budget`, which stops through `post_stop`). `RUNNER()`
returns the runner's seams as keywords (spawn, orchestra, dispatch, accept); None = the real ones.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.team import board as BD
from halo_harness.team import spec as S
from halo_harness.studio import team_live as live

RUNNER = None
MOVED = "Team's board moved into Agents -> Runs (a run's plan shows who owns what); halo team runs the team file"


def _bad(lines, status: int = 422):
    lines = [lines] if isinstance(lines, str) else list(lines)
    return status, {"error": lines[0] if lines else "invalid", "problems": lines}


def _team(req):
    """`(team, None)` or `(None, (status, body))`."""
    try:
        team = S.load_team(req.cwd, req.state_dir)
    except ValueError as e:
        return None, _bad(str(e))
    if team is None:
        return None, (404, {"error": f"no team file in {S.team_root(req.cwd)} (halo team init writes .halo/team.yaml)",
                            "found": False})
    return team, None


def _run_dir(req, team, body_run=None):
    ref = body_run or req.query.get("run") or None
    return BD.find_run(Path(team["root"]), ref)


def _publisher(req):
    if req.server is None:
        return None
    from halo_harness.studio.events import bridge_for
    return bridge_for(req.server).publish_local


def _seams() -> dict:
    return dict(RUNNER() or {}) if RUNNER is not None else {}


def post_answer(req):
    """A stage's gate answered (the attention row's a / r / s): accept, redo with its text, or stop."""
    from halo_harness.team.stages import write_answer
    team, err = _team(req)
    if err:
        return err
    run_dir = _run_dir(req, team, req.body.get("run"))
    if run_dir is None:
        return 404, {"error": "no team run yet"}
    ok, message = write_answer(run_dir, str(req.body.get("stage") or ""), str(req.body.get("action") or ""),
                               str(req.body.get("text") or ""))
    if not ok:
        return _bad(message)
    driven = False
    if not live.live_run(team["root"]) and not BD.runner_live(BD.read_board(run_dir)):
        driven = live.start(team, run_dir, seams=_seams(), publish=_publisher(req))
    return 200, {"ok": True, "message": message, "run": run_dir.name, "driven": driven}


def post_stop(req):
    """Stop a team run (a budget hold's s): the stop request, then one tick when nothing drives it."""
    team, err = _team(req)
    if err:
        return err
    run_dir = _run_dir(req, team, req.body.get("run"))
    if run_dir is None:
        return 404, {"error": "no team run yet"}
    if BD.read_board(run_dir).get("state") != "open":
        return _bad(f"run {run_dir.name} is already {BD.read_board(run_dir).get('state')}", 409)
    BD.request_stop(run_dir, str(req.body.get("reason") or "stopped in Studio"))
    if not live.live_run(team["root"]) and not BD.runner_live(BD.read_board(run_dir)):
        from halo_harness.team.run import TeamRunner
        TeamRunner(team, run_dir, cwd=team["root"], **_seams()).tick()
    return 200, {"ok": True, "run": run_dir.name}


def dispatch_team(req):
    """Every /api/team/... route the board used: 410 and where it went (GET team/coach is coach_api's, first)."""
    return 410, {"error": MOVED, "problems": [MOVED], "moved": "agents/runs"}
