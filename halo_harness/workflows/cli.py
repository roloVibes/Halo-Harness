"""halo_harness.workflows.cli -- `halo workflow` (Halo 3.2.0.0 R5,
docs/COMMANDS-workflows.md).

    halo workflow list [--json]                          every workflow of the packs that run here
    halo workflow show <pack>/<name> [--json]            the file: inputs, outputs, stages, prerequisites
    halo workflow check <pack>/<name> [--input k=v ...]  compile it: the jobs, the goal, or every problem
    halo workflow run <pack>/<name> [--input k=v ...] [--as orchestra|goal] [--model REF] [--force]
                                                         compile it and run it now as an Orchestra run
                                                         (halo orchestra run), or queue it for the supervisor

Every subcommand takes `--repo DIR` (default: the current folder). A run is
an ordinary Orchestra run (`halo orchestra status|report|stop <run>`); a
workflow whose stage has `gate: human` waits for its plan's review (`halo
orchestra plan|approve <run>`, or Studio's plan canvas). Exit codes: 0 done,
1 not found or the run stopped, 2 a bad request or a compile problem.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from halo_harness.workflows import spec


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo workflow", description="A pack's workflows, compiled to Orchestra runs (docs/WORKFLOWS.md).")
    sub = p.add_subparsers(dest="cmd")
    ls = sub.add_parser("list", help="every workflow of the packs that run here")
    ls.add_argument("--json", action="store_true")
    for name, helptext in (("show", "a workflow's inputs, outputs, stages and prerequisites"),
                           ("check", "compile a workflow with its inputs: the jobs, or every problem"),
                           ("run", "compile a workflow and run it (an Orchestra run), or queue it (--as goal)")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("ref", help="<pack>/<name>, like doc-review/review")
        if name != "show":
            s.add_argument("--input", dest="inputs", action="append", default=[], metavar="K=V",
                           help="an input's value (repeatable)")
        if name != "run":
            s.add_argument("--json", action="store_true")
        if name == "run":
            s.add_argument("--as", dest="kind", choices=("orchestra", "goal"), default="orchestra",
                           help="run it now (orchestra) or queue it for the supervisor (goal)")
            s.add_argument("--model", default=None, metavar="REF", help="the model every part uses (default: the roles)")
            s.add_argument("--force", action="store_true", help="run even when the lineup preflight finds problems")
    for s in sub.choices.values():
        s.add_argument("--repo", default=None, help="the repo root (default: the current folder)")
    return p


def parse_inputs(pairs) -> "tuple[dict, list]":
    out, bad = {}, []
    for pair in pairs or []:
        key, sep, value = str(pair).partition("=")
        if not sep or not key.strip():
            bad.append(f"--input {pair!r} is not K=V")
        else:
            out[key.strip()] = value
    return out, bad


def cmd_workflow(argv) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as e:
        return int(e.code or 0)
    if args.cmd is None:
        parser.print_help()
        return 0
    repo = Path(args.repo or ".").resolve()
    if args.cmd == "list":
        return _list(repo, args.json)
    wf, why = spec.find(args.ref, cwd=repo)
    if wf is None:
        print(f"halo workflow {args.cmd}: {why}", file=sys.stderr)
        return 1
    if args.cmd == "show":
        return _show(wf, args.json)
    raw, bad = parse_inputs(args.inputs)
    if bad:
        print(f"halo workflow {args.cmd}: " + "; ".join(bad), file=sys.stderr)
        return 2
    from halo_harness.workflows.compile import compile_workflow
    compiled = compile_workflow(wf, raw, repo=repo, cwd=repo)
    if compiled.problems:
        print(f"halo workflow {args.cmd}: {wf.ref} does not compile with these inputs:", file=sys.stderr)
        for line in compiled.problems:
            print(f"  - {line}", file=sys.stderr)
        return 2
    if args.cmd == "check":
        return _check(compiled, args.json)
    if args.kind == "goal":
        from halo_harness.workflows.goal import queue_compiled
        return queue_compiled(compiled, repo)
    return run_now(compiled, repo, model=args.model, force=args.force)


def _list(repo: Path, as_json: bool) -> int:
    rows = [{"ref": wf.ref, "pack": wf.pack.id, "name": wf.name, "description": wf.description,
             "stages": [s["id"] for s in spec.stages(wf)], "inputs": list(spec.inputs(wf))}
            for wf in spec.all_workflows(cwd=repo)]
    if as_json:
        print(json.dumps({"workflows": rows}, indent=2))
        return 0
    if not rows:
        print("no workflows: no pack that runs here ships one (halo pack list; a pack with a problem runs nothing: halo pack doctor)")
        return 0
    for r in rows:
        print(f"  {r['ref']:<28} {len(r['stages'])} stage(s): {', '.join(r['stages'])}  inputs: {', '.join(r['inputs']) or '-'}")
        if r["description"]:
            print(f"  {'':<28} {r['description']}")
    return 0


def _stage_line(s: dict, wf) -> str:
    from halo_harness.packs.workflow_stages import role_bio
    bits = [f"role {s.get('role')} -> {role_bio(wf.pack.manifest, wf.pack.root, s.get('role')) or '?'}" if s.get("role") else "the default worker"]
    bits += [f"after {', '.join(s['after'])}"] if s.get("after") else ["at once"]
    each = s.get("for_each")
    bits += [f"one job per file of {each.get('input') if isinstance(each, dict) else each}"] if each else []
    if isinstance(s.get("when"), dict):
        from halo_harness.workflows.conditions import describe
        bits.append(f"when {describe(s['when'])}")
    bits += [f"{k} {s[k]}" for k in ("gate", "retries", "timeout_s", "budget_usd", "after_event") if s.get(k) is not None]
    verify = s.get("verify") if isinstance(s.get("verify"), dict) else {}
    bits += [f"verify `{verify['test']}`"] if verify.get("test") else []
    bits += [f"evidence {', '.join(verify['evidence'])}"] if verify.get("evidence") else []
    return f"    {s['id']:<10} " + "; ".join(bits)


def _show(wf, as_json: bool) -> int:
    if as_json:
        print(json.dumps({"ref": wf.ref, "path": str(wf.path), "workflow": wf.data}, indent=2, default=str))
        return 0
    print(f"{wf.ref} (pack {wf.pack.id} {wf.pack.version}): {wf.description}")
    print("  inputs:")
    for name, sp in spec.inputs(wf).items():
        extra = "required" if sp.get("required") else (f"default {sp.get('default')!r}" if "default" in sp else "optional")
        print(f"    {name:<10} {sp.get('type') or 'text'}, {extra}" + (f" -- {sp['description']}" if sp.get("description") else ""))
    print("  outputs:")
    for name, o in spec.outputs(wf).items():
        print(f"    {name:<10} {o.get('type')} from {o.get('from')}")
    print("  stages:")
    for s in spec.stages(wf):
        print(_stage_line(s, wf))
    pre = wf.data.get("prerequisites") if isinstance(wf.data.get("prerequisites"), dict) else {}
    if pre:
        print("  prerequisites: " + "; ".join(f"{k} {', '.join(map(str, v))}" for k, v in pre.items() if v))
    print(f"  done when: {wf.data.get('done_when') or '(every stage done, its outputs checked)'}")
    return 0


def _check(compiled, as_json: bool) -> int:
    goal = compiled.goal
    if as_json:
        print(json.dumps({"ok": True, "goal": goal.to_dict(), "jobs": compiled.jobs, "skipped": compiled.skipped}, indent=2))
        return 0
    print(f"{goal.workflow['ref']} compiles: {len(compiled.jobs)} job(s), plan {goal.plan}"
          + (f", test `{goal.test}`" if goal.test else "") + (f", budget ${goal.budget_usd:.2f}" if goal.budget_usd is not None else ""))
    for j in compiled.jobs:
        after = ", ".join(j["after"] + [n["from"] + ":" + n["take"] for n in (j["handoff"].get("needs") or [])]) or "-"
        print(f"  {j['id']:<7} {j['stage']:<10} {j['bio'] or '(default worker)':<24} after {after:<24} {j['title']}")
    for x in compiled.skipped:
        print(f"  skipped {x['stage']}: {x['why']}")
    return 0


def run_now(compiled, repo: Path, *, model=None, force: bool = False) -> int:
    from halo_harness.orchestra.goal import new_run
    from halo_harness.orchestra_cli_run import cmd_run
    run_dir = new_run(repo, compiled.goal)
    print(f"workflow {compiled.goal.workflow['ref']}: run {run_dir.name} ({len(compiled.jobs)} job(s))", flush=True)
    return cmd_run(argparse.Namespace(run=run_dir.name, model=model, dry_run=False, force=force, review=False), repo)


def orchestra_new(args, repo: Path) -> int:
    """`halo orchestra new --workflow <pack>/<name> [--input k=v ...]`: the compiled run, made, not started."""
    from halo_harness.orchestra.goal import new_run
    from halo_harness.workflows.compile import compile_workflow
    wf, why = spec.find(args.workflow, cwd=repo)
    raw, bad = parse_inputs(getattr(args, "inputs", None))
    if wf is None or bad:
        print(f"halo orchestra new: {why or '; '.join(bad)}", file=sys.stderr)
        return 2
    compiled = compile_workflow(wf, raw, repo=repo, cwd=repo)
    if compiled.problems:
        print(f"halo orchestra new: {wf.ref} does not compile:\n" + "\n".join(f"  - {p}" for p in compiled.problems), file=sys.stderr)
        return 2
    run_dir = new_run(repo, compiled.goal)
    print(f"run {run_dir.name}: {run_dir}")
    print(f"  workflow {wf.ref}: {len(compiled.jobs)} job(s), plan {compiled.goal.plan}")
    print(f"next: halo orchestra run {run_dir.name}")
    return 0
