"""halo_harness.flows.cli -- `halo flow`.

    halo flow new <template> [--name N] [--project SLUG] [--force]   copy a template to ~/.halo/flows/
    halo flow templates                                             the shipped templates
    halo flow validate <name>                                       check a flow file
    halo flow run <name> [--brief T] [--input K=V]... [--asset P]... [--project SLUG]
                         [--set STEP.KEY=V]... [--model M] [--yes] [--watch] [--resume]
    halo flow resume <run> [--yes] [--watch] [--model M]            continue a stopped or killed run
    halo flow status [run]                                          the runs, or one run's steps and gate
    halo flow stop <run> [--reason TEXT]                            stop between steps / at the gate
    halo flow report <run> [--json]                                 the run's report
    halo flow answer <run> <step> accept|redo "<text>"|stop         answer a waiting gate
    halo flow runs                                                  every run, newest last
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from halo_harness.flows import gates, spec as fspec, state


def _resolve_run(ref: str):
    run_dir = state.find_run(ref)
    if run_dir is None:
        print(f"halo flow: no run {ref!r} (halo flow runs lists them)", file=sys.stderr)
    return run_dir


def cmd_new(rest: list) -> int:
    p = argparse.ArgumentParser(prog="halo flow new")
    p.add_argument("template")
    p.add_argument("--name", default=None)
    p.add_argument("--project", default=None)
    p.add_argument("--force", action="store_true")
    a = p.parse_args(rest)
    src = fspec.template_path(a.template)
    if src is None:
        print(f"halo flow new: no template {a.template!r} (templates: {', '.join(fspec.template_names())})", file=sys.stderr)
        return 2
    name = a.name or a.template
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        print(f"halo flow new: {name!r} is not a flow name (letters, digits, - and _)", file=sys.stderr)
        return 2
    dest = fspec.flows_dir() / f"{name}{fspec.SUFFIX}"
    if dest.exists() and not a.force:
        print(f"halo flow new: {dest} already exists (--force replaces it)", file=sys.stderr)
        return 1
    text = src.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^name:.*$", f"name: {name}", text, count=1)
    if a.project:
        from halo_harness.design.store import slugify
        text = re.sub(r"(?m)^project:.*$", f'project: "{slugify(a.project)}"', text, count=1)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    print(f"wrote {dest}")
    for line in fspec.validate_flow(fspec.load_flow(dest)):
        print(f"  {line}")
    print(f"run it: halo flow run {name} --brief \"...\"")
    return 0


def cmd_validate(rest: list) -> int:
    if not rest:
        print("usage: halo flow validate <name>", file=sys.stderr)
        return 2
    path = fspec.find_flow(rest[0])
    if path is None:
        print(f"halo flow validate: no flow {rest[0]!r}", file=sys.stderr)
        return 2
    try:
        lines = fspec.validate_flow(fspec.load_flow(path))
    except ValueError as e:
        print(f"halo flow validate: {e}", file=sys.stderr)
        return 1
    print(f"{path}: {'ok' if not fspec.errors(lines) else 'problems'}")
    for line in lines:
        print(f"  {line}")
    return 1 if fspec.errors(lines) else 0


def cmd_runs(rest: list) -> int:
    rows = state.list_runs()
    if not rows:
        print("no flow runs yet (halo flow run <name>)")
        return 0
    for r in rows:
        print(f"{r['run']}  {str(r['name']):<16} {str(r['status']):<9} ${float(r['cost_usd']):.4f}  project {r['project']}")
    return 0


def cmd_status(rest: list) -> int:
    if not rest:
        return cmd_runs([])
    run_dir = _resolve_run(rest[0])
    if run_dir is None:
        return 2
    info = state.read_run(run_dir)
    flow = info["flow"]
    print(f"run {run_dir.name}: flow {flow.get('name')}, {flow.get('status')}, ${float(flow.get('cost_usd') or 0):.4f}"
          + (f" of ${float(flow['budget_usd']):.2f}" if flow.get("budget_usd") is not None else "")
          + f", project {flow.get('project')}")
    for row, rec in zip(flow.get("steps") or [], info["steps"]):
        print(f"  {str(row.get('id')):<12} {str(row.get('kind')):<8} {str(row.get('state')):<8} "
              f"${float(rec.get('cost_usd') or 0):.4f}" + (f"  error: {rec['error']}" if rec.get("error") else ""))
    gate = info["gate"]
    if gate:
        print(f"waiting at {gate.get('step')} ({gate.get('position')}, round {gate.get('round')}):")
        for line in str(gate.get("text") or "").splitlines()[:12]:
            print(f"    {line}")
        print(f"  answer: halo flow answer {run_dir.name} {gate.get('step')} accept|redo \"<text>\"|stop")
    return 0


def cmd_stop(rest: list) -> int:
    p = argparse.ArgumentParser(prog="halo flow stop")
    p.add_argument("run")
    p.add_argument("--reason", default="stopped by the user")
    a = p.parse_args(rest)
    run_dir = _resolve_run(a.run)
    if run_dir is None:
        return 2
    state.request_stop(run_dir, a.reason)
    print(f"stop requested for {run_dir.name}: {a.reason} (the run stops between steps or at its gate)")
    return 0


def cmd_report(rest: list) -> int:
    from halo_harness.flows.report import format_report
    from halo_harness.orchestra import jsonl
    as_json = "--json" in rest
    rest = [r for r in rest if r != "--json"]
    run_dir = _resolve_run(rest[0] if rest else "last")
    if run_dir is None:
        return 2
    report = jsonl.read_json(run_dir / "report.json", None)
    if not isinstance(report, dict):
        print(f"run {run_dir.name} has no report yet ({state.read_flow(run_dir).get('status')}); halo flow status {run_dir.name}")
        return 1
    print(json.dumps(report, indent=2) if as_json else format_report(report))
    return 0


def cmd_answer(rest: list) -> int:
    if len(rest) < 3:
        print('usage: halo flow answer <run> <step> accept|redo "<text>"|stop', file=sys.stderr)
        return 2
    run_dir = _resolve_run(rest[0])
    if run_dir is None:
        return 2
    ok, msg = gates.write_answer(run_dir, rest[1], rest[2], " ".join(rest[3:]))
    print(msg, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


def cmd_templates(rest: list) -> int:
    for name in fspec.template_names():
        print(name)
    return 0


COMMANDS = {"new": cmd_new, "validate": cmd_validate, "runs": cmd_runs, "status": cmd_status, "stop": cmd_stop,
            "report": cmd_report, "answer": cmd_answer, "templates": cmd_templates}


def cmd_flow(argv: list) -> int:
    from halo_harness.flows.cli_run import cmd_resume, cmd_run
    commands = dict(COMMANDS, run=cmd_run, resume=cmd_resume)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.split("\n\n", 1)[1].rstrip())
        return 0
    fn = commands.get(argv[0])
    if fn is None:
        print(f"halo flow: unknown command {argv[0]!r} ({', '.join(sorted(commands))})", file=sys.stderr)
        return 2
    return fn(argv[1:])
