"""halo_harness.team.adapters -- the real seams behind team/run.py.

* `spawn_member` -- a fresh `halo -p` in the repo, under the member's lineup
  (`--team <lineup>`) as its alias's bio (`--agent <bio>`), permission mode
  auto, with the stage's `$HALO_TEAM_SCOPE`; the JSON result's text, cost and
  session id come back (orchestra/adapters.py's worker call, one member).
* `run_orchestra` -- a new Orchestra run in the repo with the stage's goal,
  run to its report through orchestra/adapters.py's real adapters.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

MEMBER_TIMEOUT_S = 3600


def member_bio(member: dict, *, cwd=None, state_dir=None) -> Optional[str]:
    """The bio the member's alias names in its lineup, or None."""
    from halo_harness.teams_yaml import resolve_team_template
    try:
        lineup = resolve_team_template(member.get("lineup") or "", cwd=cwd, state_dir=state_dir) or {}
    except Exception:
        return None
    for entry in lineup.get("agents") or []:
        if isinstance(entry, dict) and (entry.get("as") or entry.get("role")) == member.get("role"):
            return entry.get("agent")
    return None


def member_argv(member: dict, prompt: str, bio: Optional[str]) -> list:
    argv = [sys.executable, "-m", "halo_harness", "-p", prompt, "--output-format", "json",
            "--permission-mode", "auto"]
    if member.get("lineup"):
        argv += ["--team", member["lineup"]]
    if bio:
        argv += ["--agent", bio]
    return argv


def spawn_member(member: dict, prompt: str, *, cwd, env: dict, stage: str, run_dir, runner=subprocess.run,
                 timeout_s: int = MEMBER_TIMEOUT_S) -> dict:
    from halo_harness.orchestra.adapters import _last_json, fleet_parent_env
    env = {**env, **fleet_parent_env()}
    argv = member_argv(member, prompt, member_bio(member, cwd=cwd))
    try:
        proc = runner(argv, cwd=str(cwd), env=env, capture_output=True, text=True, encoding="utf-8",
                      errors="replace", timeout=timeout_s, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"`{member['name']}` ran past {timeout_s}s"}
    except OSError as e:
        return {"ok": False, "error": f"could not start `{member['name']}`: {e}"}
    obj = _last_json(proc.stdout or "")
    if obj is None:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        return {"ok": False, "error": f"`{member['name']}` exited {proc.returncode} without a result: {' | '.join(tail)}"}
    return {"ok": not obj.get("is_error"), "text": str(obj.get("result") or ""),
            "cost_usd": float(obj.get("total_cost_usd") or 0.0), "session_id": obj.get("session_id"),
            "error": "" if not obj.get("is_error") else str(obj.get("result") or "member error")[:500]}


def run_orchestra(goal: dict, *, root, stage: str, run_dir, model: Optional[str] = None) -> dict:
    from halo_harness.team.board import log
    return orchestra_run(goal, root, model=model, on_start=lambda rid: log(
        run_dir, "note", f"{stage}: Orchestra run {rid} started", stage=stage, orchestra_run=rid))


def orchestra_run(goal: Optional[dict], root, *, model: Optional[str] = None, on_start=None, run_dir=None,
                  wrap=None, make=None, by: str = "team", on_event=None) -> dict:
    """A new Orchestra run of `goal` in `root`, run to its report (a team stage here, or one a fleet
    member runs for a delegated stage: fleet/mission_stage_run.py, 3.1.2.0 R2). 3.1.8.0 R1 (the
    supervisor): `run_dir` runs that existing run again from its checkpoint (`goal` may be None),
    `wrap(spawn)` guards each lane's worker (supervise/budget.py), `make(run_dir, goal, model)` stands
    in for the real adapters (tests), and the runner beats `<run>/runner.json` while it runs
    (supervise/heartbeat.py)."""
    from halo_harness.orchestra import adapters
    from halo_harness.orchestra.goal import Goal, load_goal, new_run
    from halo_harness.orchestra.run import run
    from halo_harness.supervise.heartbeat import Beat
    if run_dir is not None:
        orch_dir = Path(run_dir)
        g = load_goal(orch_dir / "goal.json")
    else:
        g = Goal.from_dict(goal or {})
        orch_dir = new_run(Path(root), g)
    if on_start is not None:
        on_start(orch_dir.name)
    kwargs = (make or adapters.real_adapters)(orch_dir, g, model)
    if wrap is not None:
        kwargs = dict(kwargs, spawn=wrap(kwargs["spawn"]))
    with Beat(orch_dir, by=by):
        report = run(orch_dir, on_event=on_event, **kwargs)
    ok = report.get("status") == "finished"
    return {"ok": ok, "run_id": orch_dir.name, "cost_usd": float(report.get("cost_usd") or 0.0), "report": report,
            "text": f"Orchestra run {orch_dir.name} {report.get('status')}"
                    + (f": {report.get('stop_reason')}" if report.get("stop_reason") else ""),
            "error": "" if ok else str(report.get("stop_reason") or report.get("status") or "stopped")}
