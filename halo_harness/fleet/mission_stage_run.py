"""halo_harness.fleet.mission_stage_run -- a mission part of kind `orchestra`:
a team stage delegated to this harness (Halo 3.1.2.0 R2;
team/remote_stage.py sends it, fleet/mission_worker_run.py runs it).

The part's `run` field says what runs here:

    kind orchestra   run: {goal: {what, done_when, stop_when, workers, files, ...}}
                     -> orchestra.run in this harness's checkout of the part's repo

No model session is opened for the part itself: the run's own lead and
workers are the sessions. When it ends the part's hand-back is the run's
one line, `parts/<n>/report.json` is its report.json, and result.json
carries `run_id` and `run_kind` beside the usual fields. `ORCHESTRA(goal,
root)` is the seam (None: team/adapters.py's `orchestra_run`); it answers
`{ok, text, cost_usd, error, run_id, report}`.
"""

from __future__ import annotations

import json
from typing import Callable, Optional

from halo_harness.fleet.mission_worker import TaskError

KINDS = ("orchestra",)
ORCHESTRA: Optional[Callable] = None


def check_run(kind: str, raw) -> dict:
    """The part's `run` field, cleaned; TaskError naming the first problem."""
    from halo_harness.orchestra.goal import validate_goal
    raw = raw if isinstance(raw, dict) else {}
    goal = raw.get("goal")
    if not isinstance(goal, dict) or not goal:
        raise TaskError("an orchestra part carries run.goal {what, done_when, stop_when, ...}")
    problems = validate_goal(goal)
    if problems:
        raise TaskError(f"the stage's goal: {problems[0]}")
    return {"goal": dict(goal)}


def what(fields: dict) -> str:
    """One line for the owner's card: what the part runs here."""
    run = fields.get("run") if isinstance(fields.get("run"), dict) else {}
    return f"an Orchestra run: {str((run.get('goal') or {}).get('what') or '')[:120]}"


def run(worker) -> dict:
    """The part's run, in the checkout; its report kept for the hub."""
    from halo_harness.team.adapters import orchestra_run
    f = worker.f
    spec = f.get("run") or {}
    out = (ORCHESTRA or (lambda goal, root: orchestra_run(goal, root)))(spec["goal"], worker.cwd)
    out = dict(out or {})
    worker.run_id = out.get("run_id")
    if worker.folder is not None and isinstance(out.get("report"), dict):
        from halo_harness.fleet import mission_store as S
        S.write_text(worker.folder, f"parts/{f['part']}/report.json", json.dumps(out["report"], indent=2, default=str))
        worker.report = True
    return out


def place(worker) -> None:
    """Where the part runs: this harness's checkout of the repo."""
    if worker.checkout is None:
        worker.checkout = worker._find_repo(str(worker.f.get("repo") or ""))
