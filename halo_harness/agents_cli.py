"""halo_harness.agents_cli -- `halo agents` (Halo 3.6.0.0 R5: the agents of ~/.halo/crew/agents; the bios before).

    halo agents list                      yours, this project's (a trusted folder), then the starters to copy
    halo agents show <name>               its file (agent/1), and the workflows and maps that use it
    halo agents new <name> [--from <a>]   one of yours: a copy of a starter or another agent, else a blank one
    halo agents edit <name>               your $VISUAL / $EDITOR on your file; else Studio, Agents -> 1 · Agents, on it
    halo agents try <name> "<request>"    runs it on a throwaway copy of this repo; what it said, used and cost

Studio's Agents -> 1 · Agents is the full editor (the form, Write it for me, Try it, the builder box). `validate`,
`import` and `export --claude-md` went with the bios: an agent file's problems show in `list` and in Studio.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BLANK = {"format": "agent/1", "does": "Say in one sentence what it does.", "instructions": "", "model": "auto",
         "uses": ["read"], "careful": "ask-changes"}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo agents", description="Your agents (~/.halo/crew/agents).")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("list", help="every agent, nearest first")
    show = sub.add_parser("show", help="one agent's file")
    show.add_argument("name")
    new = sub.add_parser("new", help="an agent of yours")
    new.add_argument("name")
    new.add_argument("--from", dest="start", default=None, metavar="AGENT", help="copy this one (a starter or another)")
    edit = sub.add_parser("edit", help="open it in your editor, or in Studio")
    edit.add_argument("name")
    tr = sub.add_parser("try", help="run it once on a throwaway copy of this repo")
    tr.add_argument("name")
    tr.add_argument("request")
    return p


def cmd_agents(argv) -> int:
    from halo_harness import crew_cli_parts as P
    try:
        args = _parser().parse_args(list(argv))
    except SystemExit as e:
        return int(e.code or 0)
    cwd = Path.cwd()
    if args.cmd in (None, "list"):
        return P.print_list("agent", cwd, extra=lambda r: f"model {r.get('model') or '?'}")
    if args.cmd == "show":
        return P.show("agent", args.name, cwd)
    if args.cmd == "new":
        return P.new("agent", args.name, args.start, cwd, BLANK)
    if args.cmd == "edit":
        return P.edit("agent", args.name, cwd)
    from halo_harness.crew import store, trial
    from halo_harness.crew.formats import agent_problems
    got = store.load("agent", args.name, cwd=cwd)
    if got is None:
        print(f"halo agents try: no agent named {args.name!r} (halo agents list)", file=sys.stderr)
        return 1
    raw = store.clean(got)
    bad = agent_problems(raw, name=args.name)
    if bad:
        print(f"halo agents try: cannot try it: {bad[0]}", file=sys.stderr)
        return 1
    print(f"Trying {args.name} on a throwaway copy ({trial.estimate(raw).get('line')})...")
    return P.say_try(P.wait_try(trial.start(raw, args.request, cwd=cwd)))
