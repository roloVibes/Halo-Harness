"""halo_harness.flows.run -- the flow runner.

`run(run_dir, *, adapters, on_event=None, clock=time.time) -> report` walks
the steps in order and dispatches each by kind (intake, roles, org, render,
confirm, post, metrics, done). Each step gets `steps/<n>.json` (written as
it starts and again when it ends) and its cost is charged to the step and to
the run; the run stops with a reason when the run budget is spent, when
`stop.json` appears (between steps and inside a gate), when a gate answers
stop, or when a step fails. `report.json` is written either way.

Resumable: a re-run skips the steps already done (their outputs come back
from steps/<n>.json) and runs the first unfinished one again -- a render
killed half-way renders again, a confirm left waiting opens its gate again.
`adapters.auto_accept` (`--yes`) accepts every human gate.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.flows import steps_agents, steps_media, steps_postiz
from halo_harness.flows.report import write_report
from halo_harness.flows.spec import step_index
from halo_harness.flows.state import Flow, StopFlow, read_flow, read_step, stop_path, stop_requested, write_step
from halo_harness.work.adapters import step as step_unit

HANDLERS = {"intake": steps_agents.intake, "roles": steps_agents.roles, "org": steps_agents.org,
            "render": steps_media.render, "confirm": steps_media.confirm, "post": steps_postiz.post,
            "metrics": steps_postiz.metrics, "done": lambda ctx: {}}


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


class StepCtx:
    """What a step handler sees."""

    def __init__(self, runner: "Runner", n: int, step: dict, record: dict):
        self.runner, self.n, self.step, self.record = runner, n, step, record
        self.sid, self.kind = str(step.get("id")), str(step.get("kind"))
        self.flow, self.spec, self.outputs, self.adapters = runner.flow, runner.spec, runner.outputs, runner.adapters
        self.intake = runner.data.get("intake") or {}
        self.overrides = runner.data.get("overrides") or {}
        self.run, self.cwd = runner.run_dir.name, runner.cwd
        self.cost = 0.0

    def project(self):
        return self.runner.project()

    def step_budget(self) -> Optional[float]:
        caps = [c for c in (_num(self.step.get("budget_usd")), self.runner.remaining()) if c is not None]
        return min(caps) if caps else None

    def save(self) -> None:
        write_step(self.runner.run_dir, self.n, dict(self.record, cost_usd=round(self.cost, 6)))


class Runner:
    def __init__(self, run_dir: Path, adapters, on_event: Optional[Callable], clock: Callable):
        self.run_dir, self.adapters, self.clock = run_dir, adapters, clock
        self.data = read_flow(run_dir)
        self.spec = self.data.get("spec") or {}
        self.steps = [s for s in self.spec.get("steps") or [] if isinstance(s, dict)]
        self.flow = Flow(run_dir, on_event, feed=getattr(adapters, "feed", None), clock=clock)
        self.outputs: dict = {}
        self.total = 0.0
        self.budget = _num(self.data.get("budget_usd"))
        self.cwd = str(getattr(adapters, "cwd", None) or os.getcwd())
        self._project = None

    def remaining(self) -> Optional[float]:
        return None if self.budget is None else max(0.0, self.budget - self.total)

    def project(self):
        if self._project is None:
            from halo_harness.design.store import Project
            slug = str(self.data.get("project") or self.spec.get("name") or "flow")
            state_dir = getattr(self.adapters, "state_dir", None)
            p = Project.open(slug, state_dir=state_dir) or Project.create(slug, state_dir=state_dir)
            if not (p.path / "posts.json").exists():
                (p.path / "posts.json").write_text("[]\n", encoding="utf-8")
            (p.path / "metrics.jsonl").touch(exist_ok=True)
            self._project = p
            self.flow.update(project_path=str(p.path))
        return self._project

    def record_of(self, step_id: str) -> dict:
        return read_step(self.run_dir, step_index(self.spec, step_id) + 1)

    def _execute(self, n: int, step: dict, record: dict) -> dict:
        ctx = StepCtx(self, n, step, record)
        try:
            out = HANDLERS[ctx.kind](ctx)
        except StopFlow as e:
            self._fail(ctx, str(e))
            raise
        except KeyError as e:
            self._fail(ctx, str(e.args[0] if e.args else e))
            raise StopFlow(f"{ctx.sid} failed: {e.args[0] if e.args else e}") from None
        except Exception as e:
            self._fail(ctx, f"{type(e).__name__}: {e}")
            raise StopFlow(f"{ctx.sid} failed: {type(e).__name__}: {e}") from None
        record.update(finished=round(self.clock(), 3), output=out, error=None)
        record["cost_usd"] = round(float(record.get("cost_usd") or 0.0) + ctx.cost, 6)
        write_step(self.run_dir, n, record)
        self.outputs[ctx.sid] = out
        self.total += ctx.cost
        self.flow.update(cost_usd=round(self.total, 6))
        self.flow.log("step", f"{ctx.sid} done (${ctx.cost:.4f})", step=ctx.sid, cost_usd=round(ctx.cost, 6),
                      run_cost_usd=round(self.total, 6))
        self.flow.set(ctx.sid, "done")
        return out

    def _fail(self, ctx: StepCtx, error: str) -> None:
        self.total += ctx.cost
        ctx.record.update(finished=round(self.clock(), 3), error=error)
        ctx.record["cost_usd"] = round(float(ctx.record.get("cost_usd") or 0.0) + ctx.cost, 6)
        write_step(self.run_dir, ctx.n, ctx.record)
        self.flow.update(cost_usd=round(self.total, 6))
        self.flow.set(ctx.sid, "failed", error[:200])

    def rerun(self, step_id: str, instruction: str = "") -> dict:
        """Run an earlier step again (a confirm's redo), the instruction appended to its prompt."""
        i = step_index(self.spec, step_id)
        if i < 0:
            raise StopFlow(f"no step {step_id!r} to redo")
        record = read_step(self.run_dir, i + 1) or {"id": step_id, "kind": self.steps[i].get("kind")}
        if instruction:
            record["instructions"] = list(record.get("instructions") or []) + [instruction]
        record.update(started=round(self.clock(), 3), finished=None, error=None)
        self.flow.set(step_id, "running", "redo" + (f": {instruction}" if instruction else ""))
        write_step(self.run_dir, i + 1, record)
        return self._execute(i + 1, self.steps[i], record)

    def check_stop(self, step: dict) -> None:
        reason = stop_requested(self.run_dir)
        if reason:
            raise StopFlow(reason)
        if self.budget is not None and step.get("kind") != "done" and self.total >= self.budget - 1e-9 and self.total > 0:
            raise StopFlow(f"the run budget ${self.budget:.2f} is spent (${self.total:.4f})")

    def go(self) -> dict:
        started = None
        for i, step in enumerate(self.steps):
            rec = read_step(self.run_dir, i + 1)
            if self.flow.state_of(step.get("id")) in ("done", "skipped") and rec:
                self.outputs[step.get("id")] = rec.get("output")
                self.total += float(rec.get("cost_usd") or 0.0)
            elif started is None:
                started = step.get("id")
        if self.outputs and started:
            self.flow.log("state", f"resume: picking up at {started}", step=started)
        self.flow.update(status="running")
        status, reason = "finished", ""
        try:
            for i, step in enumerate(self.steps):
                sid = step.get("id")
                if self.flow.state_of(sid) in ("done", "skipped"):
                    continue
                self.check_stop(step)
                old = read_step(self.run_dir, i + 1)
                record = step_unit.new_record(sid, step.get("kind"), round(self.clock(), 3), old)  # 3.1.2.0 R1
                self.total += record["cost_usd"]  # what a killed attempt of this step already spent
                self.flow.set(sid, "running")
                write_step(self.run_dir, i + 1, record)
                self._execute(i + 1, step, record)
        except StopFlow as e:
            status, reason = "stopped", str(e)
        report = write_report(self.run_dir, status=status, stop_reason=reason, clock=self.clock)
        self.flow.update(status=status, cost_usd=round(self.total, 6))
        self.flow.log("report", f"run {status}" + (f": {reason}" if reason else "") + f" (${self.total:.4f})",
                      status=status, stop_reason=reason, cost_usd=round(self.total, 6))
        return report


def run(run_dir, *, adapters, on_event: Optional[Callable] = None, clock: Callable = time.time) -> dict:
    from halo_harness.orchestra import jsonl
    run_dir = Path(run_dir)
    done = jsonl.read_json(run_dir / "report.json", None)
    if isinstance(done, dict) and done.get("status") == "finished":
        return done
    if stop_path(run_dir).exists():
        stop_path(run_dir).unlink()
    return Runner(run_dir, adapters, on_event, clock).go()
