"""halo_harness.orchestra_cli_run -- `halo orchestra run | stop`: driving a
run (Halo 3.0.3.0 round R2; 3.1.0.0 R2 moved lanes and report to
orchestra_cli_views.py and the parsers to orchestra_cli.py).

    halo orchestra run [RUN] [--model REF] [--dry-run] [--force]   split, workers, merge, tests, gate, report
    halo orchestra stop [RUN] [--reason TEXT]            ask a running run to stop between steps
    halo orchestra run [RUN] --review | plan | approve | reject   the reviewed plan (orchestra_cli_plan.py)

`run` prints one line per step as it happens (the run log's lines), then
the report. `--dry-run` asks the lead for the split only and prints the
jobs; nothing is claimed, no worktree is made. Before either, the run-start
preflight (lineup_preflight.py) checks the run's lineup (the goal's
`lineup`, else the active team) and lists every problem that would make
members come back empty, with its fix, then stops; `--force` runs anyway.
Exit codes: 0 finished, 1 stopped or not found, 2 a bad request or a
preflight stop.
"""

from __future__ import annotations

import sys
from pathlib import Path

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra import goal as G


def _open(args, repo: Path):
    from halo_harness.orchestra_cli import _open as open_run
    return open_run(args, repo)


def _print_event(entry: dict) -> None:
    if entry.get("kind") in ("state", "merge", "gate", "report"):
        print(run_events.format_line(entry), flush=True)


def cmd_run(args, repo: Path) -> int:
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    try:
        if getattr(args, "review", False):
            from halo_harness.orchestra_cli_plan import set_review
            set_review(run_dir)
        goal = G.load_goal(run_dir / "goal.json")
    except ValueError as e:
        print(f"halo orchestra run: {e}", file=sys.stderr)
        return 2
    if not getattr(args, "force", False):
        from halo_harness.lineup_preflight import blocking, lineup_problems, refusal_text
        problems = lineup_problems(goal.lineup or None, cwd=repo)
        if blocking(problems):
            print(refusal_text(problems, what=f"run {run_dir.name}"), file=sys.stderr)
            return 2
    from halo_harness.orchestra import adapters
    if args.dry_run:
        return _dry_run(run_dir, goal, adapters.model_call(args.model, goal.lead, cwd=run_dir))
    from halo_harness.orchestra.report import format_report
    from halo_harness.orchestra.run import run
    print(f"run {run_dir.name}: {goal.workers} worker(s), test {goal.test or '(none)'}", flush=True)
    report = run(run_dir, **adapters.real_adapters(run_dir, goal, args.model), on_event=_print_event)
    print(format_report(report, run_dir))
    return 0 if report.get("status") == "finished" else 1


def _dry_run(run_dir: Path, goal, call) -> int:
    from halo_harness.orchestra.run import goal_units
    from halo_harness.orchestra.split import StopRun, parse_answer, split_prompt, validate_jobs
    repo = G.repo_root_of(run_dir)
    try:
        units = goal_units(repo, goal)
    except StopRun as e:
        print(f"halo orchestra run: {e}", file=sys.stderr)
        return 1
    answer = call(split_prompt(goal, units))
    text = answer.get("text") if isinstance(answer, dict) else (answer[0] if isinstance(answer, tuple) else answer)
    data = parse_answer(str(text or ""))
    if isinstance(data, dict) and data.get("stop"):
        print(f"the lead would stop the run: {data['stop']}")
        return 1
    problems = validate_jobs(data, [u.key for u in units], goal.workers, getattr(goal, "handoffs", None))
    if problems:
        print("the lead's split does not pass the check:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"run {run_dir.name}: the lead's split, {len(data['jobs'])} job(s) (dry run: nothing claimed)")
    for i, job in enumerate(data["jobs"], 1):
        print(f"  job-{i}  worker {i}  {job['title']}")
        print(f"          claims: {', '.join(job['claims'])}")
    return 0


def cmd_stop(args, repo: Path) -> int:
    from halo_harness.orchestra.run import request_stop
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    request_stop(run_dir, args.reason)
    print(f"run {run_dir.name}: stop requested ({args.reason}); the runner stops at its next step")
    return 0


HANDLERS = {"run": cmd_run, "stop": cmd_stop}
