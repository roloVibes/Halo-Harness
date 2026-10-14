"""halo_harness.orchestra_cli_run -- the run half of `halo orchestra`.

    halo orchestra run [RUN] [--model REF] [--dry-run]   split, workers, merge, tests, gate, report
    halo orchestra lanes [RUN]                           every lane: state, holder, returns, cost
    halo orchestra report [RUN]                          the run's report and its checks
    halo orchestra stop [RUN] [--reason TEXT]            ask a running run to stop between steps

`run` prints one line per step as it happens (the run log's lines), then
the report. `--dry-run` asks the lead for the split only and prints the
jobs; nothing is claimed, no worktree is made. Exit codes: 0 finished,
1 stopped or not found, 2 a bad request.
"""

from __future__ import annotations

import sys
from pathlib import Path

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra import goal as G


def add_parsers(sub) -> None:
    r = sub.add_parser("run", help="run the pipeline: split, workers, merge, tests, gate, report")
    r.add_argument("run", nargs="?", default=None, help="run id, id prefix or folder (default: latest)")
    r.add_argument("--model", default=None, metavar="REF", help="the model every part uses (default: the roles)")
    r.add_argument("--dry-run", dest="dry_run", action="store_true", help="split only: print the jobs")
    for name, helptext in (("lanes", "every lane: state, holder, returns, cost"),
                           ("report", "the run's report and its checks"),
                           ("stop", "ask a running run to stop between steps")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("run", nargs="?", default=None, help="run id, id prefix or folder (default: latest)")
        if name == "stop":
            s.add_argument("--reason", default="stopped by the user", help="the reason the report shows")


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
        goal = G.load_goal(run_dir / "goal.json")
    except ValueError as e:
        print(f"halo orchestra run: {e}", file=sys.stderr)
        return 2
    from halo_harness.orchestra import adapters
    if args.dry_run:
        return _dry_run(run_dir, goal, adapters.model_call(args.model, goal.lead, cwd=run_dir))
    from halo_harness.orchestra.report import format_report
    from halo_harness.orchestra.run import run
    print(f"run {run_dir.name}: {goal.workers} worker(s), test {goal.test or '(none)'}", flush=True)
    report = run(run_dir, **adapters.real_adapters(run_dir, goal, args.model), on_event=_print_event)
    print(format_report(report))
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
    problems = validate_jobs(data, [u.key for u in units], goal.workers)
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


def cmd_lanes(args, repo: Path) -> int:
    from halo_harness.orchestra.lanes import lane_rows
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    rows = lane_rows(run_dir)
    if not rows:
        print(f"run {run_dir.name}: no lanes yet (halo orchestra run {run_dir.name})")
        return 0
    print(f"run {run_dir.name}: {len(rows)} lane(s)")
    for row in rows:
        print(f"  lane {row.get('lane'):<3} {row.get('state') or '-':<9} returned {row.get('pieces_returned', 0)}  "
              f"${float(row.get('cost_usd') or 0):.4f}  {row.get('holder') or '-':<28} {row.get('title') or ''}")
        print(f"           {', '.join(row.get('claims') or [])}")
    return 0


def cmd_report(args, repo: Path) -> int:
    from halo_harness.orchestra.report import format_report, load_report
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    report = load_report(run_dir)
    if report is None:
        print(f"run {run_dir.name}: no report yet (halo orchestra run {run_dir.name})")
        return 1
    print(format_report(report))
    return 0


def cmd_stop(args, repo: Path) -> int:
    from halo_harness.orchestra.run import request_stop
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    request_stop(run_dir, args.reason)
    print(f"run {run_dir.name}: stop requested ({args.reason}); the runner stops at its next step")
    return 0


HANDLERS = {"run": cmd_run, "lanes": cmd_lanes, "report": cmd_report, "stop": cmd_stop}
