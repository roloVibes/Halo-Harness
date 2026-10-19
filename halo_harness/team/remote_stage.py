"""halo_harness.team.remote_stage -- an orchestra stage that runs on a
fleet member (Halo 3.1.2.0 R2; team/run_stage.py starts it, docs/TEAM.md).

A stage `kind: orchestra` with `harness: <member>` goes to
that member the way a delegated agent member does (team/delegate.py ->
fleet/mission_dispatch.py): a one-part mission whose part carries the run
(`{goal}`). The
member runs `orchestra.run` locally (fleet/mission_stage_run.py)
and hands back `result.json`, its report and a hand-back line. The stage's
row follows the part:

    asked    -> the stage waits on the owner's card (its unit `waiting`)
    running  -> it runs on the member
    done | failed -> the stage finishes with the run's report in stages/<id>/report.json

The row's `remote` field is `{harness, kind, mission, part_state, run}` (the
remote run id once it is known); the board shows the harness chip and that
run id. A refused dispatch (403, no hub, the member offline) fails the
stage with the reason.
"""

from __future__ import annotations

from halo_harness.team import board as BD

KEY = "@run"


def task_of(runner, stage: dict, redo: str = "") -> dict:
    """What the member runs: the stage's goal (with the team's defaults)."""
    from halo_harness.team.resolve import goal_for_stage
    kind = stage["kind"]
    base = {"team": runner.team["name"], "run": runner.run_dir.name, "stage": stage["id"], "kind": kind,
            "title": f"team {runner.team['name']} stage {stage['id']} ({kind})", "repo": repo_name(runner.root)}
    goal = goal_for_stage(runner.team, stage, runner.root)
    if redo:
        goal = dict(goal, what=f"{goal.get('what') or ''}\n\nTHE LEAD ASKED FOR A REDO: {redo}".strip())
    return dict(base, goal=goal, brief=f"Run the Orchestra goal of stage {stage['id']}: {goal.get('what')}")


def repo_name(root) -> str:
    """The team repo's name as a member's checkout of it reports it (its origin's name, else the folder)."""
    try:
        from halo_harness.remote.fleet_identity import project
        return str(project(str(root)).get("repo") or "") or str(root).replace("\\", "/").rstrip("/").split("/")[-1]
    except Exception:
        return str(root).replace("\\", "/").rstrip("/").split("/")[-1]


def send(runner, sid: str, stage: dict, redo: str = "") -> None:
    from halo_harness.team.run_stage import finish
    harness = str(stage.get("harness"))
    status, body = runner.delegate().send_run(harness, task_of(runner, stage, redo))
    body = body if isinstance(body, dict) else {}
    if status in (200, 202):
        handle = dict(body.get("handle") or body, member=KEY, harness=harness)
        runner.live[sid] = {"remote": True, "order": [], "lead": KEY, "workers": [], "results": {},
                            "handles": {KEY: handle}, "redo": redo}
        part = "running" if status == 200 else "asked"
        BD.set_stage(runner.run_dir, sid, waiting=_line(stage["kind"], harness, part),
                     remote={"harness": harness, "kind": stage["kind"], "mission": handle.get("mission"),
                             "part_state": part, "run": None})
        BD.log(runner.run_dir, "note", f"{sid}: the {stage['kind']} run goes to {harness} ({part})", stage=sid,
               status=status, harness=harness, mission=handle.get("mission"))
        return None
    reason = str(body.get("error") or f"status {status}")
    word = "refused" if status == 403 else "could not take the stage"
    return finish(runner, sid, {"ok": False, "error": f"{harness} {word}: {reason}"})


def _line(kind: str, harness: str, part: str) -> str:
    return (f"{kind} run asked; the owner's card is open on {harness}" if part == "asked"
            else f"{kind} run running on {harness}")


def waiting(runner, sid: str, handle: dict, part: str) -> None:
    """The part is asked or running on the member: the row says so."""
    row = runner.row(sid)
    remote = dict(row.get("remote") or {}, part_state=part)
    BD.set_stage(runner.run_dir, sid, waiting=_line(remote.get("kind") or "", handle.get("harness") or "", part),
                 remote=remote)


def step(runner, sid: str) -> None:
    """The member's result is in: the stage finishes with its report."""
    from halo_harness.team.run_stage import finish
    live = runner.live.get(sid)
    if live is None or KEY not in live["results"] or live["handles"]:
        return None
    runner.live.pop(sid, None)
    res = live["results"][KEY]
    row = runner.row(sid)
    remote = dict(row.get("remote") or {}, part_state=res.get("state") or ("done" if res.get("ok") else "failed"),
                  run=res.get("run_id"))
    BD.set_stage(runner.run_dir, sid, remote=remote)
    if isinstance(res.get("report"), dict):
        BD.write_stage_file(runner.run_dir, sid, "report.json", res["report"])
    kind = remote.get("kind") or "orchestra"
    refs = {f"{kind}_run": res.get("run_id"), "harness": remote.get("harness"), "mission": remote.get("mission")}
    return finish(runner, sid, dict(res, refs=refs))
