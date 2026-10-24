"""halo_harness.workflows.goal -- a workflow run as a goal of the supervisor
(Halo 3.2.0.0 R5; the supervisor is 3.1.8.0 R1, `halo supervise`,
halo_harness/supervise/, docs/SUPERVISE.md).

`halo workflow run <pack>/<name> --as goal` (and `halo goal add --workflow
<pack>/<name> [--input k=v ...]`) compiles the workflow, makes its Orchestra
run folder at once (the compiled goal.json, hand-offs and pinned plan), and
queues a supervisor goal of kind `orchestra` whose `run_dir` is that folder:
the supervisor's `runner.ensure_run` takes a goal's existing run folder as it
is, runs it with the real adapters behind its budget guard, and resumes it
from its checkpoint (`runner.json`, the run's first unfinished step) after a
crash, a pause or `halo goal resume`. The queued goal carries `workflow`
(`<pack>/<name>`) for `halo goal show`.

    add(compiled, repo, state_dir=None) -> the queued goal (dict)
    queue_compiled(compiled, repo)      -> the CLI's exit code
    cli_add(state_dir, args)            -> `halo goal add --workflow`'s exit code (args: workflow, inputs, repo)

A build without the supervisor answers one line naming `--as orchestra`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def available() -> bool:
    try:
        return importlib.util.find_spec("halo_harness.supervise.queue") is not None
    except (ImportError, ValueError):
        return False


NOT_HERE = ("the supervisor (halo supervise, 3.1.8.0) is not in this build, so there is no goal queue: "
            "run the workflow now with --as orchestra")


def add(compiled, repo, state_dir=None) -> dict:
    from halo_harness.orchestra.goal import new_run
    from halo_harness.supervise import queue
    goal, repo = compiled.goal, Path(repo).resolve()
    run_dir = new_run(repo, goal)
    row = queue.add(state_dir, goal.what.splitlines()[0], done_when=goal.done_when, stop_when=goal.stop_when, repo=repo,
                    budget_usd=goal.budget_usd, lineup=goal.lineup, kind="orchestra", files=list(goal.files),
                    test=goal.test, workers=goal.workers, review=goal.plan == "review",
                    lineup_acceptance=False)  # 3.2.1.0 R1: its test and plan are its stages', not the lineup's
    queue.update(state_dir, row["id"], lambda g: g.update(run_dir=str(run_dir), workflow=goal.workflow.get("ref")))
    return queue.load(state_dir, row["id"]) or dict(row, run_dir=str(run_dir))


def queue_compiled(compiled, repo, state_dir=None) -> int:
    if not available():
        print(f"halo workflow run --as goal: {NOT_HERE}", file=sys.stderr)
        return 2
    row = add(compiled, repo, state_dir)
    print(f"queued {row['id']}: {compiled.goal.workflow.get('ref')} as run {Path(row['run_dir']).name} "
          f"({len(compiled.jobs)} job(s), plan {compiled.goal.plan})")
    print("the supervisor runs it and resumes it from its checkpoint (start one with `halo supervise` if none is running).")
    return 0


def cli_add(state_dir, args) -> int:
    """`halo goal add --workflow <pack>/<name> [--input k=v ...] [--repo DIR]` (supervise/goal_cli.py calls it)."""
    from halo_harness.workflows import spec
    from halo_harness.workflows.cli import parse_inputs
    from halo_harness.workflows.compile import compile_workflow
    repo = Path(getattr(args, "repo", None) or ".").resolve()
    wf, why = spec.find(args.workflow, cwd=repo)
    raw, bad = parse_inputs(getattr(args, "inputs", None))
    if wf is None or bad:
        print(f"halo goal add: {why or '; '.join(bad)}", file=sys.stderr)
        return 1
    compiled = compile_workflow(wf, raw, repo=repo, cwd=repo)
    if compiled.problems:
        print(f"halo goal add: {wf.ref} does not compile:\n" + "\n".join(f"  - {p}" for p in compiled.problems), file=sys.stderr)
        return 1
    row = add(compiled, repo, state_dir)
    print(f"queued {row['id']}: {wf.ref} as run {Path(row['run_dir']).name} (orchestra, repo {repo.name})")
    print("the supervisor runs it (start one with `halo supervise` if none is running).")
    return 0
