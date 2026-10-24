"""halo_harness.supervise.replan -- the supervisor's second move: a run that
drifts gets a new plan for the lanes left (Halo 3.1.8.0 R2, docs/SUPERVISE.md
"Replanning").

    mode(goal, cfg)        none | auto | review: the goal's own `replan` (`halo goal add --replan`), else
                           supervise.replan; a goal with plan: review always reviews (unless none)
    allowed(goal, cfg)     '' when a replan may be asked, else why not (a workflow run first, then none,
                           supervise.replan_max, the cooldown)
    pinned_by(goal)        3.2.1.0 R2: the `<pack>/<name>` a goal's run is compiled from ('' for none): the goal
                           row's `workflow`, its goal.json `workflow` block, or split.json `workflow.pinned`.
                           A workflow run keeps its stage set: the replanner never pauses it (its moves are
                           checked and applied as one plan, and a split or a specialist adds a lane), and
                           with a replan mode set the goal row's `replan_off` and one `state` line say so once
    check_and_pause(...)   drift.py over the run; drifting and allowed: the run pauses (below)
    spawn_hook(...)        budget.Guard's `before`: no lane starts while the run pauses for a replan, and a
                           drift found before a lane starts (returns, forecast) pauses it
    watch(sup)             the tick: the same check for every running goal (blocked and stalled lanes, where
                           nothing spawns)
    apply_checked(...)     a checked plan written into the run (replan_apply.py), the episode closed

replan_ask.py `settle` runs after the run stopped on its pause, in the goal's own
thread (never the tick): it asks the lead, checks, and applies (auto) or parks a
goal_plan row (review) or a goal_replan row (a second failed check);
replan_rows.py takes the owner's answer to either row.

The pause is the run's own: `<run>/replan.json` says `pausing` and the run's stop
file asks it to stop between steps (orchestra/run.py); a worker that runs finishes
its step, no lane is killed, and the guard starts no new one.

    <run>/replan.json       {n, state: pausing | asking | applied | review | parked | rejected | unchanged | dropped
                             | stopped, at, why: [drift rows], problems, moves, cost_usd, settled, by}
    <run>/replan.plan.json  {jobs, why}: the lead's last proposal for the lanes left (edit it, then answer `a`)
    goal file `replans`     [{n, at, why: [kinds], lines, state, settled, by, note}]: one per replan, the cooldown,
                            supervise.replan_max and the status line read it
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import jsonl
from halo_harness.supervise import decisions, queue

REC, PLAN = "replan.json", "replan.plan.json"
PAUSE = "paused for a replan"
LIVE = ("pausing", "asking")
PINNED = "a workflow run keeps its stage set (its plan is pinned by {ref})"


def mode(goal: dict, cfg: dict) -> str:
    m = str(goal.get("replan") or cfg.get("replan") or "none")
    if m not in ("auto", "review"):
        return "none"
    return "review" if goal.get("plan") == "review" else m


def record(run_dir) -> dict:
    data = jsonl.read_json(Path(run_dir) / REC, {})
    return data if isinstance(data, dict) else {}


def _write(run_dir, rec: dict) -> None:
    jsonl.write_json(Path(run_dir) / REC, rec)


def pausing(run_dir) -> bool:
    return record(run_dir).get("state") in LIVE


def pinned_by(goal: dict, run_dir=None) -> str:
    """The workflow the goal's run is compiled from (`<pack>/<name>`), '' for a run without one."""
    ref = goal.get("workflow") if isinstance(goal, dict) else None
    if isinstance(ref, str) and ref.strip():
        return ref.strip()
    rd = run_dir or (goal.get("run_dir") if isinstance(goal, dict) else None)
    if not rd:
        return ""
    block = (jsonl.read_json(Path(rd) / "goal.json", {}) or {}).get("workflow")
    if isinstance(block, dict) and block:
        return str(block.get("ref") or "its workflow")
    pin = (jsonl.read_json(Path(rd) / "split.json", {}) or {}).get("workflow")
    return "its workflow" if isinstance(pin, dict) and pin.get("pinned") else ""


def off_line(goal: dict, cfg: dict, run_dir=None) -> str:
    """The one line a workflow goal's row and `halo goal show` print ('' when no replan mode is set, or no workflow)."""
    ref = pinned_by(goal, run_dir)
    return PINNED.format(ref=ref) if ref and mode(goal, cfg) != "none" else ""


def _note_off(state_dir, gid: str, run_dir, line: str) -> None:
    """Once per goal: the row's `replan_off` and a `state` line in the run's events.jsonl."""
    seen: list = []
    queue.update(state_dir, gid, lambda g: seen.append(g.get("replan_off")) or g.update(replan_off=line))
    if seen and seen[0] != line:
        event(run_dir, "replan_off", line)


def allowed(goal: dict, cfg: dict, now: Optional[float] = None, run_dir=None) -> str:
    now = time.time() if now is None else now
    ref = pinned_by(goal, run_dir)
    if ref:
        return PINNED.format(ref=ref)
    if mode(goal, cfg) == "none":
        return "supervise.replan is none"
    eps = goal.get("replans") or []
    asked = [e for e in eps if e.get("state") != "dropped"]  # a pause the run outran asked nobody
    if len(asked) >= int(cfg["replan_max"]):
        return f"the goal replanned {len(asked)} times (supervise.replan_max {cfg['replan_max']})"
    if eps:
        last = max(float(eps[-1].get("at") or 0.0), float(eps[-1].get("settled") or 0.0))
        if now - last < float(cfg["replan_cooldown_s"]):
            return f"the last replan was {now - last:.0f}s ago (supervise.replan_cooldown_s {cfg['replan_cooldown_s']:g})"
    return ""


def episode(state_dir, gid: str, n: int, **fields) -> None:
    """Update the goal's `replans` row number `n`."""
    def fn(g: dict) -> None:
        for row in g.get("replans") or []:
            if int(row.get("n") or 0) == n:
                row.update({k: v for k, v in fields.items() if v is not None})
    queue.update(state_dir, gid, fn)


def event(run_dir, name: str, text: str, **data) -> None:
    from halo_harness.orchestra import events as run_events
    run_events.log(run_dir, "state", f"{name}: {text}", step="replan", replan=name.split("_", 1)[-1], **data)


def pause(state_dir, gid: str, run_dir, drifts: list, now: Optional[float] = None) -> bool:
    """Ask the run to pause for a replan (once: False when one is already in flight)."""
    from halo_harness.filelock import file_lock
    from halo_harness.orchestra.run import request_stop
    from halo_harness.supervise.drift import kinds, lines
    now = time.time() if now is None else now
    run_dir = Path(run_dir)
    with file_lock(run_dir / REC):
        if pausing(run_dir):
            return False
        goal = queue.load(state_dir, gid) or {}
        n = len(goal.get("replans") or []) + 1
        _write(run_dir, {"n": n, "state": "pausing", "at": round(now, 3), "why": [d.to_dict() for d in drifts]})
    for row in decisions.all_rows(state_dir):  # an older replan row of this goal no longer applies
        if row.get("goal") == gid and (row.get("target") or {}).get("replan") and not row.get("closed"):
            decisions.close(state_dir, row["id"], f"replan {n} replaces it")
    queue.update(state_dir, gid, lambda g: g.setdefault("replans", []).append(
        {"n": n, "at": round(now, 3), "why": kinds(drifts), "lines": lines(drifts), "state": "pausing"}))
    request_stop(run_dir, "replan: " + "; ".join(lines(drifts)))
    return True


def check_and_pause(state_dir, gid: str, run_dir, cfg: dict, now: Optional[float] = None) -> list:
    """The drifts that paused the run ([] when it did not drift, may not replan, or already pauses)."""
    from halo_harness.orchestra import plan as P
    from halo_harness.supervise.budget import others_spent
    from halo_harness.supervise.drift import drift
    goal = queue.load(state_dir, gid)
    if goal is None or pausing(run_dir):
        return []
    off = off_line(goal, cfg, run_dir)
    if off:  # 3.2.1.0 R2: a workflow run is never paused for a replan; its row says so once
        if goal.get("replan_off") != off:
            _note_off(state_dir, gid, run_dir, off)
        return []
    if allowed(goal, cfg, now, run_dir) or P.is_planned(run_dir):
        return []
    found = drift(run_dir, cfg, now=now, others_usd=others_spent(state_dir, gid))
    return found if found and pause(state_dir, gid, run_dir, found, now) else []


def spawn_hook(state_dir, gid: str, run_dir, cfg: dict) -> Callable:
    def before(lane) -> str:
        return PAUSE if pausing(run_dir) or check_and_pause(state_dir, gid, run_dir, cfg) else ""
    return before


def watch(sup) -> None:
    """The tick: every running orchestra goal whose run thread is alive."""
    for goal in sup._running_orchestra():
        t = sup._threads.get(goal["id"])
        if t is not None and t.is_alive() and goal.get("run_dir"):
            check_and_pause(sup.state_dir, goal["id"], Path(goal["run_dir"]), sup.cfg, sup.clock())


def drop(state_dir, gid: str, run_dir, why: str) -> None:
    """The pause no longer applies (the run finished first, a budget stop, the goal moved): no replan."""
    rec = record(run_dir)
    if rec.get("state") in LIVE:
        rec.update(state="dropped", settled=round(time.time(), 3), note=why)
        _write(run_dir, rec)
        episode(state_dir, gid, int(rec.get("n") or 0), state="dropped", settled=rec["settled"], note=why)


def apply_checked(state_dir, gid: str, run_dir, checked, by: str) -> dict:
    from halo_harness.supervise import replan_apply
    rec = record(run_dir)
    n = int(rec.get("n") or 0)
    rev = replan_apply.apply(run_dir, checked, n=n, by=by,
                             why=[f"{d.get('kind')}: {d.get('text')}" for d in rec.get("why") or []])
    rec.update(state="applied", settled=round(time.time(), 3), by=by, moves=checked.moves)
    _write(run_dir, rec)
    episode(state_dir, gid, n, state="applied", settled=rec["settled"], by=by)
    return rev
