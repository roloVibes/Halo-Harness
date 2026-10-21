"""halo_harness.work.adapters.goal -- a supervisor goal as a unit (Halo 3.1.8.0
R1). The run folder is the supervise folder `<state>/supervise/` (its marker
is `queue.json`); each goal is `goals/<g-id>.json` (supervise/queue.py). This
adapter reads a goal as a `Unit` so `halo work` lists goals beside Orchestra
lanes, mission parts and team stages.

Unit mapping: id = the goal id; owner = its lineup; title = what; claims =
the repo (mode `path`); cost_usd; attempts = `retries`; gate none; state the
queue's own (queued -> ready, parked -> waiting, states.py); refs = run_dir,
bg_id, repo; extra = kind, repo, budget_usd, why, failure. The ledger is the
goal's history lines (supervise/history.py).
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.work import unit as U
from halo_harness.work.ledger import line

KIND = "goal"
_EXTRA = ("kind", "repo", "budget_usd", "why", "failure", "held", "retries")


def _sd(run_dir) -> Path:
    """The state dir the supervise folder sits in (`<state>/supervise/` -> `<state>`)."""
    return Path(run_dir).parent


def to_unit(goal: dict, run_id: str = "") -> U.Unit:
    return U.Unit.from_native(
        KIND, goal["id"], str(goal.get("state") or "queued"), title=str(goal.get("what") or ""), run_id=run_id,
        owner=str(goal.get("lineup") or ""), claims=U.claims([goal.get("repo")] if goal.get("repo") else [], "path"),
        gate=U.gate("none"), cost_usd=float(goal.get("cost_usd") or 0.0), started=goal.get("started"),
        ended=goal.get("ended"), attempts=int(goal.get("retries") or 0), error=(goal.get("failure") or {}).get("last_event") or "" if goal.get("failure") else "",
        refs={"run_dir": goal.get("run_dir"), "bg_id": goal.get("bg_id"), "repo": goal.get("repo")},
        extra={k: goal.get(k) for k in _EXTRA if k in goal}, source=dict(goal))


def units(run_dir) -> list:
    from halo_harness.supervise import queue
    return [to_unit(g, Path(run_dir).name) for g in queue.all_goals(_sd(run_dir))]


def unit(run_dir, uid):
    from halo_harness.supervise import queue
    goal = queue.load(_sd(run_dir), str(uid))
    return to_unit(goal, Path(run_dir).name) if goal else None


def write(run_dir, u: U.Unit) -> None:
    """A goal's state is the supervisor's to move (supervise/queue.py); `halo work` is read-only, so this
    writes nothing a read did not already hold."""
    from halo_harness.supervise import queue
    queue.set_state(_sd(run_dir), u.id, {"ready": "queued", "waiting": "parked"}.get(u.state, u.state),
                    (u.extra or {}).get("why") or "")


def set_native(run_dir, uid, word: str, text: str = "") -> None:
    from halo_harness.supervise import queue
    queue.set_state(_sd(run_dir), str(uid), word, text)


def read_gate(run_dir, uid) -> dict:
    return U.gate("none")


def ledger_lines(run_dir) -> list:
    from halo_harness.supervise import history
    run = Path(run_dir).name
    out = []
    for e in history.read(_sd(run_dir)):
        if e.get("row"):
            out.append(line({"ts": e.get("ts"), "text": f"decision {e.get('key')} on {e.get('row')}"}, "note", run,
                            unit=e.get("goal"), by=e.get("by") or "", native="decision",
                            data={k: v for k, v in e.items() if k != "ts"}))
        else:
            out.append(line({"ts": e.get("ts"), "text": f"{e.get('from') or '-'} -> {e.get('to')}"
                             + (f" ({e['why']})" if e.get("why") else "")}, "state", run, unit=e.get("goal"),
                            native=str(e.get("to") or ""), data={k: v for k, v in e.items() if k != "ts"}))
    return out
