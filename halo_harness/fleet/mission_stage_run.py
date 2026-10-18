"""halo_harness.fleet.mission_stage_run -- a mission part of kind `orchestra` or
`flow`: a team stage delegated to this harness (Halo 3.1.2.0 R2;
team/remote_stage.py sends it, fleet/mission_worker_run.py runs it).

The part's `run` field says what runs here:

    kind orchestra   run: {goal: {what, done_when, stop_when, workers, files, ...}}
                     -> orchestra.run in this harness's checkout of the part's repo
    kind flow        run: {flow: <name>, inputs: {...}}
                     -> flows.run of that flow (found from the checkout when there is one)

No model session is opened for the part itself: the run's own lead,
workers and steps are the sessions. When it ends the part's hand-back is the
run's one line, `parts/<n>/report.json` is its report.json, and result.json
carries `run_id` and `run_kind` beside the usual fields. `ORCHESTRA(goal,
root)` and `FLOW(name, inputs, cwd)` are the seams (None: team/adapters.py's
`orchestra_run` / `flow_run`); each answers `{ok, text, cost_usd, error,
run_id, report}`.
"""

from __future__ import annotations

import json
import re
from typing import Callable, Optional

from halo_harness.fleet.mission_worker import TaskError

KINDS = ("orchestra", "flow")
ORCHESTRA: Optional[Callable] = None
FLOW: Optional[Callable] = None
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$")


def check_run(kind: str, raw) -> dict:
    """The part's `run` field, cleaned; TaskError naming the first problem."""
    raw = raw if isinstance(raw, dict) else {}
    if kind == "orchestra":
        from halo_harness.orchestra.goal import validate_goal
        goal = raw.get("goal")
        if not isinstance(goal, dict) or not goal:
            raise TaskError("an orchestra part carries run.goal {what, done_when, stop_when, ...}")
        problems = validate_goal(goal)
        if problems:
            raise TaskError(f"the stage's goal: {problems[0]}")
        return {"goal": dict(goal)}
    name = str(raw.get("flow") or "")
    if not _NAME.match(name):
        raise TaskError(f"a flow part names its flow (letters, digits, - _ .), got {name!r}")
    inputs = raw.get("inputs") if isinstance(raw.get("inputs"), dict) else {}
    return {"flow": name, "inputs": {str(k)[:80]: v for k, v in list(inputs.items())[:50]}}


def what(fields: dict) -> str:
    """One line for the owner's card: what the part runs here."""
    run = fields.get("run") if isinstance(fields.get("run"), dict) else {}
    if fields.get("kind") == "orchestra":
        return f"an Orchestra run: {str((run.get('goal') or {}).get('what') or '')[:120]}"
    return f"flow {run.get('flow')}"


def run(worker) -> dict:
    """The part's run, on `worker`'s folder (the checkout for an orchestra part); its report kept for the hub."""
    f = worker.f
    spec = f.get("run") or {}
    if f["kind"] == "orchestra":
        from halo_harness.team.adapters import orchestra_run
        out = (ORCHESTRA or (lambda goal, root: orchestra_run(goal, root)))(spec["goal"], worker.cwd)
    else:
        from halo_harness.team.adapters import flow_run
        out = (FLOW or (lambda name, inputs, cwd: flow_run(name, inputs, cwd)))(spec["flow"], spec.get("inputs") or {},
                                                                                  worker.cwd)
    out = dict(out or {})
    worker.run_id = out.get("run_id")
    if worker.folder is not None and isinstance(out.get("report"), dict):
        from halo_harness.fleet import mission_store as S
        S.write_text(worker.folder, f"parts/{f['part']}/report.json", json.dumps(out["report"], indent=2, default=str))
        worker.report = True
    return out


def place(worker) -> None:
    """Where the part runs: an orchestra part in this harness's checkout of the repo; a flow part there
    when the checkout is here, else in the mission folder."""
    if worker.f["kind"] == "orchestra" and worker.checkout is None:
        worker.checkout = worker._find_repo(str(worker.f.get("repo") or ""))
    elif worker.f["kind"] == "flow" and worker.checkout is None and worker.f.get("repo"):
        try:
            worker.checkout = worker._find_repo(str(worker.f["repo"]))
        except TaskError:
            worker.checkout = None
