"""halo_harness.supervise.runner -- the two ways a goal runs (Halo 3.1.8.0 R1).

* `orchestra`: an Orchestra run in the goal's repo (`<repo>/.halo/orchestra/<run-id>/`,
  recorded as the goal's `run_dir`), run to its report through
  team/adapters.orchestra_run with the real adapters, each lane's worker
  behind the budget guard (budget.py), the runner beating runner.json. A run
  that already has a folder runs again from its checkpoint (orchestra/run.py
  picks up at the first unfinished step; a written or merged lane is never
  run again).
* `job`: `halo -p <what> --output-format json --permission-mode auto
  [--max-budget-usd <cap>] [--team <lineup> --agent <its main bio>]` through
  bg_run.start_background_run (`halo bg` lists it; the goal's `bg_id`), in the
  goal's repo, with HALO_SUPERVISE_GOAL / HALO_SUPERVISE_ASKS set (asks.py).

`outcome(...)` reads how a goal ended -- report.json, or the job's
status.json and its result JSON -- as `{state, why, cost_usd, failure}`;
`failure` is `{kind: crash | worker | gate | budget | time | cancelled, step, last_event, report?}`.
`ADAPTERS` and `POPEN` are the seams tests set (no model is called).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from halo_harness.orchestra import jsonl

ADAPTERS = None   # (run_dir, goal, model) -> run()'s model_calls / spawn / judge; None: the real adapters
POPEN = None      # bg_run's popen seam for a job goal
RETRYABLE = ("crash", "worker")


def ensure_run(goal: dict) -> Path:
    """The goal's Orchestra run folder, made on its first start."""
    if goal.get("run_dir") and (Path(goal["run_dir"]) / "goal.json").is_file():
        return Path(goal["run_dir"])
    from halo_harness.orchestra.goal import Goal, new_run
    from halo_harness.supervise.queue import orchestra_fields
    return new_run(Path(goal["repo"]), Goal.from_dict(orchestra_fields(goal)))


def failure(kind: str, run_dir=None, text: str = "", report: Optional[dict] = None) -> dict:
    out = {"kind": kind, "step": "", "last_event": text}
    if run_dir is not None:
        graph = jsonl.read_json(Path(run_dir) / "workflow.json", {}) or {}
        steps = graph.get("steps") or []
        stopped = [s["id"] for s in steps if s.get("state") in ("failed", "running", "planned")]
        out["step"] = stopped[0] if stopped else next((s["id"] for s in steps if s.get("state") not in ("done", "skipped")), "")
        from halo_harness.orchestra import events as run_events
        last = run_events.read(run_dir)
        out["last_event"] = text or (str(last[-1].get("text") or "") if last else "")
    if report is not None:
        out["report"] = {"status": report.get("status"), "stop_reason": report.get("stop_reason"),
                         "path": str(Path(run_dir) / "report.json") if run_dir is not None else None}
    return out


def classify(reason: str) -> "tuple[str, str, str]":
    """`(state, why, failure kind)` for a stopped run's stop_reason."""
    r = str(reason or "")
    low = r.lower()
    if low.startswith("budget:") or "stop: budget:" in low:
        return "parked", "budget", "budget"
    if low.startswith("paused"):
        return "parked", "paused", ""
    if low.startswith("time:"):
        return "parked", "time", "time"
    if low.startswith("cancelled"):
        return "stopped", "cancelled", "cancelled"
    if low.startswith("the plan was rejected"):
        return "stopped", "plan rejected", "cancelled"
    if "reached the return cap" in low:
        return "parked", "gate", "gate"
    if "the tests" in low and "finished branch" in low:
        return "failed", "gate", "gate"
    if "stop:" in low:
        return "stopped", "stop when", "worker"
    if low.startswith("lane ") or "worker" in low:
        return "failed", "worker", "worker"
    return "failed", "crash", "crash"


def run_orchestra(state_dir, goal: dict, cfg: dict, on_event=None) -> dict:
    """Run (or resume) the goal's Orchestra run to its report; the outcome. Never raises."""
    from halo_harness.supervise.budget import Guard, run_spent
    from halo_harness.team.adapters import orchestra_run
    run_dir = Path(goal["run_dir"])
    guard = Guard(state_dir, goal, run_dir, cfg.get("budget_usd"))
    try:
        got = orchestra_run(None, goal["repo"], run_dir=run_dir, wrap=guard.wrap, make=ADAPTERS, by="supervise",
                            model=goal.get("model") or None, on_event=on_event)
        report = got["report"]
    except Exception as e:  # anything run() did not turn into a stopped report: a crash
        text = f"the runner stopped on an error: {type(e).__name__}: {e}"
        return {"state": "failed", "why": "crash", "cost_usd": run_spent(run_dir), "failure": failure("crash", run_dir, text)}
    if guard.hit:
        report = dict(report, stop_reason=f"budget: {guard.hit}")
        jsonl.write_json(run_dir / "report.json", report)
    return report_outcome(run_dir, report)


def report_outcome(run_dir, report: dict) -> dict:
    cost = float(report.get("cost_usd") or 0.0)
    if report.get("status") == "finished":
        return {"state": "done", "why": "finished", "cost_usd": cost, "failure": None}
    state, why, kind = classify(str(report.get("stop_reason") or ""))
    return {"state": state, "why": why, "cost_usd": cost,
            "failure": failure(kind, run_dir, str(report.get("stop_reason") or ""), report) if kind else None}


def main_bio(lineup: str, repo) -> Optional[str]:
    if not lineup:
        return None
    from halo_harness.team.adapters import member_bio
    return member_bio({"lineup": lineup, "role": "main"}, cwd=repo)


def job_argv(goal: dict, cap: Optional[float]) -> list:
    argv = ["-p", goal["what"], "--output-format", "json", "--permission-mode", "auto"]
    if cap is not None:
        argv += ["--max-budget-usd", f"{cap:.6f}".rstrip("0").rstrip(".") or "0"]
    if goal.get("lineup"):
        argv += ["--team", goal["lineup"]]
        bio = main_bio(goal["lineup"], goal.get("repo"))
        if bio:
            argv += ["--agent", bio]
    return argv


def start_job(state_dir, goal: dict, cfg: dict) -> dict:
    """Start the job goal's `halo -p` in the background; bg_run's `{id, log_path, pid, meta_path}`."""
    from halo_harness.bg_run import start_background_run
    from halo_harness.supervise.budget import job_cap
    env = {**os.environ, "HALO_SUPERVISE_GOAL": goal["id"], "HALO_SUPERVISE_ASKS": str(cfg.get("asks") or "park")}
    argv = job_argv(goal, job_cap(state_dir, goal, cfg.get("budget_usd")))
    return start_background_run(argv, popen=POPEN or subprocess.Popen, env=env, cwd=str(goal["repo"]))


def job_outcome(goal: dict) -> Optional[dict]:
    """None while the job runs; else how it ended."""
    from halo_harness.bg_run import is_our_process, load_run
    meta = load_run(str(goal.get("bg_id") or ""))
    if meta is None:
        return {"state": "failed", "why": "crash", "cost_usd": 0.0, "failure": failure("crash", text="no bg run record")}
    status = jsonl.read_json(Path(meta["run_dir"]) / "status.json", None)
    if not isinstance(status, dict):
        if is_our_process(meta):
            return None
        return {"state": "failed", "why": "crash", "cost_usd": 0.0,
                "failure": failure("crash", text="the job's process ended without a status")}
    from halo_harness.orchestra.adapters import _last_json
    try:
        result = _last_json(Path(meta["log_path"]).read_text(encoding="utf-8", errors="replace")) or {}
    except OSError:
        result = {}
    cost = float(result.get("total_cost_usd") or 0.0)
    text = str(result.get("result") or "")[-300:]
    if result.get("subtype") == "error_max_budget_usd":
        return {"state": "parked", "why": "budget", "cost_usd": cost, "failure": failure("budget", text=text)}
    if status.get("exit_code") == 0 and result and not result.get("is_error"):
        return {"state": "done", "why": "finished", "cost_usd": cost, "failure": None}
    kind = "worker" if result else "crash"
    note = text or f"exit {status.get('exit_code')}" + (f": {status['launch_error']}" if status.get("launch_error") else "")
    return {"state": "failed", "why": kind, "cost_usd": cost, "failure": failure(kind, text=note)}


def stop_job(goal: dict) -> bool:
    """End a running job goal's process tree."""
    from halo_harness.bg_run import is_our_process, kill_pid, load_run
    meta = load_run(str(goal.get("bg_id") or ""))
    if meta is None or not is_our_process(meta):
        return False
    return kill_pid(int(meta["pid"]))


def harness_argv() -> list:
    return [sys.executable, "-m", "halo_harness"]
