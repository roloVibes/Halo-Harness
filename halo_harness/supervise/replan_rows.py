"""halo_harness.supervise.replan_rows -- the owner's answer to a replan row and
the "replanned N times" line (Halo 3.1.8.0 R2, docs/SUPERVISE.md "Replanning").

    goal_plan (target.replan)  a apply the new plan | r keep the old plan (why) | o open the plan
    goal_replan                a apply the new plan (replan.plan.json, the owner's edit included, checked
                               again) | r keep the old plan (why) | s stop the goal | o open the plan

`decide(sup, row, key, text)` is called by apply.decision for both. An apply
that fails the check reopens the row with the problems; an apply or a keep
re-queues the parked goal, which resumes from its checkpoint (the old lanes
unchanged on a keep). A row whose goal moved on meanwhile (`halo goal resume`,
a cancel) is closed and changes nothing. `line(goal)` is what `halo supervise
status`, `halo goal show` and the run report print.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from halo_harness.supervise import decisions, queue
from halo_harness.supervise.replan import _write, apply_checked, episode, event, record

WORDS = {"applied": "applied", "rejected": "kept the old plan", "review": "waits for your review",
         "parked": "the lead's plan failed the check", "unchanged": "no change", "stopped": "the lead stopped the run",
         "pausing": "pausing", "asking": "asking the lead"}


def proposal_of(run_dir) -> Optional[dict]:
    """`<run>/replan.plan.json` as an answer (`{"jobs": [...]}`), the owner's edit included."""
    from halo_harness.orchestra import jsonl
    data = jsonl.read_json(Path(run_dir) / "replan.plan.json", None)
    return data if isinstance(data, dict) else None


def approve(state_dir, gid: str, run_dir, by: str) -> list:
    """The owner's a: replan.plan.json checked again and applied; the problems ([] = applied)."""
    from halo_harness.supervise import replan_plan
    checked = replan_plan.check(run_dir, proposal_of(run_dir) or {}, state_dir=state_dir)
    if checked.problems:
        return checked.problems
    apply_checked(state_dir, gid, run_dir, checked, by or "owner")
    return []


def reject(state_dir, gid: str, run_dir, why: str, by: str) -> None:
    """The owner's r: the old plan resumes unchanged; the why goes to events.jsonl."""
    rec = record(run_dir)
    n = int(rec.get("n") or 0)
    rec.update(state="rejected", settled=round(time.time(), 3), by=by, note=why)
    _write(run_dir, rec)
    episode(state_dir, gid, n, state="rejected", settled=rec["settled"], by=by, note=why)
    event(run_dir, "replan_rejected", f"#{n} by {by or 'the owner'}: {why}; the old plan resumes", n=n, by=by,
          why=why, moves=rec.get("moves") or [])


def decide(sup, row: dict, key: str, text: str) -> None:
    sd, gid = sup.state_dir, row["goal"]
    run_dir = Path((row.get("target") or {}).get("run_dir") or "")
    goal = queue.load(sd, gid)
    by = str((row.get("answer") or {}).get("by") or "") or "the owner"
    if goal is None:
        return decisions.close(sd, row["id"], "the goal is gone")
    if goal.get("state") != "parked" or int(record(run_dir).get("n") or 0) != int((row.get("target") or {}).get("replan") or 0):
        return decisions.close(sd, row["id"], f"the goal moved on (it is {goal.get('state')}): nothing changed")
    if key == "s":
        reject(sd, gid, run_dir, text or "stopped from Attention", by)
        queue.set_state(sd, gid, "stopped", "stopped from Attention")
        return decisions.close(sd, row["id"], "stopped")
    if key == "a":
        problems = approve(sd, gid, run_dir, by)
        if problems:
            decisions.reopen(sd, row["id"], "the new plan does not pass the check: " + "; ".join(problems))
            return
        why = "replan applied"
    elif key == "r":
        reject(sd, gid, run_dir, text or "kept the old plan from Attention", by)
        why = "replan rejected: the old plan resumes"
    else:
        return
    queue.set_state(sd, gid, "queued", why, started=None, time_stop=False)
    decisions.close(sd, row["id"], why)


def asked(goal: dict) -> list:
    """The goal's replans that asked the lead (a pause the run outran is not one)."""
    return [e for e in goal.get("replans") or [] if e.get("state") != "dropped"]


def line(goal: dict) -> str:
    """'replanned N times (forecast: applied; returns: kept the old plan)', '' for none."""
    eps = asked(goal)
    if not eps:
        return ""
    why = "; ".join(f"{'+'.join(e.get('why') or []) or 'drift'}: {WORDS.get(e.get('state'), e.get('state') or '?')}"
                    for e in eps)
    return f"replanned {len(eps)} time{'s' if len(eps) != 1 else ''} ({why})"
