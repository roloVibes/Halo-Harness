"""halo_harness.workflows.runtime -- a workflow lane's stage, each time its
worker is about to run (Halo 3.2.0.0 R5; called from orchestra/workers.py
`run_lane`, which runs every pass: the first, a retry, a piece sent back).

    stage_text, early = stage(run_dir, goal, lane)

* `stage_text` joins the worker's prompt: the stage, the item, its brief (the
  lead's refinement, pinned.py), what it is verified by and the schema its
  artifact must match.
* `early` is a result the worker's spawn is NOT called for (None: run it):
  - the stage's `when` names an upstream output that is false: the lane is
    `skipped` (`{ok: True, text: ""}`, its `skipped` reason on the lane, a
    `state` line);
  - the stage spent its `budget_usd` already: `STOP: budget: ...` (the run stops);
  - `after_event` never came within the stage's `timeout_s` (or a stop was asked).
* `lane.timeout_s` is the stage's `timeout_s` (orchestra/adapters.py spawn_worker reads it).
Not a workflow goal: `("", None)`.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from halo_harness.orchestra import events as run_events

EVENT_POLL_S = 0.5


def _stage_row(goal, stage_id: str) -> dict:
    return next((s for s in (goal.workflow or {}).get("stages") or [] if s.get("id") == stage_id), {})


def stage_lanes(run_dir, goal, stage_id: str) -> list:
    from halo_harness.orchestra.lanes import list_lanes
    jobs = set(_stage_row(goal, stage_id).get("jobs") or [])
    return [lane for lane in list_lanes(run_dir) if lane.job.id in jobs]


def spent(run_dir, goal, stage_id: str) -> float:
    return sum(lane.cost_usd for lane in stage_lanes(run_dir, goal, stage_id))


def _text(run_dir, goal, lane, row: dict, st: dict) -> str:
    from halo_harness.workflows.pinned import brief_of
    wf = goal.workflow or {}
    lines = [f"Your stage of the workflow {wf.get('ref')}: {st.get('title') or row.get('stage')} (stage {row.get('stage')})"
             + (f", for {row['item']}" if row.get("item") else "") + "."]
    brief = brief_of(run_dir, goal, lane.job.id)
    if brief:
        lines.append(f"Brief: {brief}")
    if not lane.job.claims:
        lines.append("This stage claims no unit of the repo: edit no file of it; hand on what the stage gives (below).")
    verify = st.get("verify") if isinstance(st.get("verify"), dict) else {}
    if verify.get("test"):
        lines.append(f"The gate verifies the stage with `{verify['test']}`.")
    if verify.get("evidence"):
        lines.append("The gate reads this evidence, not your reply: " + ", ".join(verify["evidence"]) + ".")
    for name, out in (wf.get("outputs") or {}).items():
        if out.get("from") == row.get("stage") and out.get("schema"):
            lines.append(f"Your {name} is checked against the {out['schema']} schema: save it as JSON that matches it "
                         "(a mismatch comes back to you with the problems).")
    return "\n".join(lines)


def _wait_event(run_dir, goal, lane, name: str, timeout_s, clock: Callable) -> str:
    """'' once `name` (<pack>:<kind>) was published after the run started; else why not."""
    from halo_harness.orchestra.goal import run_meta
    from halo_harness.orchestra.run import stop_requested
    from halo_harness.packs.events_log import since
    created = float(run_meta(run_dir).get("created") or 0)
    if since(name, created):
        return ""
    lane.set_state("waiting", f"waits for the event {name}", clock=clock)
    run_events.log(run_dir, "state", f"lane {lane.n} waits for the event {name}", lane=lane.n, step=f"worker-{lane.n}")
    end = time.monotonic() + float(timeout_s or 3600)
    while time.monotonic() < end:
        if since(name, created):
            run_events.log(run_dir, "state", f"lane {lane.n}: the event {name} came", lane=lane.n)
            return ""
        if stop_requested(run_dir):
            return f"stopped while it waited for the event {name}"
        time.sleep(EVENT_POLL_S)
    return f"the event {name} did not come within {int(float(timeout_s or 3600))}s"


def stage(run_dir, goal, lane, *, clock: Callable = time.time) -> "tuple[str, object]":
    wf = getattr(goal, "workflow", None) or {}
    row = (wf.get("jobs") or {}).get(lane.job.id)
    if not row:
        return "", None
    run_dir = Path(run_dir)
    st = _stage_row(goal, row.get("stage"))
    lane.timeout_s = int(st["timeout_s"]) if isinstance(st.get("timeout_s"), int) else 0
    budget = st.get("budget_usd")
    if isinstance(budget, (int, float)) and spent(run_dir, goal, row["stage"]) >= float(budget):
        return "", {"ok": False, "error": f"STOP: budget: stage {row['stage']} spent "
                                          f"${spent(run_dir, goal, row['stage']):.4f} of its ${float(budget):.4f}"}
    when = st.get("when") if isinstance(st.get("when"), dict) else {}
    if "output" in when and not lane.data().get("skipped"):
        from halo_harness.workflows.conditions import on_output
        ok, why = on_output(when, run_dir, stage_lanes(run_dir, goal, str(when["output"]).partition(".")[0]))
        if not ok:
            lane.update(skipped=why)
            run_events.log(run_dir, "state", f"worker-{lane.n} skipped: stage {row['stage']} {why}", lane=lane.n,
                           step=f"worker-{lane.n}", state="skipped", stage=row["stage"])
            return "", {"ok": True, "text": ""}
    if lane.data().get("skipped"):
        return "", {"ok": True, "text": ""}
    if st.get("after_event"):
        why = _wait_event(run_dir, goal, lane, str(st["after_event"]), st.get("timeout_s"), clock)
        if why:
            return "", {"ok": False, "error": f"STOP: {why}"}
    return _text(run_dir, goal, lane, row, st), None
