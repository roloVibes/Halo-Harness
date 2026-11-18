"""halo_harness.workflows_cli -- `halo workflows` (Halo 3.6.0.0 R5: the workflows of ~/.halo/crew/workflows; the board
of squares before).

    halo workflows list                         yours, this project's (a trusted folder), then the ones that ship with Halo
    halo workflows show <name>                  its file (workflow/1) and the maps it is on
    halo workflows new <name> [--from <start>]  one of yours: a copy of one that ships with Halo (code, plan, review, research, media)
                                                or another workflow, else a blank one-step one
    halo workflows copy <name> [--as <new>]     your own copy of one (one that ships with Halo, a pack's, the project's), to edit
    halo workflows edit <name>                  your $VISUAL / $EDITOR on your file; else Studio, Agents -> 2 · Workflows
    halo workflows try <name> "<request>"       runs it on a throwaway copy of this repo, step by step
    halo workflows run <name> "<request>"       runs it here, for real, on the step runner (each step's agents as
                                                children of a session on your default model)

`enable`, `disable` and `when` went with the board: when main hands a workflow work is the map's line (halo maps,
Studio's Agents -> 3 · Map).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BLANK = {"format": "workflow/1", "for": "Say in one sentence what it is for.",
         "steps": [{"name": "Do it", "agents": ["coder"], "gets": "the task", "hands": "what it did"}]}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo workflows", description="Your workflows (~/.halo/crew/workflows).")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("list", help="every workflow, nearest first")
    show = sub.add_parser("show", help="one workflow's file")
    show.add_argument("name")
    new = sub.add_parser("new", help="a workflow of yours")
    new.add_argument("name")
    new.add_argument("--from", dest="start", default=None, metavar="WORKFLOW", help="copy this one (one that ships with Halo or another)")
    cp = sub.add_parser("copy", help="your own copy of one (one that ships with Halo, a pack's, the project's), to edit")
    cp.add_argument("name")
    cp.add_argument("--as", dest="as_name", default=None, metavar="NAME", help="the copy's name (default my-<name>)")
    edit = sub.add_parser("edit", help="open it in your editor, or in Studio")
    edit.add_argument("name")
    for verb, what in (("try", "once on a throwaway copy of this repo"), ("run", "here, for real, on the step runner")):
        sp = sub.add_parser(verb, help=f"run it {what}")
        sp.add_argument("name")
        sp.add_argument("request")
    return p


def _load(name: str, cwd: Path, verb: str):
    from halo_harness.crew import runner, store
    from halo_harness.crew.formats import workflow_problems
    got = store.load("workflow", name, cwd=cwd)
    _full, said = store.resolve("workflow", name, cwd=cwd)  # 3.6.0.0 R5c: a pack's workflow named bare
    if said:
        print(said, file=sys.stderr)
    if got is None:
        print(f"halo workflows {verb}: no workflow named {name!r} (halo workflows list)", file=sys.stderr)
        return None, None
    wf = store.clean(got)
    bad = workflow_problems(wf, name=name)
    if not bad:
        bad, agents = runner.preflight(wf, lambda n: store.load("agent", n, cwd=cwd))
    if bad:
        print(f"halo workflows {verb}: cannot run it: {bad[0]}", file=sys.stderr)
        return None, None
    return wf, {n: store.clean(a) for n, a in agents.items()}


def _run_here(wf: dict, request: str, cwd: Path) -> int:
    from halo_harness import headless
    from halo_harness.crew.runner_session import run_workflow
    session = headless.build_session(cwd=cwd, print_mode=True, cli_flags={}).session
    try:
        res, text = run_workflow(session.agent_runtime, wf, request, cwd=cwd, tool_id="cli")
    finally:
        session.close_runtimes()
    print(text)
    return 0 if res.state == "done" else 1


def cmd_workflows(argv) -> int:
    from halo_harness import crew_cli_parts as P
    try:
        args = _parser().parse_args(list(argv))
    except SystemExit as e:
        return int(e.code or 0)
    cwd = Path.cwd()
    if args.cmd in (None, "list"):
        return P.print_list("workflow", cwd, extra=lambda r: f"{len(r.get('steps') or [])} step{'' if len(r.get('steps') or []) == 1 else 's'}")
    if args.cmd == "show":
        return P.show("workflow", args.name, cwd)
    if args.cmd == "new":
        return P.new("workflow", args.name, args.start, cwd, BLANK)
    if args.cmd == "copy":  # 3.6.0.0 R5d: own_copy
        from halo_harness.crew_cli_parts import copy
        return copy("workflow", args.name, args.as_name, cwd)
    if args.cmd == "edit":
        return P.edit("workflow", args.name, cwd)
    wf, agents = _load(args.name, cwd, args.cmd)
    if wf is None:
        return 1
    if args.cmd == "run":
        return _run_here(wf, args.request, cwd)
    from halo_harness.crew import trial_flow
    print(f"Trying {args.name} on a throwaway copy, step by step...")
    return P.say_try(P.wait_try(trial_flow.start_flow(wf, agents, args.request, cwd=cwd)))
