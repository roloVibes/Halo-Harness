"""halo_harness.studio.team_api -- `/api/team/...`, Studio's Team backend
(Halo 3.0.8.0 round R1; round R2 draws the Team tab on it). Same loopback /
origin / token guard as every Studio route; the team is the one of the repo
that holds Studio's folder (`req.cwd`), docs/TEAM.md.

    GET  team                           {found, path, source, root, team, problems, preflight, run, live}
    POST team/validate {yaml?}          {ok, problems, preflight, team}  (the file, or the YAML text given)
    GET  team/board?run=                {run, board, status, live}  (no run yet: the stages, all pending)
    POST team/run {stage?, force?, new?}  202 {run, stage, started}
                                        422 {error, problems} on a problem in the file,
                                        422 {error, problems, preflight: true} when the preflight blocks,
                                        409 {error, run} while another process drives the run
    POST team/answer {stage, action, text?, run?}  {ok, message, run, driven}
    POST team/stop {reason?, run?}      {ok, run}
    GET  team/blocks                    {blocks: [<block status>]}
    GET  team/blocks/<id>/changes?since=N  {block, changes, next}
    GET  team/events?since=N&run=       {run, events, next}
    POST team/init                      {ok, written, path}; 409 when a file exists (R2, team_init_api.py)

Board, gate, claim and change events go out on `/api/events` as `team` frames (studio/team_live.py).
`RUNNER()` returns the runner's seams as keywords (`spawn`, `orchestra`, `flow`, `dispatch`,
`accept`); None = the real ones (team/run.py); tests set it to the fakes.
"""

from __future__ import annotations

import re
from pathlib import Path

from halo_harness.team import blocks as B
from halo_harness.team import board as BD
from halo_harness.team import spec as S
from halo_harness.studio.team_init_api import post_init
from halo_harness.studio import team_live as live

RUNNER = None


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


def _findings(team, req) -> list:
    from halo_harness.team.validate import preflight_findings
    return preflight_findings(team, cwd=team["root"], state_dir=req.state_dir)


def get_team(req):
    try:
        team = S.load_team(req.cwd, req.state_dir)
    except ValueError as e:
        return 200, {"found": True, "team": None, "problems": [str(e)], "preflight": [], "run": None, "live": False}
    if team is None:
        root = S.team_root(req.cwd)
        return 200, {"found": False, "path": str(S.repo_team_path(root)), "source": None, "root": str(root),
                     "team": None, "problems": [], "preflight": [], "run": None, "live": False}
    run_dir = BD.latest_run(Path(team["root"]))
    return 200, {"found": True, "path": team["path"], "source": team["source"], "root": team["root"], "team": team,
                 "problems": S.validate_team(team, cwd=team["root"], state_dir=req.state_dir, preflight=False),
                 "preflight": _findings(team, req), "run": run_dir.name if run_dir else None,
                 "live": bool(live.live_run(team["root"]))}


def post_validate(req):
    text = req.body.get("yaml")
    if isinstance(text, str):
        try:
            team = S.normalize(S.parse_yaml(text, "the YAML"))
        except ValueError as e:
            return 200, {"ok": False, "problems": [str(e)], "preflight": [], "team": None}
        team.update(root=str(S.team_root(req.cwd)))
        team["name"] = team["name"] or Path(team["root"]).name
    else:
        team, err = _team(req)
        if err:
            return err
    problems = S.validate_team(team, cwd=team["root"], state_dir=req.state_dir, preflight=False)
    findings = _findings(team, req)
    from halo_harness.lineup_preflight import blocking
    return 200, {"ok": not problems and not blocking(findings), "problems": problems, "preflight": findings,
                 "team": team}


def get_board(req):
    from halo_harness.team.cli_run import status_of
    from halo_harness.team.run import rows_for
    team, err = _team(req)
    if err:
        return err
    run_dir = _run_dir(req, team)
    if run_dir is None:
        if req.query.get("run"):
            return 404, {"error": f"no team run {req.query['run']!r}"}
        board = {"run": None, "team": team["name"], "state": "none", "stages": rows_for(team, state_dir=req.state_dir)}
        return 200, {"run": None, "board": board, "status": None, "live": False}
    return 200, {"run": run_dir.name, "board": BD.read_board(run_dir), "status": status_of(run_dir),
                 "live": live.live_run(team["root"]) == run_dir.name}


def post_run(req):
    from halo_harness.lineup_preflight import blocking, refusal_body
    from halo_harness.team.run import open_run
    team, err = _team(req)
    if err:
        return err
    body = req.body
    problems = S.validate_team(team, cwd=team["root"], state_dir=req.state_dir, preflight=False)
    if problems:
        return _bad(problems)
    stage = str(body.get("stage") or "") or None
    if stage and S.stage_by_id(team, stage) is None:
        return _bad(f"no stage {stage!r} (stages: {', '.join(s['id'] for s in team['workflow']['stages'])})")
    if not body.get("force"):
        findings = _findings(team, req)
        if blocking(findings):
            return 422, refusal_body(findings, what=f"team {team['name']}")
    running = live.live_run(team["root"])
    if running:
        if stage and live.request(team["root"], stage):
            return 202, {"run": running, "stage": stage, "started": False, "queued": True}
        return 409, {"error": f"run {running} is live in Studio: name the stage to start", "run": running}
    run_dir = open_run(team, new=bool(body.get("new")), cwd=team["root"], state_dir=req.state_dir)
    board = BD.read_board(run_dir)
    if BD.runner_live(board):
        return 409, {"error": f"run {run_dir.name} is driven by another process (pid {board['runner'].get('pid')})",
                     "run": run_dir.name}
    if stage is None:
        stage = next((r["id"] for r in board.get("stages") or [] if r.get("state") == "pending"
                      and S.parse_trigger(r.get("trigger"))[0] == "manual"), None)
    started = live.start(team, run_dir, stage=stage, seams=_seams(), publish=_publisher(req))
    return 202, {"run": run_dir.name, "stage": stage, "started": started}


def post_answer(req):
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


def get_blocks(req):
    team, err = _team(req)
    return err or (200, {"blocks": B.all_status(team)})


def _since(req):
    try:
        return max(0, int(req.query.get("since") or 0)), None
    except ValueError:
        return 0, _bad("since is a whole number (the count of lines already seen)")


def get_changes(req):
    team, err = _team(req)
    if err:
        return err
    block = S.block_by_id(team, req.params["block"])
    if block is None:
        return 404, {"error": f"no block {req.params['block']!r}"}
    since, err = _since(req)
    if err:
        return err
    lines = B.changes(Path(team["root"]), block, since)
    return 200, {"block": block["id"], "changes": lines, "next": since + len(lines)}


def get_events(req):
    team, err = _team(req)
    since, err = (0, err) if err else _since(req)
    if err:
        return err
    run_dir = _run_dir(req, team)
    if run_dir is None:
        return 200, {"run": None, "events": [], "next": 0}
    events = BD.read_events(run_dir, since=since)
    return 200, {"run": run_dir.name, "events": events, "next": since + len(events)}


ROUTES = [
    ("GET", r"^team$", get_team), ("POST", r"^team/validate$", post_validate), ("GET", r"^team/board$", get_board),
    ("POST", r"^team/run$", post_run), ("POST", r"^team/answer$", post_answer), ("POST", r"^team/stop$", post_stop),
    ("GET", r"^team/blocks$", get_blocks), ("GET", r"^team/blocks/(?P<block>[A-Za-z0-9_-]+)/changes$", get_changes),
    ("GET", r"^team/events$", get_events), ("POST", r"^team/init$", post_init)]


def dispatch_team(req):
    for method, pattern, fn in ROUTES:
        m = re.match(pattern, req.path)
        if m and method == req.method:
            req.params = dict(m.groupdict())
            return fn(req)
    if any(re.match(p, req.path) for _, p, _ in ROUTES):
        return 405, {"error": f"/api/{req.path} answers another method (docs/TEAM.md lists the routes)"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
