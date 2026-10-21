"""halo_harness.supervise.replan_ask -- the replan asked in the goal's own run
thread (Halo 3.1.8.0 R2; never the tick): `settle(...)` runs after the run
stopped on its replan pause. It asks the run's lead (orchestra/adapters.py's
one-shot path, runner.ADAPTERS in tests) with replan_prompt.py's prompt, checks
the answer (replan_plan.py) and asks once more with the problems; then it
applies the plan (auto), parks a goal_plan row with the diff (review), or parks
a goal_replan row with the problems (a second failed check). Each lead call's
cost and session go on split.json's lead line, so the run's spend counts them.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from halo_harness.orchestra import jsonl
from halo_harness.supervise import decisions, queue
from halo_harness.supervise.replan import PLAN, _write, apply_checked, drop, episode, event, mode, record


def _outcome(run_dir, state: str, why: str, failure=None) -> dict:
    from halo_harness.supervise.budget import run_spent
    return {"state": state, "why": why, "cost_usd": run_spent(run_dir), "failure": failure}


def _lead(run_dir, goal: dict, make) -> Callable:
    from halo_harness.orchestra import adapters
    from halo_harness.orchestra.goal import load_goal
    return (make or adapters.real_adapters)(Path(run_dir), load_goal(Path(run_dir) / "goal.json"),
                                            goal.get("model") or None)["model_calls"]


def _ask(run_dir, call: Callable, prompt: str) -> "tuple[str, float]":
    """One lead call; its cost and session go on split.json's lead line (the run's spend counts them)."""
    from halo_harness.orchestra.split import _call
    try:
        text, cost, sid = _call(call, prompt)
    except Exception as e:  # the lead's call failed: it reads as a bad answer
        return f"(the lead's call failed: {type(e).__name__}: {e})", 0.0
    split = jsonl.read_json(Path(run_dir) / "split.json", {}) or {}
    split["lead_cost_usd"] = round(float(split.get("lead_cost_usd") or 0.0) + cost, 6)
    split["lead_sessions"] = list(split.get("lead_sessions") or []) + ([sid] if sid else [])
    jsonl.write_json(Path(run_dir) / "split.json", split)
    return text, cost


def settle(state_dir, goal: dict, run_dir, cfg: dict, report: dict, make=None):
    """After the run stopped on its replan pause. "resume": run it again from its checkpoint (applied, or no
    change); None: the pause did not apply (read the report as always); else the goal's outcome."""
    from halo_harness.orchestra.goal import load_goal
    from halo_harness.orchestra.split import parse_answer
    from halo_harness.supervise import replan_plan, replan_prompt
    from halo_harness.supervise.replan_moves import diff_lines
    run_dir, gid = Path(run_dir), goal["id"]
    rec, now_goal = record(run_dir), queue.load(state_dir, gid) or goal
    if report.get("status") == "finished" or now_goal.get("state") != "running":
        drop(state_dir, gid, run_dir, "the run finished first" if report.get("status") == "finished" else "the goal moved")
        return None
    if now_goal.get("time_stop"):  # supervise.max_minutes stopped it too: the time limit wins
        from halo_harness.supervise.runner import failure
        drop(state_dir, gid, run_dir, "the goal's time limit came first")
        return _outcome(run_dir, "parked", "time", failure("time", run_dir, "time: past the goal's max_minutes"))
    n, drifts = int(rec.get("n") or 0), list(rec.get("why") or [])
    rec.update(state="asking")
    _write(run_dir, rec)
    call, g, problems, spent, checked, data = _lead(run_dir, goal, make), load_goal(run_dir / "goal.json"), [], 0.0, None, None
    for attempt in (1, 2):
        text, cost = _ask(run_dir, call, replan_prompt.prompt(run_dir, g, drifts, problems or None))
        spent += cost
        if attempt == 1:
            event(run_dir, "replan_asked", f"#{n} the lead is asked for the lanes left: "
                  + "; ".join(f"{d.get('kind')}: {d.get('text')}" for d in drifts), n=n, why=drifts, cost_usd=cost)
        data = parse_answer(text)
        if isinstance(data, dict) and str(data.get("stop") or "").strip():
            from halo_harness.supervise.runner import failure
            reason = f"the lead stopped the run: {str(data['stop']).strip()}"
            rec.update(state="stopped", cost_usd=round(spent, 6), note=reason)
            _write(run_dir, rec)
            episode(state_dir, gid, n, state="stopped", settled=round(time.time(), 3), note=reason)
            return _outcome(run_dir, "stopped", "stop when", failure("worker", run_dir, reason))
        checked = replan_plan.check(run_dir, data, state_dir=state_dir)
        if not checked.problems:
            break
        problems = checked.problems
        event(run_dir, "replan_answer", f"#{n} answer {attempt} fails the check: " + "; ".join(problems),
              n=n, attempt=attempt, problems=problems)
    jsonl.write_json(run_dir / PLAN, {"jobs": (data or {}).get("jobs") if isinstance(data, dict) else [],
                                      "why": str((data or {}).get("why") or "") if isinstance(data, dict) else ""})
    rec.update(cost_usd=round(spent, 6), problems=checked.problems, moves=checked.moves)
    if checked.problems:
        rec.update(state="parked")
        _write(run_dir, rec)
        episode(state_dir, gid, n, state="parked", note="; ".join(checked.problems)[:300])
        decisions.park(state_dir, "goal_replan", gid, f"replan-{n}", f"Goal {gid}: the lead's new plan failed the "
                       "check twice", "; ".join(checked.problems), run_dir=str(run_dir), replan=n)
        return _outcome(run_dir, "parked", "replan")
    if not checked.moves:
        rec.update(state="unchanged", settled=round(time.time(), 3))
        _write(run_dir, rec)
        episode(state_dir, gid, n, state="unchanged", settled=rec["settled"])
        event(run_dir, "replan_applied", f"#{n}: the lead kept every lane as it was", n=n, by="auto", moves=[])
        return "resume"
    if mode(now_goal, cfg) == "review":
        rec.update(state="review")
        _write(run_dir, rec)
        episode(state_dir, gid, n, state="review")
        decisions.park(state_dir, "goal_plan", gid, f"replan-{n}", f"Goal {gid}: a new plan for the lanes left waits "
                       "for your review", "; ".join(diff_lines(checked.moves)), run_dir=str(run_dir), replan=n)
        return _outcome(run_dir, "parked", "replan review")
    apply_checked(state_dir, gid, run_dir, checked, "auto")
    return "resume"
