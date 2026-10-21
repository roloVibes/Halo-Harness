"""halo_harness.supervise.loop -- the supervisor's tick (Halo 3.1.8.0 R1).

Each tick:
  1. resume: any of the supervisor's own running orchestra goals whose run has
     no live runner and no report runs again from its checkpoint (a crash
     while nobody was driving it) up to `supervise.retries` times;
  2. start: while fewer than `max_running` goals run, the next queued goal
     that is not held starts -- an orchestra goal through the runner (its
     worker guarded by the budget), a job goal as a `halo -p` background run;
  3. poll running goals: a finished orchestra run or an ended job job settles
     the goal; a goal past `max_minutes` is stopped and parks (`why: time`);
     a running orchestra goal whose run drifts pauses for a replan (R2,
     replan.py: the lead is asked in the goal's own thread, never here);
  4. decisions: a parked decision the owner answered is applied (approve or
     reject a plan, raise a cap and resume, stop); a goal_ask past its
     deadline is answered for the owner;
  5. arm: every declaring lineup not armed yet is armed (arm.py); the live
     sessions' feed is drained into the armers;
  6. the pulse is written with the goal counts.

The supervisor runs each goal's orchestra run in its own thread (so several
may run when `max_running > 1`) and never blocks the tick on a model. Tests
drive `Supervisor(...).tick()` in-process with the runner's ADAPTERS seam.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.supervise import apply, arm, asks, budget, decisions, heartbeat, pulse, queue, replan, runner
from halo_harness.supervise.settings import ask_wait_s, settings


class Supervisor:
    def __init__(self, state_dir, *, popen=None, clock: Callable = time.time, feed: Optional[Callable] = None):
        self.state_dir = Path(state_dir)
        self.clock = clock
        self.cfg = settings(self.state_dir)
        self.pulse = pulse.Pulse(self.state_dir, clock=clock)
        self.armer = arm.Armer(self.state_dir, popen=popen)
        self._popen = popen
        self._threads: dict = {}        # goal id -> the thread running its orchestra run
        self._thread_result: dict = {}  # goal id -> its outcome once the thread finished
        self._lock = threading.Lock()
        self._feed = feed          # a callable returning new feed frames (loop.py's tap); tests pass one
        self._session_cwd: dict = {}

    # ---- the whole tick --------------------------------------------------------
    def tick(self) -> dict:
        self.cfg = settings(self.state_dir)
        self._settle()
        self._resume()
        self._start()
        self._timeouts()
        replan.watch(self)  # R2: a running goal whose run drifts pauses for a replan (supervise/replan.py)
        self.watch_plans()
        self._decisions()
        self._expire_asks()
        self._arm()
        counts = queue.counts(self.state_dir)
        self.pulse.write("running", counts)
        return counts

    # ---- 1. resume a crashed run -----------------------------------------------
    def _resume(self) -> None:
        """Orphans only: a running goal this process has no thread for (a previous supervisor died) --
        a thread of ours, alive or with its outcome not yet settled, is never doubled."""
        for goal in self._running_orchestra():
            run_dir = Path(goal["run_dir"]) if goal.get("run_dir") else None
            if run_dir is None or not run_dir.is_dir():
                continue
            if goal["id"] in self._threads:
                continue
            from halo_harness.orchestra.report import load_report
            if load_report(run_dir) is not None or heartbeat.other_live(run_dir) is not None:
                continue
            self._spawn_run(goal)

    # ---- 2. start the next queued goal -----------------------------------------
    def _start(self) -> None:
        while self._running_count() < int(self.cfg["max_running"]):
            goal = self._next_queued()
            if goal is None:
                return
            over = budget.over_at_start(self.state_dir, goal, self.cfg.get("budget_usd"))
            if over:
                parked = queue.set_state(self.state_dir, goal["id"], "parked", f"budget: {over}",
                                         failure={"kind": "budget", "step": "", "last_event": over})
                apply.park_budget(self, parked, over)
                continue
            try:
                if goal["kind"] == "job":
                    run = runner.start_job(self.state_dir, goal, self.cfg)
                    queue.set_state(self.state_dir, goal["id"], "running", "started", bg_id=run["id"])
                else:
                    queue.set_state(self.state_dir, goal["id"], "running", "started",
                                    run_dir=str(runner.ensure_run(goal)))
                    self._spawn_run(queue.load(self.state_dir, goal["id"]))
            except (OSError, ValueError) as e:  # the goal could not start: it fails, the queue goes on
                why = f"could not start: {type(e).__name__}: {e}"
                queue.set_state(self.state_dir, goal["id"], "failed", "crash",
                                failure={"kind": "crash", "step": "start", "last_event": why})

    # ---- 3. the running goals --------------------------------------------------
    def _settle(self) -> None:
        for goal in self._running():
            out = None
            if goal["kind"] == "job":
                out = runner.job_outcome(goal)
            else:
                with self._lock:
                    out = self._thread_result.pop(goal["id"], None)
            if out is not None:
                apply.outcome(self, goal, out)

    def _timeouts(self) -> None:
        cap_m = float(self.cfg.get("max_minutes") or 0)
        if cap_m <= 0:
            return
        now = self.clock()
        for goal in self._running():
            started = float(goal.get("started") or now)
            if now - started < cap_m * 60.0 or goal.get("time_stop"):
                continue
            why = f"time: past the goal's max_minutes ({cap_m:g})"
            if goal["kind"] == "job":  # no checkpoint to stop at: end it and park it (never a retried crash)
                runner.stop_job(goal)
                queue.set_state(self.state_dir, goal["id"], "parked", "time",
                                failure={"kind": "time", "step": "", "last_event": why})
            elif goal.get("run_dir"):  # once: the run stops between steps and parks `why: time`
                from halo_harness.orchestra.run import request_stop
                request_stop(Path(goal["run_dir"]), why)
                queue.update(self.state_dir, goal["id"], lambda g: g.update(time_stop=True))

    # ---- 4. the owner's decisions ----------------------------------------------
    def _decisions(self) -> None:
        for row in decisions.answered(self.state_dir):
            apply.decision(self, row)

    def _expire_asks(self) -> None:
        apply.expire_asks(self)

    # ---- 5. the schedules ------------------------------------------------------
    def _arm(self) -> None:
        repos = sorted({g["repo"] for g in queue.all_goals(self.state_dir)
                        if g.get("state") in ("queued", "running", "parked") and g.get("repo")})
        self.armer.scan([Path(r) for r in repos])
        for frame in self._drain_feed():
            self._session_cwd.update(_cwd_from_frame(frame))
            self.armer.feed(frame, self._session_cwd.get)
            parked = asks.park_frame(self.state_dir, frame, asks.session_goals(self.state_dir), ask_wait_s(self.cfg))
            if parked is not None and self.cfg.get("asks") == "deny":
                asks.send(parked, "r" if parked["target"].get("ask") in ("question",) else "s", "")
                decisions.close(self.state_dir, parked["id"], "supervise.asks is deny")

    # ---- the orchestra run on its own thread -----------------------------------
    def _spawn_run(self, goal: dict) -> None:
        if goal is None:
            return

        def work() -> None:
            out = runner.run_orchestra(self.state_dir, goal, self.cfg)
            with self._lock:
                self._thread_result[goal["id"]] = out
        t = threading.Thread(target=work, name=f"halo-supervise-{goal['id']}", daemon=True)
        self._threads[goal["id"]] = t
        t.start()

    def run_inline(self, goal: dict) -> dict:
        """Tests: run one orchestra goal to its outcome in this thread (no daemon thread)."""
        out = runner.run_orchestra(self.state_dir, goal, self.cfg)
        apply.outcome(self, queue.load(self.state_dir, goal["id"]), out)
        return out

    # ---- helpers ----------------------------------------------------------------
    def _running(self) -> list:
        return [g for g in queue.all_goals(self.state_dir) if g.get("state") == "running"]

    def _running_orchestra(self) -> list:
        return [g for g in self._running() if g.get("kind") == "orchestra"]

    def _running_count(self) -> int:
        return len(self._running())

    def _next_queued(self) -> Optional[dict]:
        return next((g for g in queue.all_goals(self.state_dir)
                     if g.get("state") == "queued" and not g.get("held")), None)

    def _drain_feed(self) -> list:
        if self._feed is None:
            return []
        try:
            return list(self._feed() or [])
        except Exception:
            return []

    def watch_plans(self) -> None:
        """Park a goal_plan for every running review goal whose split is waiting and has no row yet."""
        from halo_harness.orchestra import plan as P
        for goal in self._running_orchestra():
            if goal.get("plan") == "review" and goal.get("run_dir") and P.is_planned(Path(goal["run_dir"])) \
                    and not P.read_decision(Path(goal["run_dir"])):
                apply.park_plan(self, goal)

    def close(self) -> None:
        self.armer.stop()
        self.pulse.write("stopped", queue.counts(self.state_dir))


def _cwd_from_frame(frame: dict) -> dict:
    """A `sessions` frame carries each attached session's cwd; keep it so a repo lineup's triggers
    only see that repo's sessions (arm.Armer.feed)."""
    if frame.get("event") != "sessions":
        return {}
    data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
    out = {}
    for s in data.get("sessions") or []:
        if isinstance(s, dict) and s.get("session_id") and s.get("cwd"):
            out[str(s["session_id"])] = str(s["cwd"])
    return out
