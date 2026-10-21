"""halo_harness.supervise.apply -- how the supervisor settles a goal and takes
a decision (Halo 3.1.8.0 R1), kept out of loop.py so the tick stays small.

`outcome(sup, goal, out)` writes a finished goal's end state (a retryable
failure is re-queued up to `supervise.retries`, then parks `why: retries`; a
budget or gate stop parks and raises its Attention row). `decision(sup, row)`
applies the owner's answer to a parked decision (approve or reject a plan,
raise a cap and resume, stop, or forward a job goal's ask over its socket;
R2: a replan's goal_plan or goal_replan row goes to replan_rows.decide).
`park_*` make the budget / gate / plan rows. `cancel(sup, gid, why)` is the
shared stop used by `halo goal cancel` and a goal_ask's Stop.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.supervise import asks, decisions, queue, runner

EXPIRE_KEY = {"permission": "r", "question": "r", "plan": "r", "approval": "s"}


def outcome(sup, goal: dict, out: dict) -> None:
    sup._threads.pop(goal["id"], None)
    state, why, failure = out["state"], out.get("why") or "", out.get("failure")
    cost = float(out.get("cost_usd") or 0.0)
    now = queue.load(sup.state_dir, goal["id"]) or goal
    if now.get("state") != "running":  # `halo goal pause` / `cancel` moved it meanwhile: keep that, record the cost
        queue.update(sup.state_dir, goal["id"], lambda g: g.update(cost_usd=cost))
        return
    retryable = state == "failed" and failure and failure.get("kind") in runner.RETRYABLE
    if retryable and int(goal.get("retries") or 0) < int(sup.cfg["retries"]):
        queue.update(sup.state_dir, goal["id"], lambda g: g.update(
            retries=int(g.get("retries") or 0) + 1, cost_usd=cost, state="queued", why="retry", failure=failure))
        return
    if retryable:
        state, why = "parked", "retries"
    queue.set_state(sup.state_dir, goal["id"], state, why, cost_usd=cost, failure=failure)
    goal = queue.load(sup.state_dir, goal["id"])
    if why == "budget" and state == "parked":
        park_budget(sup, goal, (failure or {}).get("last_event") or "over the budget")
    elif why == "gate" and state in ("parked", "failed"):
        park_gate(sup, goal, (failure or {}).get("last_event") or "the gate sent a piece back past the cap")
    if state in queue.OVER:
        decisions.close_goal(sup.state_dir, goal["id"], f"the goal is {state}")


def decision(sup, row: dict) -> None:
    ans = row.get("answer") or {}
    key, text = ans.get("key"), str(ans.get("text") or "")
    kind = row["kind"]
    if kind == "goal_replan" or (kind == "goal_plan" and (row.get("target") or {}).get("replan")):
        from halo_harness.supervise.replan_rows import decide  # 3.1.8.0 R2: a replan's review or its failed check
        decide(sup, row, key, text)
    elif kind == "goal_plan":
        _plan(sup, row, key, text)
    elif kind == "goal_gate":
        _raise(sup, row, key, text, step="return_cap")
    elif kind == "goal_budget":
        _raise(sup, row, key, text, step="budget")
    elif kind == "goal_ask":
        _ask(sup, row, key, text)


def expire_asks(sup) -> None:
    for row in asks.expired(sup.state_dir, sup.clock()):
        key = EXPIRE_KEY.get((row.get("target") or {}).get("ask"), "r")
        asks.send(row, key, "")
        decisions.close(sup.state_dir, row["id"], "no answer came before the deadline")


def _plan(sup, row: dict, key: str, text: str) -> None:
    from halo_harness.orchestra import plan as P
    run_dir = Path((row.get("target") or {}).get("run_dir") or "")
    if key == "a":
        problems = P.approve(run_dir, P.read_draft(run_dir) or P.lead_jobs(run_dir), by="supervisor")
        if problems:
            decisions.reopen(sup.state_dir, row["id"], "the plan does not pass the check: "
                             + "; ".join(p["text"] for p in problems))
            return
    elif key == "r":
        P.reject(run_dir, text or "rejected from Attention", by="supervisor")
    decisions.close(sup.state_dir, row["id"], f"plan {key}")


def _raise(sup, row: dict, key: str, text: str, step: str) -> None:
    gid = row["goal"]
    goal = queue.load(sup.state_dir, gid)
    if goal is None:
        return decisions.close(sup.state_dir, row["id"], "the goal is gone")
    if key == "s":
        queue.set_state(sup.state_dir, gid, "stopped", "stopped from Attention")
        return decisions.close(sup.state_dir, row["id"], "stopped")
    if step == "budget":
        base = float(goal.get("budget_usd") or 0.0) or 1.0
        add = decisions.number(text, base) if key == "r" else base
        queue.update(sup.state_dir, gid, lambda g: g.update(
            budget_usd=round(float(g.get("budget_usd") or 0.0) + add, 6), state="queued", why="budget raised"))
    else:
        _raise_return_cap(goal, int(decisions.number(text, 1) if key == "r" else 1))
        queue.set_state(sup.state_dir, gid, "queued", "cap raised")
    decisions.close(sup.state_dir, row["id"], "raised and resumed")


def _raise_return_cap(goal: dict, by: int) -> None:
    from halo_harness.orchestra import jsonl
    gp = Path(goal.get("run_dir") or "") / "goal.json"
    data = jsonl.read_json(gp, None)
    if isinstance(data, dict):
        data["return_cap"] = int(data.get("return_cap") or 2) + by
        jsonl.write_json(gp, data)


def _ask(sup, row: dict, key: str, text: str) -> None:
    if key == "s":
        cancel(sup, row["goal"], "stopped from Attention")
    else:
        why = asks.send(row, key, text)
        if why:
            decisions.reopen(sup.state_dir, row["id"], f"could not answer: {why}")
            return
    decisions.close(sup.state_dir, row["id"], f"ask {key}")


def cancel(sup, gid: str, why: str) -> None:
    goal = queue.load(sup.state_dir, gid)
    if goal is None:
        return
    if goal["kind"] == "job":
        runner.stop_job(goal)
    elif goal.get("run_dir"):
        from halo_harness.orchestra.run import request_stop
        request_stop(Path(goal["run_dir"]), "cancelled")
    queue.set_state(sup.state_dir, gid, "stopped", why,
                    failure={"kind": "cancelled", "step": "", "last_event": why})


def park_budget(sup, goal: dict, detail: str) -> None:
    decisions.park(sup.state_dir, "goal_budget", goal["id"], "cap",
                   f"Goal {goal['id']}: over the budget", detail, run_dir=goal.get("run_dir"))


def park_gate(sup, goal: dict, detail: str) -> None:
    decisions.park(sup.state_dir, "goal_gate", goal["id"], "cap",
                   f"Goal {goal['id']}: the gate sent a piece back past the return cap", detail,
                   run_dir=goal.get("run_dir"))


def park_plan(sup, goal: dict) -> None:
    decisions.park(sup.state_dir, "goal_plan", goal["id"], "plan",
                   f"Goal {goal['id']}: the plan waits for your review", goal.get("what") or "",
                   run_dir=goal.get("run_dir"))
