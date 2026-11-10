"""halo_harness.workflows.squares_cli -- `halo workflows` (Halo 3.3.16.0 R3, docs/COMMANDS-workflows.md).

    halo workflows list [--json]                        every square with its contract line (and the other workflows)
    halo workflows show <ref> [--json]                  the contract, then the file (inputs, outputs, stages)
    halo workflows enable <ref> [--lineup <name>]       on for the active lineup (the auto lineup: config workflows.enabled)
    halo workflows disable <ref> [--lineup <name>]
    halo workflows test <ref> [--task TEXT]             the check pass + a dry run of the router on a sample task
    halo workflows new <name> --from <square>           copy a square into yours (~/.halo/workflows/<name>.yaml)
    halo workflows check | run <ref> ...                as `halo workflow check | run` (cli.py)

`halo workflow` stays the old verbs' command (list | show | check | run of a pack's workflows). Exit codes:
0 done, 1 not found or a problem, 2 a bad request.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from halo_harness.workflows import registry

SAMPLES = {"pdf": "summarize report.pdf", "vision": "describe what is on screen.png", "audio": "transcribe talk.mp3",
           "video": "say what happens in clip.mp4", "media": "describe what is on screen.png",
           "plan": "plan the move to the new config format", "review": "review the change to the parser",
           "research": "research how other tools cache this", "code": "fix the failing test",
           "work-data": "find last week's notes on the release"}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo workflows", description="Workflow squares: list, enable, test (docs/WORKFLOWS-squares.md).")
    sub = p.add_subparsers(dest="cmd")
    ls = sub.add_parser("list", help="every square with its contract line")
    ls.add_argument("--json", action="store_true")
    sh = sub.add_parser("show", help="a square's contract and file")
    sh.add_argument("ref")
    sh.add_argument("--json", action="store_true")
    for verb in ("enable", "disable"):
        s = sub.add_parser(verb, help=f"{verb} a square for a lineup (default: the active one)")
        s.add_argument("ref")
        s.add_argument("--lineup", default=None)
    t = sub.add_parser("test", help="the check pass and a dry run of the router")
    t.add_argument("ref")
    t.add_argument("--task", default="")
    n = sub.add_parser("new", help="copy a square into yours")
    n.add_argument("name")
    n.add_argument("--from", dest="source", required=True)
    for s in sub.choices.values():
        s.add_argument("--repo", default=None, help="the repo root (default: the current folder)")
    return p


def cmd_workflows(argv) -> int:
    argv = list(argv)
    if argv and argv[0] in ("check", "run"):
        from halo_harness.workflows.cli import cmd_workflow
        return cmd_workflow(argv)
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    if args.cmd is None:
        parser.print_help()
        return 0
    repo = Path(args.repo or ".").resolve()
    if args.cmd == "list":
        return _list(repo, args.json)
    if args.cmd == "new":
        return _new(args.name, args.source, repo)
    from halo_harness.workflows.spec import find
    wf, why = find(args.ref, cwd=repo)
    if wf is None:
        print(f"halo workflows {args.cmd}: {why}", file=sys.stderr)
        return 1
    if args.cmd == "show":
        return _show(wf, repo, args.json)
    if args.cmd == "test":
        return _test(wf, repo, args.task)
    ok, line = (registry.enable if args.cmd == "enable" else registry.disable)(wf.ref, args.lineup, cwd=repo)
    print(line if ok else f"halo workflows {args.cmd}: {line}", file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


def rows(repo: Path) -> "list[dict]":
    on = set(registry.enabled_refs(cwd=repo))
    out = []
    for wf in registry.squares(cwd=repo):
        c = wf.contract
        out.append({"ref": wf.ref, "group": registry.group_of(wf), "origin": wf.origin, "square": c.square,
                    "enabled": wf.ref in on, "line": c.line(wf.ref), "path": str(wf.path), **c.to_json()})
    return out


def _list(repo: Path, as_json: bool) -> int:
    got = rows(repo)
    if as_json:
        print(json.dumps({"lineup": registry.active_lineup(), "squares": got}, indent=2, default=str))
        return 0
    lineup = registry.active_lineup() or "none"
    print(f"squares (lineup {lineup}; * = enabled):")
    for r in got:
        mark = "*" if r["enabled"] else " "
        tail = "" if r["square"] else "  (not a square: its file says no gives)"
        print(f" {mark} [{r['group']:<7}] {r['line']}{tail}")
    return 0


def _show(wf, repo: Path, as_json: bool) -> int:
    c = wf.contract
    if as_json:
        print(json.dumps({"ref": wf.ref, "origin": wf.origin, "path": str(wf.path), "contract": c.to_json(),
                          "problems": registry.check(wf, cwd=repo), "workflow": wf.data}, indent=2, default=str))
        return 0
    bio, model = c.lead()
    print(c.line(wf.ref))
    print(f"  from      {wf.origin} ({wf.path})")
    print(f"  covers    {', '.join(c.covers) or '-'}")
    print(f"  lineup    {c.lineup_name() or (f'lead {bio} on {model or the_parent()}' if bio else '(the session lineup)')}")
    print(f"  engine    {c.engine}" + (" (runs as orchestra while only this harness is here)" if c.engine == "mission" else ""))
    print(f"  costs     {c.costs()}")
    print(f"  limits    {c.limits_chip()}")
    if wf.origin == "pack":
        from halo_harness.workflows.cli import _show as show_file
        return show_file(wf, False)
    for line in registry.check(wf, cwd=repo):
        print(f"  problem   {line}")
    return 0


def slash_text(args: str, cwd) -> str:
    """The TUI's `/workflows [list | show <ref> | test <ref>]`: the same lines as the CLI."""
    import contextlib
    import io
    argv = str(args or "").split() or ["list"]
    if argv[0] not in ("list", "show", "test"):
        argv = ["list"]
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        cmd_workflows(argv + ["--repo", str(cwd or ".")])
    return out.getvalue().rstrip() or "no squares"


def the_parent() -> str:
    return "the session's model"


def _test(wf, repo: Path, task: str) -> int:
    from halo_harness.workflows import router
    from halo_harness.workflows.compile import compile_workflow
    c = wf.contract
    problems = registry.check(wf, cwd=repo)
    if not c.square:
        problems.append("not a square: its file says no gives (the router never picks it)")
    compiled = compile_workflow(wf, {"task": task or "a sample task", "files": ""}, repo=repo, cwd=repo)
    problems += [f"compile: {p}" for p in compiled.problems]
    print(f"{wf.ref}: check {'clean' if not problems else 'found ' + str(len(problems)) + ' problem(s)'}")
    for p in problems:
        print(f"  - {p}")
    samples = [("", task)] if task else [(k, SAMPLES[k]) for k in c.covers if k in SAMPLES][:3] or [("", "a sample task")]
    for cover, sample in samples:
        need = cover if cover and cover not in router.READS + ("media",) else ""  # an ask word is said as the need
        r = router.route(sample, (), need=need, model_ref="", squares=[wf] if c.square else [], takes=["text"])
        covered = [g for g in r.gaps if g in c.covers]
        print(f"  router on {sample!r} (a text-only model): gaps {', '.join(r.gaps) or 'none'} -> "
              + (f"{wf.ref} covers {', '.join(covered)}" if covered and not r.refused else r.why))
    return 1 if problems else 0


def _new(name: str, source: str, repo: Path) -> int:
    from halo_harness.packs import names as N
    from halo_harness.workflows.spec import find
    if not N.is_valid_name(name):
        print(f"halo workflows new: {name!r} is not a name (letters, digits, - and _)", file=sys.stderr)
        return 2
    wf, why = find(source, cwd=repo)
    if wf is None:
        print(f"halo workflows new: {why}", file=sys.stderr)
        return 1
    folder = registry.folders(cwd=repo)[0][1]
    dest = folder / f"{name}.yaml"
    if dest.exists():
        print(f"halo workflows new: {dest} is there already", file=sys.stderr)
        return 1
    text = Path(wf.path).read_text(encoding="utf-8")
    import re
    text = re.sub(r"(?m)^name:.*$", f"name: {name}", text, count=1)
    folder.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {dest} (a copy of {wf.ref}); enable it: halo workflows enable {name}")
    return 0
