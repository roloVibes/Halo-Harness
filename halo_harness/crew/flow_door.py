"""halo_harness.crew.flow_door -- a session's Workflow tool runs a saved crew workflow by name (Halo 3.6.0.0 R2).

The Workflow tool (tools/workflow.py) asks here first: a `name` that is one of your crew workflows (or a trusted
project's; the shipped starters are copied, never run by name) runs on the step runner (crew/runner_session.py), and
its receipt line says so ("crew workflow <name> · ran on the step runner"); any other name goes to the squares as
before. The tool is offered when such a workflow exists, even with no square enabled (workflows/offer.py).

    named(name, cwd) -> dict | None      the workflow file a name means (project, then yours)
    names(cwd) -> [name]                 yours and the project's, with no problem
    tail(cwd) -> str                     what the tool's description adds: " Your workflows (by name): ..."
"""

from __future__ import annotations

from typing import Optional


def named(name: str, cwd=None, state_dir=None) -> Optional[dict]:
    from halo_harness.crew import store
    if not name:
        return None
    for scope in ("project", "yours"):
        got = store.load("workflow", name, cwd=cwd, state_dir=state_dir, scope=scope)
        if got is not None:
            return got
    return None


def rows(cwd=None, state_dir=None) -> list:
    from halo_harness.crew import store
    try:
        return [r for r in store.rows("workflow", cwd=cwd, state_dir=state_dir) if r["_scope"] != "starter" and not r["_problems"]]
    except Exception:
        return []


def names(cwd=None, state_dir=None) -> list:
    out: list = []
    for r in rows(cwd, state_dir):
        if r["name"] not in out:
            out.append(r["name"])
    return out


def tail(cwd=None, state_dir=None) -> str:
    got = rows(cwd, state_dir)
    if not got:
        return ""
    bits = "; ".join(f"{r['name']} ({str(r.get('for') or '').strip()[:80]})" for r in got[:12])
    return f" Your workflows (pass `name`; they run step by step): {bits}."


def run(runtime, name: str, task: str, *, cwd, tool_id: str = "", files=(), spawn=None) -> "Optional[tuple]":
    """(text, is_error) when `name` is a crew workflow, else None (the squares take it)."""
    wf = named(name, cwd)
    if wf is None:
        return None
    from halo_harness.crew.runner_session import run_workflow
    body = {k: v for k, v in wf.items() if not str(k).startswith("_")}
    res, text = run_workflow(runtime, body, task, cwd=cwd, tool_id=tool_id, files=files, spawn=spawn)
    return text, res.state in ("failed",)
