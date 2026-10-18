"""halo_harness.studio.team_budget_api -- `POST /api/team/budget`, the answer
to a stage held at its budget line (Halo 3.1.2.0 R2; team/budget.py,
docs/TEAM.md "Budgets"). studio/team_api.py routes it; the Attention
queue's `team_budget` row (fleet/team_attention.py) calls it.

    POST team/budget {stage, action: skip | stop, run?}
        skip  -> {ok, message, run}   the stage is skipped in this run
        stop  -> {ok, message, run}   the run stops (as POST team/stop)
        404 no run / 409 the stage is not held / 422 an action it does not take

Raise is not an action here: the budget lives in the team file, so Raise
opens it (edit `budget_usd`, then run the stage again: the runner reads
the file each time).
"""

from __future__ import annotations


def post_budget(req):
    from halo_harness.studio.team_api import _bad, _run_dir, _team, post_stop
    from halo_harness.team import budget
    team, err = _team(req)
    if err:
        return err
    body = req.body if isinstance(req.body, dict) else {}
    sid, action = str(body.get("stage") or ""), str(body.get("action") or "")
    if action not in ("skip", "stop"):
        return _bad(f"the answer to a budget hold is skip or stop (raise: edit budget_usd in {team['path']}), "
                    f"got {action!r}")
    run_dir = _run_dir(req, team, body.get("run"))
    if run_dir is None:
        return 404, {"error": "no team run yet"}
    if not any(h.get("stage") == sid for h in budget.held(run_dir)):
        return _bad(f"stage {sid!r} of run {run_dir.name} is not held at a budget line", 409)
    if action == "stop":
        req.body = {"run": run_dir.name, "reason": f"stopped at stage {sid}'s budget line"}
        return post_stop(req)
    ok, message = budget.skip(run_dir, sid, by="Studio")
    return (200 if ok else 409), {"ok": ok, "message": message, "run": run_dir.name}
