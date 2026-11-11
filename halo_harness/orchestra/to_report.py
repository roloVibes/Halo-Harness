"""halo_harness.orchestra.to_report -- one Orchestra run, run to its report (Halo 3.4.0.0 B: moved here from the
team package, which left with the team file; the supervisor and a fleet mission's orchestra part call it).

`orchestra_run(goal, root, ...)` starts a new run of `goal` in `root` (or, with `run_dir`, runs that existing run
again from its checkpoint) through orchestra/adapters.py's real adapters and answers `{ok, run_id, cost_usd,
report, text, error}`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def orchestra_run(goal: Optional[dict], root, *, model: Optional[str] = None, on_start=None, run_dir=None,
                  wrap=None, make=None, by: str = "orchestra", on_event=None) -> dict:
    """A new Orchestra run of `goal` in `root`, run to its report (a fleet member runs one for a mission's orchestra
    part: fleet/mission_stage_run.py, 3.1.2.0 R2). 3.1.8.0 R1 (the supervisor): `run_dir` runs that existing run
    again from its checkpoint (`goal` may be None), `wrap(spawn)` guards each lane's worker (supervise/budget.py),
    `make(run_dir, goal, model)` stands in for the real adapters (tests), and the runner beats `<run>/runner.json`
    while it runs (supervise/heartbeat.py)."""
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
