"""halo_harness.supervise.goal_cli -- `halo goal` (Halo 3.1.8.0 R1,
docs/COMMANDS-supervise.md): the supervisor's goal queue from a terminal.

    halo goal add "<what>" [--repo DIR] [--done-when ..] [--stop-when ..]
                 [--budget USD] [--lineup NAME] [--as orchestra|job] [--file F ...] [--test CMD] [--review]
                 [--replan none|auto|review]
    halo goal list [--json]
    halo goal show <id> [--json]            the goal and its history lines
    halo goal rm <id>                        drop a goal (not one that runs)
    halo goal hold <id> / release <id>       keep a queued goal from starting / let it
    halo goal pause <id> / resume <id>       pause: hold a queued goal, or cancel a running one's work and re-queue it
    halo goal cancel <id>                    stop a running goal's run or job; state stopped, why cancelled

A goal is run by the supervisor (`halo supervise`); `halo goal add` only
queues it. Exit codes: 0 done, 1 could not (the reason on stderr), 2 usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from halo_harness.supervise import history, queue


def _state_dir():
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def cmd_goal(argv: list) -> int:
    p = argparse.ArgumentParser(prog="halo goal", description="The supervisor's goal queue (docs/SUPERVISE.md).")
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("add", help="queue a goal")
    a.add_argument("what", help="what the goal is")
    a.add_argument("--repo", default=None, help="the repo it works on (default: the current folder)")
    a.add_argument("--done-when", dest="done_when", default="", help="DONE WHEN")
    a.add_argument("--stop-when", dest="stop_when", default="", help="STOP WHEN")
    a.add_argument("--budget", type=float, default=None, metavar="USD", help="the goal's spend cap, a stop")
    a.add_argument("--lineup", default="", help="the lineup (team template) that plays the parts")
    a.add_argument("--as", dest="kind", choices=("orchestra", "job"), default="orchestra", help="run it as an Orchestra run or a plain job")
    a.add_argument("--file", dest="files", action="append", default=None, metavar="F", help="a file the workers share (repeatable, orchestra)")
    a.add_argument("--test", default="", help="the test command the gate runs (orchestra)")
    a.add_argument("--review", action="store_true", help="pause for the plan's review before it runs (orchestra)")
    a.add_argument("--replan", choices=("none", "auto", "review"), default="",
                   help="what the supervisor does when the run drifts (default: supervise.replan)")
    for name in ("list",):
        s = sub.add_parser(name, help="every goal")
        s.add_argument("--json", action="store_true")
    sh = sub.add_parser("show", help="one goal and its history")
    sh.add_argument("id")
    sh.add_argument("--json", action="store_true")
    for name, helptext in (("rm", "drop a goal"), ("hold", "keep a queued goal from starting"),
                           ("release", "let a held goal start"), ("pause", "pause a goal"),
                           ("resume", "resume a paused goal"), ("cancel", "stop a running goal")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("id")
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    state_dir = _state_dir()
    if args.cmd == "add":
        return _add(state_dir, args)
    if args.cmd == "list":
        return _list(state_dir, args.json)
    if args.cmd == "show":
        return _show(state_dir, args.id, args.json)
    if args.cmd in ("rm", "hold", "release", "pause", "resume", "cancel"):
        return _verb(state_dir, args.cmd, args.id)
    p.print_help()
    return 2


def _add(state_dir, args) -> int:
    try:
        goal = queue.add(state_dir, args.what, done_when=args.done_when, stop_when=args.stop_when, repo=args.repo,
                         budget_usd=args.budget, lineup=args.lineup, kind=args.kind, files=args.files, test=args.test,
                         review=args.review, replan=args.replan)
    except ValueError as e:
        print(f"halo goal add: {e}", file=sys.stderr)
        return 1
    print(f"queued {goal['id']}: {goal['what']} ({goal['kind']}, repo {Path(goal['repo']).name})")
    print("the supervisor runs it (start one with `halo supervise` if none is running).")
    return 0


def _list(state_dir, as_json: bool) -> int:
    goals = queue.all_goals(state_dir)
    if as_json:
        print(json.dumps({"goals": goals}, indent=2, default=str))
        return 0
    from halo_harness.supervise import pulse
    if not pulse.live(state_dir):
        print("(no supervisor is running: `halo supervise` starts one)")
    if not goals:
        print("no goals yet. `halo goal add \"<what>\"` queues one.")
        return 0
    for g in goals:
        held = " held" if g.get("held") else ""
        why = f" -- {g['why']}" if g.get("why") else ""
        print(f"  {g['id']}  {g['state']:<8}{held}  ${float(g.get('cost_usd') or 0):.4f}  [{g['kind']}] {g['what'][:60]}{why}")
    return 0


def _show(state_dir, gid: str, as_json: bool) -> int:
    goal = queue.resolve(state_dir, gid)
    if goal is None:
        print(f"halo goal show: no goal {gid!r}", file=sys.stderr)
        return 1
    lines = history.read(state_dir, goal["id"])
    if as_json:
        print(json.dumps({"goal": goal, "history": lines}, indent=2, default=str))
        return 0
    print(f"{goal['id']}: {goal['state']} [{goal['kind']}]  ${float(goal.get('cost_usd') or 0):.4f}")
    print(f"  what: {goal['what']}")
    print(f"  done when: {goal['done_when']}")
    print(f"  stop when: {goal['stop_when']}")
    print(f"  repo: {goal['repo']}" + (f"   lineup: {goal['lineup']}" if goal.get("lineup") else ""))
    if goal.get("budget_usd") is not None:
        print(f"  budget: ${float(goal['budget_usd']):.4f}")
    if goal.get("run_dir"):
        print(f"  run: {Path(goal['run_dir']).name}")
    if goal.get("bg_id"):
        print(f"  job: {goal['bg_id']}")
    from halo_harness.supervise.replan_rows import line as replan_line
    if goal.get("replan") or replan_line(goal):
        print(f"  replan: {goal.get('replan') or 'supervise.replan'}" + (f"; {replan_line(goal)}" if replan_line(goal) else ""))
    if goal.get("failure"):
        f = goal["failure"]
        print(f"  failure: {f.get('kind')} at {f.get('step') or '?'}: {f.get('last_event') or ''}")
    if lines:
        print("  history:")
        for row in lines:
            print(history.format_line(row))
    return 0


def _verb(state_dir, verb: str, gid: str) -> int:
    goal = queue.resolve(state_dir, gid)
    if goal is None:
        print(f"halo goal {verb}: no goal {gid!r}", file=sys.stderr)
        return 1
    gid = goal["id"]
    if verb == "rm":
        if goal.get("state") == "running":
            print(f"halo goal rm: {gid} is running; cancel it first", file=sys.stderr)
            return 1
        queue.remove(state_dir, gid)
        print(f"removed {gid}")
        return 0
    if verb in ("hold", "pause") and goal.get("state") == "queued":
        queue.update(state_dir, gid, lambda g: g.update(held=True, why="held"))
        print(f"{gid} held (it will not start until `halo goal release {gid}`)")
        return 0
    if verb == "release" or (verb == "resume" and goal.get("held")):
        queue.update(state_dir, gid, lambda g: g.update(held=False, why="released"))
        print(f"{gid} released")
        return 0
    if verb in ("cancel", "pause") and goal.get("state") == "running":
        return _cancel(state_dir, goal, requeue=(verb == "pause"))
    if verb == "resume" and goal.get("state") in ("stopped", "parked", "failed"):
        # a fresh start for the time limit (supervise.max_minutes); the run resumes from its checkpoint
        queue.set_state(state_dir, gid, "queued", "resumed", held=False, time_stop=False, started=None)
        print(f"{gid} back in the queue")
        return 0
    print(f"halo goal {verb}: {gid} is {goal.get('state')}, nothing to do", file=sys.stderr)
    return 1


def _cancel(state_dir, goal: dict, *, requeue: bool) -> int:
    from halo_harness.supervise import runner
    gid = goal["id"]
    if goal["kind"] == "job":
        runner.stop_job(goal)
    elif goal.get("run_dir"):
        from halo_harness.orchestra.run import request_stop
        request_stop(Path(goal["run_dir"]), "paused" if requeue else "cancelled")
    if requeue:
        queue.set_state(state_dir, gid, "queued", "paused", held=True)
        print(f"{gid} paused (its work stopped; `halo goal resume {gid}` runs it again from its checkpoint)")
    else:
        queue.set_state(state_dir, gid, "stopped", "cancelled",
                        failure={"kind": "cancelled", "step": "", "last_event": "cancelled from the CLI"})
        from halo_harness.supervise import decisions
        decisions.close_goal(state_dir, gid, "the goal was cancelled")
        print(f"{gid} cancelled")
    return 0
