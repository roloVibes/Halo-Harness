"""halo_harness.start.engine -- the guided run's control loop (Halo 3.1.1.0 R1).

`StartRun(options, emit=..., ask=...).run()` walks the seven steps. Each step
is announced as a frame, then (unless `yes`) waits on `ask`: an empty
answer (Enter) runs it, `q` stops the start there. A step's work lives in
steps_setup.py (lineup, repo, next) and steps_run.py (goal, plan, run,
report); it returns its lines, or raises `Stopped` / `StepFailed`.

A frame is one dict, the same everywhere (terminal, the TUI panel, Studio's
`start` frames):

    {step: 1..7, key, title, why, command, state, lines, total: 7}
    state: ready (the screen waits for Enter) | running | done | failed | stopped

`run()` returns the summary (`--json` prints it):

    {ok, fake, stopped_at, reason, lineup, repo, run, report: {status, checks}, coach: N,
     steps: [{step, key, title, state, command, lines}]}

`cancel()` (Esc in the TUI panel, Studio's stop) ends the start at the next
check: between steps, while the plan waits, and during the run (it asks the
Orchestra run to stop).

3.2.2.0 R1: any other exception a step (or the command its screen shows)
raises fails that step the same way: its frame is `failed` with
`<Type>: <message>` and `the full error is in <path>`, the summary's
`reason` is that one line and `error_log` the path. `write_error_log`
(start/errors.py, re-exported here) appends the traceback to
`<state>/start/<yyyy-mm-dd>/<run or start>-error.log`; `halo start`, Studio's
start job and the TUI panel call it for a failure outside the walk.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from halo_harness.start import steps as S
from halo_harness.start.errors import error_line, log_path_or_empty, write_error_log  # noqa: F401 (write_error_log: the one every surface calls)


class Stopped(Exception):
    """The start ends here at the user's word (q, Esc, a rejected plan)."""


class StepFailed(Exception):
    """The step could not do its work; the message says why and what to do."""


@dataclass
class Options:
    lineup: str = S.DEFAULT_LINEUP
    repo: Optional[str] = None
    files: tuple = S.GOAL_FILES
    yes: bool = False
    fake: Optional[bool] = None          # None: the HALO_START_FAKE variable decides
    model: Optional[str] = None
    state_dir: Optional[Path] = None     # None: bridge_home()
    studio: bool = True                  # step 4 offers Studio's plan canvas
    poll_s: float = 0.2
    plan_timeout_s: float = 900.0
    run_timeout_s: float = 7200.0
    today: Optional[str] = None
    extra: dict = field(default_factory=dict)


class StartRun:
    def __init__(self, options: Optional[Options] = None, *, emit: Optional[Callable[[dict], None]] = None,
                 ask: Optional[Callable[[str], str]] = None, open_studio: Optional[Callable[["StartRun"], str]] = None):
        self.opts = options or Options()
        self._emit = emit
        self._ask = ask
        self.open_studio = open_studio
        self._cancel = threading.Event()
        self.frames: "dict[str, dict]" = {}
        self.lineup = ""
        self.repo: Optional[Path] = None
        self.run_dir: Optional[Path] = None
        self.runner: Optional[threading.Thread] = None
        self.result: dict = {}
        self.coach: dict = {}
        self._pending: Optional[str] = None  # the step the walk is at (named when a stop lands between two steps)
        from halo_harness.start import fake
        self.fake = fake.enabled() if self.opts.fake is None else bool(self.opts.fake)

    # -- plumbing -------------------------------------------------------------
    @property
    def state_dir(self) -> Path:
        if self.opts.state_dir is not None:
            return Path(self.opts.state_dir)
        from halo_harness.config.paths import bridge_home
        return Path(bridge_home())

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def wait(self, seconds: float) -> None:
        self._cancel.wait(seconds)

    def emit(self, key: str, state: str, lines=None, command: Optional[str] = None) -> dict:
        n, title, why = S.step_info(key)
        prev = self.frames.get(key) or {}
        frame = {"step": n, "total": S.TOTAL, "key": key, "title": title, "why": why,
                 "command": command if command is not None else prev.get("command", ""), "state": state,
                 "lines": list(lines) if lines is not None else list(prev.get("lines") or [])}
        self.frames[key] = frame
        if self._emit is not None:
            try:
                self._emit(dict(frame))
            except Exception:
                pass
        return frame

    def ask(self, prompt: str) -> str:
        """The user's answer, lowercased; '' (go on) with --yes or no one to ask."""
        if self.opts.yes or self._ask is None or self.cancelled:
            return "q" if self.cancelled else ""
        try:
            return str(self._ask(prompt) or "").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "q"

    # -- the walk ---------------------------------------------------------------
    def run(self) -> dict:
        from halo_harness.start import steps_run, steps_setup
        work = {"lineup": steps_setup.lineup, "repo": steps_setup.repo, "goal": steps_run.goal,
                "plan": steps_run.plan, "run": steps_run.run, "report": steps_run.report, "next": steps_setup.next_steps}
        commands = {"lineup": steps_setup.lineup_command, "repo": steps_setup.repo_command,
                    "goal": steps_run.goal_command, "plan": steps_run.plan_command, "run": steps_run.run_command,
                    "report": steps_run.report_command, "next": steps_setup.next_command}
        summary = {"ok": False, "fake": self.fake, "stopped_at": None, "reason": "", "lineup": "", "repo": "",
                   "run": "", "report": {}, "coach": 0, "steps": []}
        if not self.fake:
            from halo_harness.start import provider
            ok, text = provider.ready()
            if not ok:
                summary.update(stopped_at="lineup", reason="no_provider", message=text)
                return summary
        try:
            for key in S.KEYS:
                self._pending = key
                command = commands[key](self)
                if self.cancelled:
                    self.emit(key, "stopped", [], command)
                    raise Stopped(f"stopped before {key}")
                if not self.opts.yes:
                    self.emit(key, "ready", [], command)
                    if self.ask("Enter runs this step, q stops the start: ") == "q":
                        raise Stopped(f"stopped before {key}")
                self.emit(key, "running", [], command)
                lines = work[key](self)
                self.emit(key, "done", lines)
            summary["ok"] = True
        except Stopped as e:
            self._stop_current("stopped", str(e), summary)
        except StepFailed as e:
            self._stop_current("failed", str(e), summary)
        except Exception as e:  # anything else a step raised: the step fails with one line, the traceback in a file
            self._crashed(e, summary)
        finally:
            self._finish()
        summary.update(lineup=self.lineup, repo=str(self.repo or ""), run=self.run_dir.name if self.run_dir else "",
                       report={"status": self.result.get("status", ""), "stop_reason": self.result.get("stop_reason", ""),
                               "checks": [dict(c) for c in self.result.get("checks") or []]},
                       coach=len(self.coach.get("suggestions") or []),
                       steps=[{k: f[k] for k in ("step", "key", "title", "state", "command", "lines")}
                              for f in sorted(self.frames.values(), key=lambda f: f["step"])])
        return summary

    def _current(self) -> Optional[dict]:
        """The newest frame still ready or running (None between two steps)."""
        return next((f for f in sorted(self.frames.values(), key=lambda f: -f["step"])
                     if f["state"] in ("ready", "running")), None)

    def _stop_current(self, state: str, reason: str, summary: dict) -> None:
        current = self._current()
        if current:
            self.emit(current["key"], state, list(current.get("lines") or []) + [reason])
        summary.update(stopped_at=current["key"] if current else self._pending, reason=reason)

    def _crashed(self, exc: Exception, summary: dict) -> None:
        line = error_line(exc)
        path = log_path_or_empty(self.state_dir, self.run_dir, exc, today=self.opts.today)
        extra = [f"the full error is in {path}"] if path else []
        current = self._current()
        key = current["key"] if current else self._pending
        if key is not None and (self.frames.get(key) or {}).get("state") != "done":
            self.emit(key, "failed", list((self.frames.get(key) or {}).get("lines") or []) + [line] + extra)
        summary.update(stopped_at=key, reason=line, error_log=path)

    def _finish(self) -> None:
        """A run still going when the start ends is asked to stop; the plan, if it waits, is rejected."""
        if self.runner is None or not self.runner.is_alive() or self.run_dir is None:
            return
        from halo_harness.orchestra import plan as P
        from halo_harness.orchestra.run import request_stop
        try:
            if P.read_decision(self.run_dir) is None and P.split_jobs(self.run_dir):
                P.reject(self.run_dir, "the guided start stopped", by="start")
            request_stop(self.run_dir, "the guided start stopped")
        except Exception:
            pass
        self.runner.join(30)
