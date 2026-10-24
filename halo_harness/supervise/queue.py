"""halo_harness.supervise.queue -- the goal queue (Halo 3.1.8.0 R1).

One file per goal, `<state>/supervise/goals/<g-id>.json`:

    {id, what, done_when, stop_when, repo, budget_usd, lineup, kind: orchestra | job,
     state: queued | running | parked | done | stopped | failed, created, started, ended,
     run_dir | bg_id, cost_usd, why, held, retries, failure, files, test, workers, plan, replan, replans}

`held` keeps a queued goal from starting (`halo goal hold` / `release`,
`pause` on a queued one). `failure` is set on a goal that ended badly:
`{kind: crash | worker | gate | budget | time | cancelled | retries, step, last_event, report?}`.
`files`, `test`, `workers` and `plan` are the Orchestra goal's own fields
(orchestra/goal.py); 3.2.1.0 R1: an orchestra goal with a lineup takes the
lineup's acceptance (`test`, `review`) the way `halo orchestra new` does,
and `taken` (only when it took something) lists the lines saying what.
R2: `replan` (none | auto | review, '' = supervise.replan)
and `replans` (one row per replan, supervise/replan.py). `<state>/supervise/queue.json` marks the folder for
`halo work` (work/adapters/goal.py). Every write takes the goal file's lock,
so `halo goal` and a running supervisor never lose each other's change;
every state change adds a history line (history.py).
"""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.filelock import file_lock
from halo_harness.privateio import write_private_atomic

STATES = ("queued", "running", "parked", "done", "stopped", "failed")
OVER = ("done", "stopped", "failed")
KINDS = ("orchestra", "job")
MARKER = "queue.json"


def root(state_dir=None) -> Path:
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    return Path(state_dir) / "supervise"


def goals_dir(state_dir=None) -> Path:
    return root(state_dir) / "goals"


def goal_path(state_dir, gid: str) -> Path:
    return goals_dir(state_dir) / f"{gid}.json"


def new_id() -> str:
    return f"g-{secrets.token_hex(3)}"


def _write(state_dir, goal: dict) -> None:
    write_private_atomic(goal_path(state_dir, goal["id"]), json.dumps(goal, indent=2, sort_keys=True, default=str))


def _mark(state_dir) -> None:
    marker = root(state_dir) / MARKER
    if not marker.exists():
        write_private_atomic(marker, json.dumps({"version": 1, "created": round(time.time(), 3)}))


def lineup_defaults(goal: dict, state_dir=None) -> "list[str]":
    """3.2.1.0 R1: an orchestra goal's lineup acceptance, as `halo orchestra new --lineup` takes it
    (packs/lineup_run.py): an empty `test` gets the lineup's, `plan: auto` becomes review when the lineup
    says review. A test you gave wins. The lines say what was taken."""
    from halo_harness.packs.lineup_run import run_defaults
    name = goal.get("lineup") or ""
    took = run_defaults(name, cwd=goal.get("repo"), state_dir=state_dir) if name else {}
    lines: "list[str]" = []
    if took.get("test") and not str(goal.get("test") or "").strip():
        goal["test"] = took["test"]
        lines.append(f"test from lineup {name}: {took['test']}")
    if took.get("review") and goal.get("plan") == "auto":
        goal["plan"] = "review"
        lines.append(f"plan: review from lineup {name} (the run pauses for the plan's review)")
    return lines


def add(state_dir, what: str, *, done_when: str = "", stop_when: str = "", repo=None, budget_usd=None,
        lineup: str = "", kind: str = "orchestra", files=None, test: str = "", workers: Optional[int] = None,
        review: bool = False, replan: str = "", lineup_acceptance: bool = True) -> dict:
    """A new queued goal. ValueError for a bad field (the sentence says which). An orchestra goal with a
    lineup takes its acceptance (`lineup_defaults`) unless `lineup_acceptance` is False (a compiled
    workflow, whose test and plan come from its stages); the lines are the goal's `taken`."""
    what = str(what or "").strip()
    if not what:
        raise ValueError("say what the goal is: halo goal add \"<what>\"")
    if kind not in KINDS:
        raise ValueError(f"--as is orchestra or job, got {kind!r}")
    if replan not in ("", "none", "auto", "review"):
        raise ValueError(f"--replan is none, auto or review, got {replan!r}")
    if budget_usd is not None and (isinstance(budget_usd, bool) or float(budget_usd) < 0):
        raise ValueError(f"--budget is a number of dollars, 0 or more, got {budget_usd!r}")
    repo_path = Path(repo or Path.cwd()).resolve()
    if not repo_path.is_dir():
        raise ValueError(f"--repo {repo_path} is not a folder")
    goal = {"id": new_id(), "what": what, "done_when": str(done_when or "").strip() or "the goal is done as stated",
            "stop_when": str(stop_when or "").strip() or "the goal cannot be done without asking the owner",
            "repo": str(repo_path), "budget_usd": None if budget_usd is None else float(budget_usd),
            "lineup": str(lineup or ""), "kind": kind, "state": "queued", "created": round(time.time(), 3),
            "started": None, "ended": None, "run_dir": None, "bg_id": None, "cost_usd": 0.0, "why": "",
            "held": False, "retries": 0, "failure": None, "files": [str(f) for f in files or []],
            "test": str(test or ""), "workers": workers, "plan": "review" if review else "auto",
            "replan": str(replan or ""), "replans": []}
    taken = lineup_defaults(goal, state_dir) if kind == "orchestra" and goal["lineup"] and lineup_acceptance else []
    if taken:
        goal["taken"] = taken
    if kind == "orchestra":
        from halo_harness.orchestra.goal import validate_goal
        problems = validate_goal(orchestra_fields(goal))
        if problems:
            raise ValueError("; ".join(problems))
    _mark(state_dir)
    while goal_path(state_dir, goal["id"]).exists():
        goal["id"] = new_id()
    _write(state_dir, goal)
    from halo_harness.supervise import history
    history.change(state_dir, goal, "", "queued", "; ".join(["added"] + taken))
    return goal


def orchestra_fields(goal: dict) -> dict:
    """The Orchestra goal.json a goal of kind orchestra runs (orchestra/goal.py)."""
    out = {"what": goal["what"], "done_when": goal["done_when"], "stop_when": goal["stop_when"],
           "files": list(goal.get("files") or []), "test": goal.get("test") or "", "lineup": goal.get("lineup") or "",
           "plan": goal.get("plan") or "auto"}
    if goal.get("workers"):
        out["workers"] = int(goal["workers"])
    if goal.get("budget_usd") is not None:
        out["budget_usd"] = float(goal["budget_usd"])
    return out


def load(state_dir, gid: str) -> Optional[dict]:
    try:
        data = json.loads(goal_path(state_dir, gid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("id") else None


def resolve(state_dir, ref: str) -> Optional[dict]:
    """A goal by id or unique id prefix."""
    ref = str(ref or "").strip()
    if not ref:
        return None
    hit = load(state_dir, ref)
    if hit is not None:
        return hit
    matches = [g for g in all_goals(state_dir) if g["id"].startswith(ref)]
    return matches[0] if len(matches) == 1 else None


def all_goals(state_dir) -> list:
    """Every goal, oldest first."""
    d = goals_dir(state_dir)
    if not d.is_dir():
        return []
    out = [g for g in (load(state_dir, p.stem) for p in d.glob("g-*.json")) if g is not None]
    return sorted(out, key=lambda g: (float(g.get("created") or 0), g["id"]))


def update(state_dir, gid: str, fn: Callable[[dict], None]) -> Optional[dict]:
    """Read, change (`fn(goal)`) and write one goal under its lock; a state change adds a history line."""
    path = goal_path(state_dir, gid)
    with file_lock(path):
        goal = load(state_dir, gid)
        if goal is None:
            return None
        before = goal.get("state")
        fn(goal)
        _write(state_dir, goal)
    if goal.get("state") != before:
        from halo_harness.supervise import history
        history.change(state_dir, goal, str(before or ""), str(goal.get("state")), goal.get("why") or "")
    return goal


def set_state(state_dir, gid: str, state: str, why: str = "", **fields) -> Optional[dict]:
    if state not in STATES:
        raise ValueError(f"a goal's state is one of {', '.join(STATES)}, got {state!r}")

    def apply(goal: dict) -> None:
        goal.update(fields)
        goal["state"] = state
        goal["why"] = why
        if state == "running" and not goal.get("started"):
            goal["started"] = round(time.time(), 3)
        if state in OVER:
            goal["ended"] = round(time.time(), 3)
    return update(state_dir, gid, apply)


def remove(state_dir, gid: str) -> bool:
    try:
        goal_path(state_dir, gid).unlink()
    except OSError:
        return False
    for extra in (goal_path(state_dir, gid).with_suffix(".json.lock"),):
        try:
            extra.unlink()
        except OSError:
            pass
    return True


def counts(state_dir) -> dict:
    """The pulse's `goals`: {queued, running, done, parked} (a stopped or failed goal is in none of them)."""
    out = {"queued": 0, "running": 0, "done": 0, "parked": 0}
    for g in all_goals(state_dir):
        if g.get("state") in out:
            out[g["state"]] += 1
    return out
