"""halo_harness.orchestra_cli -- `halo orchestra` (Halo 3.0.3.0).

    halo orchestra new [--what T --done-when T --stop-when T] [--workers N] [--test CMD]
                       [--file F ...] [--lineup L] [--goal FILE] [--repo DIR]
    halo orchestra status [RUN]          the goal, the workflow's steps, live claims, the last events
    halo orchestra claims [RUN]          every live claim: key, holder, state, expiry
    halo orchestra log [RUN] [--since N] the timed run log
    halo orchestra runs                  every run of this repo, oldest first
    halo orchestra run [RUN] [--model REF] [--dry-run]   the pipeline (orchestra_cli_run.py, with stop)
    halo orchestra lanes|report|stop [RUN]
    halo orchestra run --review | plan | approve | reject [RUN]   the reviewed plan (orchestra_cli_plan.py, 3.0.9.0)
    halo orchestra coach [RUN] [--json]  the post-run coach's card (coach_cli.py, 3.0.9.0)

RUN is a run id (or a unique prefix of one) or a run folder; the latest run
when omitted. `new` prompts for WHAT YOU WANT / DONE WHEN / STOP WHEN when
they are not given and a terminal is attached. See docs/ORCHESTRA.md.

This module is the parser (every subcommand), the dispatch, `new` and
`_open` (RUN to a run folder); 3.1.0.0 R2 moved the read-only views
(status, claims, log, runs, lanes, report) to orchestra_cli_views.py, and
orchestra_cli_run.py keeps run and stop.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from halo_harness.orchestra import goal as G
from halo_harness.orchestra import jsonl

_PROMPTS = (("what", "WHAT YOU WANT"), ("done_when", "DONE WHEN"), ("stop_when", "STOP WHEN"))


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo orchestra",
                                description="The Orchestra: several agents, one set of files, nothing lost.")
    sub = p.add_subparsers(dest="cmd")
    n = sub.add_parser("new", help="start a run: goal.json, workflow.json, an empty events log")
    n.add_argument("--what", default=None, help="WHAT YOU WANT")
    n.add_argument("--done-when", dest="done_when", default=None, help="DONE WHEN")
    n.add_argument("--stop-when", dest="stop_when", default=None, help="STOP WHEN")
    n.add_argument("--workers", type=int, default=None, help="1..50 (default 5)")
    n.add_argument("--test", default=None, help="the test command the gate runs")
    n.add_argument("--file", dest="files", action="append", default=None, metavar="F",
                   help="a file the workers share, relative to the repo root (repeatable)")
    n.add_argument("--lineup", default=None, help="the lineup (team template) that plays the parts")
    n.add_argument("--goal", default=None, metavar="FILE", help="start from this goal.json")
    n.add_argument("--workflow", default=None, metavar="PACK/NAME", help="compile a pack's workflow into the run (3.2.0.0 R5)")
    n.add_argument("--input", dest="inputs", action="append", default=[], metavar="K=V", help="a --workflow input (repeatable)")
    for name, helptext in (("status", "the goal, the steps, live claims, the last events"),
                           ("claims", "every live claim"), ("log", "the timed run log")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("run", nargs="?", default=None, help="run id, id prefix or folder (default: latest)")
        if name == "log":
            s.add_argument("--since", type=int, default=0, help="skip the first N entries")
    sub.add_parser("runs", help="every run of this repo")
    r = sub.add_parser("run", help="run the pipeline: split, workers, merge, tests, gate, report")
    r.add_argument("run", nargs="?", default=None, help="run id, id prefix or folder (default: latest)")
    r.add_argument("--model", default=None, metavar="REF", help="the model every part uses (default: the roles)")
    r.add_argument("--dry-run", dest="dry_run", action="store_true", help="split only: print the jobs")
    r.add_argument("--force", action="store_true", help="run even when the lineup preflight finds problems")
    r.add_argument("--review", action="store_true", help="pause after the split until the plan is approved")
    for name, helptext in (("lanes", "every lane: state, holder, returns, cost"),
                           ("report", "the run's report and its checks"),
                           ("stop", "ask a running run to stop between steps")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("run", nargs="?", default=None, help="run id, id prefix or folder (default: latest)")
        if name == "stop":
            s.add_argument("--reason", default="stopped by the user", help="the reason the report shows")
    from halo_harness.orchestra_cli_plan import add_parsers as add_plan_parsers
    add_plan_parsers(sub)
    from halo_harness.coach_cli import add_orchestra_parser
    add_orchestra_parser(sub)
    for s in sub.choices.values():
        s.add_argument("--repo", default=None, help="the repo root (default: the current folder)")
    return p


def cmd_orchestra(argv) -> int:
    parser = _parser()
    args = parser.parse_args(list(argv))
    if args.cmd is None:
        parser.print_help()
        return 0
    repo = Path(args.repo or ".").resolve()
    from halo_harness.coach_cli import cmd_orchestra_coach
    from halo_harness.orchestra_cli_plan import HANDLERS as plan
    from halo_harness.orchestra_cli_run import HANDLERS as running
    from halo_harness.orchestra_cli_views import HANDLERS as views
    handler = dict({"new": _new, "coach": cmd_orchestra_coach}, **views, **running, **plan)[args.cmd]
    return handler(args, repo)


def _new(args, repo: Path) -> int:
    if getattr(args, "workflow", None):  # 3.2.0.0 R5: the goal, hand-offs and pinned plan a workflow compiles to
        from halo_harness.workflows.cli import orchestra_new
        return orchestra_new(args, repo)
    base = {}
    if args.goal:
        base = jsonl.read_json(args.goal, None)
        if not isinstance(base, dict):
            print(f"halo orchestra new: {args.goal} is missing or not a JSON object", file=sys.stderr)
            return 2
    goal = G.Goal.from_dict(base)
    for key in ("what", "done_when", "stop_when", "test", "lineup"):
        if getattr(args, key) is not None:
            setattr(goal, key, getattr(args, key))
    if args.workers is not None:
        goal.workers = args.workers
    if args.files:
        goal.files = list(args.files)
    from halo_harness.packs.lineup_run import goal_defaults  # 3.2.0.0 R2: the lineup's acceptance (test, review)
    taken = goal_defaults(goal, cwd=repo, explicit_test=args.test is not None)
    missing = [(k, label) for k, label in _PROMPTS if not str(getattr(goal, k) or "").strip()]
    if missing and sys.stdin.isatty():
        for key, label in missing:
            setattr(goal, key, input(f"{label}: ").strip())
    elif missing:
        flags = ", ".join("--" + k.replace("_", "-") for k, _ in missing)
        print(f"halo orchestra new: no terminal to ask on; give {flags}", file=sys.stderr)
        return 2
    problems = G.validate_goal(goal.to_dict() if not base else dict(base, **goal.to_dict()))
    if problems:
        print("halo orchestra new: the goal is not ready:", file=sys.stderr)
        for line in problems:
            print(f"  - {line}", file=sys.stderr)
        return 2
    run_dir = G.new_run(repo, goal)
    print(f"run {run_dir.name}: {run_dir}")
    print(f"  {goal.workers} worker(s), files: {', '.join(goal.files) or '(none yet)'}, "
          f"test: {goal.test or '(none yet)'}")
    for line in taken:
        print(f"  {line}")
    print(f"next: halo orchestra status {run_dir.name}")
    return 0


def _open(args, repo: Path):
    run_dir = G.resolve_run(repo, args.run)
    if run_dir is None:
        names = ", ".join(p.name for p in G.list_runs(repo)) or "none yet"
        what = f"no run named {args.run!r}" if args.run else "no runs in this repo"
        print(f"halo orchestra: {what} (runs: {names}); start one with halo orchestra new", file=sys.stderr)
    return run_dir
