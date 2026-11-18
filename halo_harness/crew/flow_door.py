"""halo_harness.crew.flow_door -- a session's Workflow tool runs a saved crew workflow by name (Halo 3.6.0.0 R2).

The Workflow tool (tools/workflow.py) asks here first: a `name` that is one of your crew workflows (or a trusted
project's; the shipped starters are copied, never run by name) runs on the step runner (crew/runner_session.py), and
its receipt line says so ("crew workflow <name> · ran on the step runner"); any other name goes to the squares as
before. The tool is offered when such a workflow exists, even with no square enabled (workflows/offer.py).

    named(name, cwd) -> dict | None      the workflow file a name means (project, then yours, then an enabled pack's;
                                         3.6.0.0 R5c: a pack's is listed, so it runs too; a bare name reaches a pack's
                                         only when no square or starter workflow has it -- the square keeps its name)
    pack_line(name, wf) -> str           "workflow <name> is <pack>--<name> (...)" when a bare name reached a pack's
    names(cwd) -> [name]                 yours, the project's and the enabled packs', with no problem
    tail(cwd) -> str                     what the tool's description adds: " Your workflows (by name): ..."
    listing(cwd, lineup) -> [line]       3.6.0.0 R5c (the judge's S11): what `/workflows` prints -- the same two lists the
                                         tool's description holds (these workflows, then the squares it enables)
"""

from __future__ import annotations

from typing import Optional


def _nearer(name: str, cwd=None, state_dir=None) -> bool:
    """A square (yours, the project's or shipped) or a starter workflow has this bare name: a pack's never takes it."""
    from halo_harness.crew import store
    try:
        if store.find("workflow", name, cwd=cwd, state_dir=state_dir, scope="starter") is not None:
            return True
        from halo_harness.workflows.registry import find_bare
        return find_bare(name, cwd=cwd, state_dir=state_dir)[0] is not None
    except Exception:
        return True  # unsure: the squares keep the name


def named(name: str, cwd=None, state_dir=None) -> Optional[dict]:
    from halo_harness.crew import store
    if not name:
        return None
    for scope in ("project", "yours"):
        got = store.load("workflow", name, cwd=cwd, state_dir=state_dir, scope=scope)
        if got is not None:
            return got
    if "--" not in name and _nearer(name, cwd, state_dir):  # 3.6.0.0 R5c (the judge's S-a): the square keeps its name
        return None
    return store.load("workflow", name, cwd=cwd, state_dir=state_dir, scope="pack")


def pack_line(name: str, wf: Optional[dict]) -> str:
    """The line a bare name that reached a pack's workflow prints (its full `<pack>--<name>`), else ""."""
    full = str((wf or {}).get("name") or "")
    if (wf or {}).get("_scope") != "pack" or not full or full == name:
        return ""
    return f"workflow {name} is {full} (an enabled pack's; its full name from now on)"


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


def listing(cwd=None, lineup=None, state_dir=None) -> list:
    """The Workflow tool's two lists, as lines: the crew workflows it runs by name, then the squares it enables."""
    from halo_harness.crew import store
    out = [f"Workflows a session runs by name (the Workflow tool's list):"]
    got = rows(cwd, state_dir)
    out += [f"  {r['name']}  ({store.scope_words(r['_scope'])})  {' '.join(str(r.get('for') or '').split())[:90]}" for r in got] or ["  none yet"]
    try:
        from halo_harness.workflows.registry import active_lineup, enabled_squares
        squares = enabled_squares(lineup if lineup is not None else active_lineup(), cwd=cwd, state_dir=state_dir)
    except Exception:
        squares = []
    out.append("Squares it enables (config workflows.enabled):")
    out += [f"  {wf.ref}" for wf in squares] or ["  none"]
    out.append("halo workflows list shows every workflow file, the ones that ship with Halo too (Copy makes it yours); /workflows show <name>")
    return out


def run(runtime, name: str, task: str, *, cwd, tool_id: str = "", files=(), spawn=None) -> "Optional[tuple]":
    """(text, is_error) when `name` is a crew workflow, else None (the squares take it). On a map (any depth: frames
    only, never routing) the run is one hand-off from the REAL caller's box to `workflow:{W}`, its steps' `map_step`
    frames keyed to it and each step's child tagged; its end is sent in a finally (3.6.0.2 R48, R13)."""
    wf = named(name, cwd)
    if wf is None:
        return None
    from halo_harness.crew import map_events
    from halo_harness.crew.map_run import control
    from halo_harness.crew.runner_session import run_workflow
    said = pack_line(name, wf)  # 3.6.0.0 R5c: a pack's workflow named bare, said once (from the file named() found)
    body = {k: v for k, v in wf.items() if not str(k).startswith("_")}
    mc = control(runtime)
    if mc is None:
        res, text = run_workflow(runtime, body, task, cwd=cwd, tool_id=tool_id, files=files, spawn=spawn)
        return (f"{said}\n{text}" if said else text), res.state in ("failed",)
    w, by = str(body.get("name") or name), map_events.caller_box(runtime)
    h, why, bad = {"box": "workflow:" + w, "name": w, "kind": "workflow"}, f"named by {by}", True
    t0 = map_events.hop(runtime, mc, h, why, task, "start", workflow=w)["t"]
    try:
        res, text = run_workflow(runtime, body, task, cwd=cwd, tool_id=tool_id, files=files, spawn=spawn,
                                 emit=map_events.step_emit(runtime, mc, h["box"], w), crew=(mc, by))
        bad = res.state in ("failed",)
        return (f"{said}\n{text}" if said else text), bad
    finally:
        map_events.hop(runtime, mc, h, why, task, "end", t0=t0, workflow=w, error=bad)
