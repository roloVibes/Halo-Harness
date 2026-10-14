"""halo_harness.orchestra_cli -- `halo orchestra` (Halo 3.0.3.0).

    halo orchestra new [--what T --done-when T --stop-when T] [--workers N] [--test CMD]
                       [--file F ...] [--lineup L] [--goal FILE] [--repo DIR]
    halo orchestra status [RUN]          the goal, the workflow's steps, live claims, the last events
    halo orchestra claims [RUN]          every live claim: key, holder, state, expiry
    halo orchestra log [RUN] [--since N] the timed run log
    halo orchestra runs                  every run of this repo, oldest first

RUN is a run id (or a unique prefix of one) or a run folder; the latest run
when omitted. `new` prompts for WHAT YOU WANT / DONE WHEN / STOP WHEN when
they are not given and a terminal is attached. See docs/ORCHESTRA.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra import goal as G
from halo_harness.orchestra import jsonl
from halo_harness.orchestra.claims import ClaimLog, clock_text
from halo_harness.orchestra.workflow import summary

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
    for name, helptext in (("status", "the goal, the steps, live claims, the last events"),
                           ("claims", "every live claim"), ("log", "the timed run log")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("run", nargs="?", default=None, help="run id, id prefix or folder (default: latest)")
        if name == "log":
            s.add_argument("--since", type=int, default=0, help="skip the first N entries")
    sub.add_parser("runs", help="every run of this repo")
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
    handler = {"new": _new, "status": _status, "claims": _claims, "log": _log, "runs": _runs}[args.cmd]
    return handler(args, repo)


def _new(args, repo: Path) -> int:
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
    print(f"next: halo orchestra status {run_dir.name}")
    return 0


def _open(args, repo: Path):
    run_dir = G.resolve_run(repo, args.run)
    if run_dir is None:
        names = ", ".join(p.name for p in G.list_runs(repo)) or "none yet"
        what = f"no run named {args.run!r}" if args.run else "no runs in this repo"
        print(f"halo orchestra: {what} (runs: {names}); start one with halo orchestra new", file=sys.stderr)
    return run_dir


def _status(args, repo: Path) -> int:
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    try:
        goal = G.load_goal(run_dir / "goal.json")
    except ValueError as e:
        print(f"halo orchestra status: {e}", file=sys.stderr)
        return 1
    print(f"run {run_dir.name}  ({run_dir})")
    print(f"  WHAT YOU WANT  {goal.what}")
    print(f"  DONE WHEN      {goal.done_when}")
    print(f"  STOP WHEN      {goal.stop_when}")
    print(f"  {goal.workers} worker(s), return cap {goal.return_cap}, test {goal.test or '(none)'}, "
          f"lead {goal.lead}, worker {goal.worker}" + (f", lineup {goal.lineup}" if goal.lineup else ""))
    print(f"  files: {', '.join(goal.files) or '(none)'}")
    graph = jsonl.read_json(run_dir / "workflow.json", {}) or {}
    counts = summary(graph)
    print("  steps: " + (", ".join(f"{v} {k}" for k, v in sorted(counts.items())) or "(no workflow.json)"))
    running = [s["id"] for s in graph.get("steps") or [] if s.get("state") == "running"]
    if running:
        print("  running: " + ", ".join(running))
    active = ClaimLog(run_dir).active()
    print(f"  live claims: {len(active)}")
    tail = run_events.read(run_dir)[-5:]
    if tail:
        print("  last events:")
        for e in tail:
            print("    " + run_events.format_line(e))
    return 0


def _claims(args, repo: Path) -> int:
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    active = ClaimLog(run_dir).active()
    if not active:
        print(f"run {run_dir.name}: no live claims")
        return 0
    print(f"run {run_dir.name}: {len(active)} live claim(s)")
    for c in sorted(active.values(), key=lambda c: c.key):
        print(f"  {c.key:<40} {c.holder:<30} {c.state:<8} until {clock_text(c.expires)}")
    return 0


def _log(args, repo: Path) -> int:
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    entries = run_events.read(run_dir, since=args.since)
    if not entries:
        print(f"run {run_dir.name}: no events" + (f" after entry {args.since}" if args.since else ""))
        return 0
    for e in entries:
        print(run_events.format_line(e))
    return 0


def _runs(args, repo: Path) -> int:
    runs = G.list_runs(repo)
    if not runs:
        print("no runs in this repo yet: halo orchestra new")
        return 0
    for run_dir in runs:
        data = jsonl.read_json(run_dir / "goal.json", {}) or {}
        what = str(data.get("what") or "")
        print(f"{run_dir.name}  {int(data.get('workers') or 0):>2} worker(s)  {what[:60]}")
    return 0
