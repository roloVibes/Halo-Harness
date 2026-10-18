"""halo_harness.orchestra_cli_plan -- the reviewed plan half of `halo
orchestra` (Halo 3.0.9.0 round R2; orchestra/plan.py).

    halo orchestra run [RUN] --review             the run pauses after the split until the plan is approved
    halo orchestra plan [RUN]                     the plan as a table, its problems and the decision
    halo orchestra approve [RUN] [--file F]       check the plan (F, else Studio's draft, else the split) and run it
    halo orchestra reject [RUN] --reason TEXT     the run stops with that reason

`approve` writes `<run>/plan.json` only when the plan passes every check
(plan_check.py) and prints each problem otherwise (exit 2). `--file` takes
a JSON file holding `{"jobs": [...]}` or the list itself. The waiting run
(`halo orchestra run --review` in another terminal, or Studio) picks the
decision up within a second. Exit codes: 0 done, 1 not found or nothing to
decide, 2 a bad plan or request.
"""

from __future__ import annotations

import sys
from pathlib import Path

from halo_harness.orchestra import jsonl
from halo_harness.orchestra import plan as P


def add_parsers(sub) -> None:
    for name, helptext in (("plan", "the plan of a review run: its jobs as a table and their problems"),
                           ("approve", "check the plan and let the waiting run take it"),
                           ("reject", "stop the waiting run with a reason")):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("run", nargs="?", default=None, help="run id, id prefix or folder (default: latest)")
        if name == "approve":
            s.add_argument("--file", default=None, metavar="F", help='a JSON file: {"jobs": [...]} or the list')
        if name == "reject":
            s.add_argument("--reason", required=True, help="why: the report shows it")


def _open(args, repo: Path):
    from halo_harness.orchestra_cli import _open as open_run
    return open_run(args, repo)


def _cell(text, width: int) -> str:
    text = str(text or "-")
    return (text if len(text) <= width else text[:width - 1] + "~").ljust(width)


def _needs(job: dict) -> str:
    needs = (job.get("handoff") or {}).get("needs") or []
    return ", ".join(f"{n.get('from')}:{n.get('take')}" for n in needs if isinstance(n, dict))


def print_plan(run_dir: Path, jobs: list, problems: list) -> None:
    print(f"{'job':<8} {'after':<14} {'bio':<12} {'model':<22} {'title'}")
    for job in jobs:
        after = ", ".join(str(a) for a in job.get("after") or [])
        print(f"{_cell(job.get('id'), 8)} {_cell(after, 14)} {_cell(job.get('bio'), 12)} {_cell(job.get('model'), 22)} "
              f"{job.get('title') or ''}")
        print(f"{'':<8} claims: {', '.join(str(c) for c in job.get('claims') or []) or '(none)'}")
        if _needs(job):
            print(f"{'':<8} needs:  {_needs(job)}")
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p['text']}")
    else:
        print("no problems: halo orchestra approve " + run_dir.name)


def cmd_plan(args, repo: Path) -> int:
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    jobs = P.current_jobs(run_dir)
    if not jobs:
        print(f"run {run_dir.name}: no plan yet (the lead has not split the goal)")
        return 1
    decision = P.read_decision(run_dir)
    state = ("approved" if decision.get("approved") else f"rejected: {decision.get('reason')}") if decision else \
        ("waits for review" if P.is_planned(run_dir) else "not waiting for review")
    source = "Studio's draft" if P.read_draft(run_dir) is not None else "the split"
    print(f"run {run_dir.name}: the plan ({len(jobs)} job(s), from {source}) {state}")
    print_plan(run_dir, jobs, P.check(run_dir, jobs))
    return 0


def _decidable(run_dir: Path) -> str:
    decision = P.read_decision(run_dir)
    if decision is not None:
        return f"the plan is already {'approved' if decision.get('approved') else 'rejected'}"
    if not P.split_jobs(run_dir):
        return "there is no plan yet: the lead has not split the goal"
    return ""


def cmd_approve(args, repo: Path) -> int:
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    why = _decidable(run_dir)
    if why:
        print(f"halo orchestra approve: run {run_dir.name}: {why}", file=sys.stderr)
        return 1
    jobs = P.current_jobs(run_dir)
    if args.file:
        data = jsonl.read_json(args.file, None)
        jobs = data.get("jobs") if isinstance(data, dict) else data
        if not isinstance(jobs, list):
            print(f'halo orchestra approve: {args.file} is not {{"jobs": [...]}} or a list of jobs', file=sys.stderr)
            return 2
    problems = P.approve(run_dir, jobs, by="cli")
    if problems:
        print(f"halo orchestra approve: the plan has {len(problems)} problem(s); it still waits:", file=sys.stderr)
        for p in problems:
            print(f"  - {p['text']}", file=sys.stderr)
        return 2
    print(f"run {run_dir.name}: plan approved ({len(jobs)} job(s)); the waiting run takes it"
          + ("" if P.is_planned(run_dir) else f" (start it again with halo orchestra run {run_dir.name})"))
    return 0


def cmd_reject(args, repo: Path) -> int:
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    why = _decidable(run_dir)
    if why:
        print(f"halo orchestra reject: run {run_dir.name}: {why}", file=sys.stderr)
        return 1
    reason = str(args.reason or "").strip()
    if not reason:
        print("halo orchestra reject: say why with --reason TEXT", file=sys.stderr)
        return 2
    P.reject(run_dir, reason, by="cli")
    print(f"run {run_dir.name}: plan rejected ({reason}); the run stops")
    return 0


def set_review(run_dir: Path) -> None:
    """`halo orchestra run --review`: the goal's `plan` becomes review before the run starts."""
    from halo_harness.orchestra.goal import load_goal, save_goal
    goal = load_goal(run_dir / "goal.json")
    if goal.plan != "review":
        goal.plan = "review"
        save_goal(goal, run_dir / "goal.json")


HANDLERS = {"plan": cmd_plan, "approve": cmd_approve, "reject": cmd_reject}
