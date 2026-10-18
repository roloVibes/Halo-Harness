"""halo_harness.start.steps_run -- the Orchestra steps of `halo start`: 3 the
goal, 4 the plan, 5 the run, 6 the report and the coach (Halo 3.1.1.0 R1).

Step 3 writes the goal (`plan: review`, the start's lineup) and starts the
run on a daemon thread, in this process: the fake adapters with
`HALO_START_FAKE=1`, else the real ones (`orchestra/adapters.real_adapters`,
the same as `halo orchestra run`), after the lineup preflight. Step 4 waits
for the lead's plan, prints it, then approves it (Enter or --yes), opens
Studio's plan canvas and waits for the decision made there (s), or stops (q,
which rejects the plan). Step 5 prints the lanes table each time it changes
until the run ends. Step 6 is the report's checks and the coach's card.
"""

from __future__ import annotations

import io
import threading
import time
from contextlib import redirect_stdout

from halo_harness.start import steps as S
from halo_harness.start.engine import StepFailed, Stopped


def _repo_flag(run) -> str:
    return f" --repo {run.repo}" if run.repo is not None else ""


def goal_command(run) -> str:
    return f'halo orchestra new --what "{S.GOAL_WHAT}" ...{_repo_flag(run)}; halo orchestra run --review{_repo_flag(run)}'


def goal(run) -> "list[str]":
    from halo_harness.orchestra import goal as G
    from halo_harness.start import sample_repo as R
    g = G.Goal(what=S.GOAL_WHAT, done_when=S.GOAL_DONE, stop_when=S.GOAL_STOP, workers=5, return_cap=2,
               test=R.test_command() if not run.opts.repo else "", files=list(run.opts.files), lineup=run.lineup,
               plan="review", test_timeout_s=120)
    problems = G.validate_goal(g.to_dict())
    if problems:
        raise StepFailed("the goal is not ready: " + "; ".join(problems))
    if not run.fake:
        from halo_harness.lineup_preflight import blocking, lineup_problems, refusal_text
        found = lineup_problems(run.lineup or None, cwd=run.repo, state_dir=run.state_dir)
        if blocking(found):
            raise StepFailed(refusal_text(found, what="the start's run", force="halo orchestra run --force"))
    run.run_dir = G.new_run(run.repo, g)
    _start_runner(run, g)
    return [f"run {run.run_dir.name}: {run.run_dir}", f"WHAT YOU WANT  {g.what}", f"DONE WHEN      {g.done_when}",
            f"STOP WHEN      {g.stop_when}", f"files {', '.join(g.files)}; test {g.test or '(none)'}; lineup {g.lineup}",
            "plan: review -- the run pauses after the lead's split until the plan is approved",
            "models: " + ("the fake lead and workers (HALO_START_FAKE=1)" if run.fake else "your configured roles")]


def _start_runner(run, g) -> None:
    from halo_harness.orchestra.run import run as orchestra_run
    if run.fake:
        from halo_harness.start.fake import adapters
        kwargs = adapters()
    else:
        from halo_harness.orchestra.adapters import real_adapters
        kwargs = real_adapters(run.run_dir, g, run.opts.model)

    def body() -> None:
        try:
            run.result = orchestra_run(run.run_dir, plan_poll_s=min(0.5, run.opts.poll_s), **kwargs) or {}
        except Exception as e:  # the run's own stop lines are in its report; this is anything else
            run.result = {"status": "stopped", "stop_reason": f"{type(e).__name__}: {e}"}
    run.runner = threading.Thread(target=body, name="halo-start-run", daemon=True)
    run.runner.start()


def plan_command(run) -> str:
    return f"halo orchestra plan{_repo_flag(run)}; halo orchestra approve{_repo_flag(run)}"


def _plan_text(run, jobs: list) -> "list[str]":
    from halo_harness.orchestra import plan as P
    from halo_harness.orchestra_cli_plan import print_plan
    out = io.StringIO()
    with redirect_stdout(out):
        print_plan(run.run_dir, jobs, P.check(run.run_dir, jobs))
    return out.getvalue().rstrip("\n").split("\n")


def _wait_planned(run) -> list:
    from halo_harness.orchestra import plan as P
    end = time.monotonic() + run.opts.plan_timeout_s
    while not P.is_planned(run.run_dir):
        if run.cancelled:
            raise Stopped("stopped while the lead split the goal")
        if not run.runner.is_alive():
            raise StepFailed("the run ended before its plan: " + str(run.result.get("stop_reason") or run.result))
        if time.monotonic() > end:
            raise StepFailed(f"no plan after {run.opts.plan_timeout_s:.0f}s: halo orchestra log{_repo_flag(run)}")
        run.wait(run.opts.poll_s)
    return P.current_jobs(run.run_dir)


def plan(run) -> "list[str]":
    from halo_harness.orchestra import plan as P
    jobs = _wait_planned(run)
    lines = _plan_text(run, jobs) + [""] + list(S.PLAN_EXPLAIN)
    run.emit("plan", "running", lines)
    prompt = "Enter approves the plan" + (", s opens it on Studio's plan canvas" if run.opts.studio else "") + \
        ", q stops: "
    answer = run.ask(prompt)
    if answer == "q":
        P.reject(run.run_dir, "stopped in halo start", by="start")
        raise Stopped("the plan was rejected: stopped in halo start")
    if answer == "s" and run.opts.studio:
        return lines + _approve_in_studio(run)
    problems = P.approve(run.run_dir, jobs, by="start")
    if problems:
        raise StepFailed("the plan has problems: " + "; ".join(p["text"] for p in problems))
    return lines + ["", f"approved: {len(jobs)} job(s); the waiting run takes them"]


def _approve_in_studio(run) -> "list[str]":
    from halo_harness.orchestra import plan as P
    url = run.open_studio(run) if run.open_studio else ""
    run.emit("plan", "running", list(run.frames["plan"]["lines"]) +
             ["", f"Studio's plan canvas: {url or 'halo studio --mode orchestra --cwd ' + str(run.repo)}",
              "approve or reject it there; the start waits"])
    while P.read_decision(run.run_dir) is None:
        if run.cancelled or not run.runner.is_alive():
            raise Stopped("stopped while the plan waited in Studio")
        run.wait(run.opts.poll_s)
    decision = P.read_decision(run.run_dir) or {}
    if not decision.get("approved"):
        raise Stopped(f"the plan was rejected in Studio: {decision.get('reason') or 'no reason given'}")
    return ["", f"approved in Studio: {len(decision.get('jobs') or [])} job(s)"]


def run_command(run) -> str:
    return f"halo orchestra lanes{_repo_flag(run)}"


def run(run) -> "list[str]":
    from halo_harness.orchestra.lanes import lane_rows
    from halo_harness.orchestra.view import lane_line
    end, last = time.monotonic() + run.opts.run_timeout_s, None
    while True:
        alive = run.runner.is_alive()
        lines = [lane_line(r) for r in lane_rows(run.run_dir)] or ["no lanes yet"]
        if lines != last:
            run.emit("run", "running", lines)
            last = lines
        if not alive:
            break
        if run.cancelled:
            raise Stopped("stopped during the run")
        if time.monotonic() > end:
            raise StepFailed(f"the run did not end within {run.opts.run_timeout_s:.0f}s")
        run.wait(run.opts.poll_s)
    status = run.result.get("status")
    if status != "finished":
        raise StepFailed(f"the run {status or 'ended'}: {run.result.get('stop_reason') or 'see its report'}")
    return list(last or []) + ["", f"finished: branch {run.result.get('branch') or '?'}"]


def report_command(run) -> str:
    return f"halo orchestra report{_repo_flag(run)}; halo orchestra coach{_repo_flag(run)}"


def report(run) -> "list[str]":
    from halo_harness.orchestra.coach import coach, format_card
    from halo_harness.orchestra.report import format_report, load_report
    data = load_report(run.run_dir) or run.result
    lines = format_report(data).split("\n")
    try:
        run.coach = coach(run.run_dir)
        lines += [""] + format_card(run.coach).split("\n")
    except ValueError as e:
        lines += ["", f"coach: {e}"]
    return lines + ["", S.COACH_APPLY]
