"""halo_harness.workflows.square_run -- a square's run, by its engine (Halo 3.3.16.0 R3,
docs/WORKFLOWS-squares.md "The router").

    session    one agent on the lineup's lead (the Agent tool's path, `agent.subagent.run_agent_call`): the
               lead bio's prompt + the task + the files' names, on the lead's model (`auto`: the square's
               own Auto pick for the gaps, `models_auto.pick`); the child shares the parent's permission
               engine and rules (it never runs more permissive), and a watcher stops it (its `abort`) when
               its cost passes the cap, its wall time `limits.wall_s` or its turns `limits.turns`
    orchestra  the compile (`halo workflow run`'s path): inputs `task` and `files`, a new run, run here and
               waited on for at most `limits.wall_s` (then asked to stop)
    mission    run as orchestra while only this harness is here

`gives` is checked on what came back (`check_gives`): text -> a reply; files -> a path list that exists;
report -> an artifact (the run's report, or a file the reply names); repo-change -> the run merged, or
the repo has changes. A miss is one line.
"""

from __future__ import annotations

import contextlib
import io
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

WATCH_S = 0.5


@dataclass
class Outcome:
    text: str = ""
    cost_usd: float = 0.0
    status: str = "done"            # done | failed | stopped
    stop: str = ""                  # why it was stopped (cap, wall, turns)
    gives_miss: str = ""
    run_id: str = ""
    model: str = ""
    report: Optional[dict] = None


def lead_model(wf, task: str, files: list, gaps: list, *, main_ref: str = "", state_dir=None) -> "tuple[str, str]":
    """(model ref or '' for the parent's, the pick's line) for the square's lead."""
    bio, model = wf.contract.lead()
    from halo_harness.models_auto import is_auto, pick
    if model and not is_auto(model):
        return model, ""
    try:
        got = pick(state_dir, needs=[g for g in gaps if g in ("vision", "audio", "video", "pdf")], task_text=task,
                   attachments=files, band=wf.contract.band, main_ref=main_ref, role=bio)
    except Exception:
        return "", ""
    return ("" if got.fallback else got.ref), got.line()


def brief(wf, task: str, files: list, *, cwd=None, state_dir=None) -> str:
    bio, _model = wf.contract.lead()
    prompt = ""
    if bio:
        from halo_harness.agents_yaml import resolve_agent_bio
        data = resolve_agent_bio(bio, cwd=cwd, state_dir=state_dir) or {}
        ctx = data.get("context") if isinstance(data.get("context"), dict) else {}
        prompt = str(ctx.get("system_prompt") or "").strip()
    lines = [prompt] if prompt else []
    lines += [f"You are the square {wf.ref}: {wf.contract.does}", f"Task: {task}"]
    lines += [f"Files: {', '.join(files)}"] if files else []
    lines += [f"Hand back: {', '.join(wf.contract.gives)}."]
    return "\n\n".join(lines)


def _watch(child_box: dict, done: threading.Event, contract, cap: Optional[float], stop: dict, clock) -> None:
    start = clock()
    while not done.wait(WATCH_S):
        child = child_box.get("child")
        row = child_box.get("row") or (lambda: {})
        r = row() or {}
        why = ""
        if cap is not None and float(r.get("cost_usd") or 0.0) > cap:
            why = f"its cost passed the cap ${cap:.2f}"
        elif contract.wall_s and clock() - start > contract.wall_s:
            why = f"it ran past limits.wall_s {contract.wall_s} s"
        elif contract.turns and int(r.get("turns") or 0) > contract.turns:
            why = f"it took more than limits.turns {contract.turns}"
        if why and child is not None:
            stop["why"] = why
            getattr(child, "abort").set()
            return


def run_session(wf, task: str, files: list, *, runtime, tool_id: str, model: str, cap: Optional[float], hops: int,
                spawn: Optional[Callable] = None, on_child: Optional[Callable] = None, clock=time.monotonic) -> Outcome:
    from halo_harness.agent.agent_registry import tree_for
    if spawn is None:
        from halo_harness.agent.subagent import run_agent_call as spawn
    parent = runtime.parent
    tool_input = {"description": f"square {wf.ref}"[:60], "prompt": brief(wf, task, files, cwd=getattr(parent, "cwd", None)),
                  "subagent_type": "general-purpose", **({"model": model} if model else {})}
    box, stop, done = {}, {}, threading.Event()

    def _child(child) -> None:
        child._square_hops = hops  # the depth the square's own agent may still hand off
        box["child"] = child
        aid = getattr(child, "agent_id", "")
        box["row"] = lambda: (tree_for(parent).row(aid) or {}) if aid else {}
        if on_child is not None:
            on_child(child)

    watcher = threading.Thread(target=_watch, args=(box, done, wf.contract, cap, stop, clock), daemon=True)
    watcher.start()
    try:
        _events, result = spawn(runtime=runtime, tool_id=tool_id, tool_input=tool_input, tool_name="Agent", on_child=_child)
    finally:
        done.set()
    text = str(getattr(result, "content", "") or "")
    row = (box.get("row") or (lambda: {}))() or {}
    out = Outcome(text=text, cost_usd=float(row.get("cost_usd") or 0.0), model=model,
                  status="stopped" if stop.get("why") else ("failed" if getattr(result, "is_error", False) else "done"),
                  stop=stop.get("why", ""))
    out.gives_miss = check_gives(wf.contract.gives, text, Path(getattr(parent, "cwd", ".") or "."))
    return out


def parent_permissions(parent) -> "tuple[str, dict]":
    """3.4.1.2 (ENGINE-1): the parent session's mode and its permanent rules (a Skill's temporary grant stays with it):
    what a Workflow-started run's lanes carry, so they never run more permissive than the session that started them."""
    engine = getattr(parent, "permission_engine", None)
    if engine is None:
        return "default", {}
    temp = {id(r) for r in getattr(engine, "_temp_allow_rules", None) or []}
    rules = {"deny": [r.raw for r in engine.deny_rules if r.raw], "ask": [r.raw for r in engine.ask_rules if r.raw],
             "allow": [r.raw for r in engine.allow_rules if r.raw and id(r) not in temp]}
    return str(getattr(engine, "mode", "default") or "default"), {k: v for k, v in rules.items() if v}


def run_orchestra(wf, task: str, files: list, *, repo, wall_s: Optional[int], runner: Optional[Callable] = None,
                  parent=None) -> Outcome:
    from halo_harness.workflows.compile import compile_workflow
    repo = Path(repo)
    compiled = compile_workflow(wf, {"task": task, "files": ", ".join(files)}, repo=repo, cwd=repo)
    if compiled.problems:
        return Outcome(status="failed", text=f"{wf.ref} does not compile: " + "; ".join(compiled.problems[:3]))
    compiled.goal.permission_mode, compiled.goal.permission_rules = parent_permissions(parent)
    from halo_harness.orchestra.test_decide import refused  # its test is decided before a lane is paid for
    said = refused(compiled.goal, repo)
    if said:
        return Outcome(status="failed", text=f"{wf.ref} did not start: {said}")
    from halo_harness.orchestra.goal import new_run
    run_dir = new_run(repo, compiled.goal)
    if runner is None:
        def runner(run_dir_):  # `halo workflow run`'s cmd_run on the run made above
            import argparse
            from halo_harness.orchestra_cli_run import cmd_run
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                cmd_run(argparse.Namespace(run=run_dir_.name, model=None, dry_run=False, force=False, review=False), repo)
    t = threading.Thread(target=runner, args=(run_dir,), daemon=True)
    t.start()
    t.join(timeout=wall_s or None)
    stop = ""
    if t.is_alive():
        from halo_harness.orchestra.run import request_stop
        request_stop(run_dir, f"the square {wf.ref} ran past limits.wall_s {wall_s} s")
        stop = f"it ran past limits.wall_s {wall_s} s"
    from halo_harness.orchestra import jsonl
    report = jsonl.read_json(run_dir / "report.json", {}) or {}
    status = "stopped" if stop else ("done" if report.get("status") == "finished" else "failed")
    text = f"run {run_dir.name}: {report.get('status') or 'no report yet'}" + (f" -- {report['stop_reason']}" if report.get("stop_reason") else "")
    out = Outcome(text=text, cost_usd=float(report.get("cost_usd") or 0.0), status=status, stop=stop, run_id=run_dir.name,
                  report=report)
    out.gives_miss = check_gives(wf.contract.gives, text, repo, report=report, run_dir=run_dir)
    return out


_PATH = re.compile(r"[\w./\\-]+\.[A-Za-z0-9]{1,6}")


def named_files(text: str, cwd: Path) -> "list[str]":
    out = []
    for m in _PATH.findall(text or ""):
        p = Path(m) if Path(m).is_absolute() else Path(cwd) / m
        if p.is_file() and m not in out:
            out.append(m)
    return out


def _repo_changed(cwd: Path) -> bool:
    from halo_harness import subprocess_safe as subprocess
    try:
        got = subprocess.run(["git", "status", "--porcelain"], cwd=str(cwd), capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return got.returncode == 0 and bool(got.stdout.strip())


def check_gives(gives: list, text: str, cwd: Path, *, report: Optional[dict] = None, run_dir=None) -> str:
    """'' when what came back is what the contract gives; else one line naming what is missing."""
    missing = []
    for g in gives or []:
        if g == "text" and not str(text or "").strip():
            missing.append("text (the reply is empty)")
        elif g == "files" and not named_files(text, cwd):
            missing.append("files (the reply names no file that exists)")
        elif g == "report" and not (report or named_files(text, cwd)):
            missing.append("report (no artifact came back)")
        elif g == "repo-change" and not ((report or {}).get("finished") or (report is None and _repo_changed(cwd))):
            missing.append("repo-change (nothing was merged)" if report is not None else "repo-change (the repo has no change)")
    return ("gives missed: " + "; ".join(missing)) if missing else ""
