"""halo_harness.agent.agent_hooks -- where the rest of the harness touches the
live agent tree (Halo 3.0.5.0 "Fleet" round R1; the tree is
agent/agent_registry.py). Every hook swallows its own errors: the tree never
breaks a turn or a spawn.

    turn_started / observe / turn_ended   Session.turn() (agent/loop.py)
    register_child                        _build_child_session (agent/subagent.py)
    register_queued                       a count/batch job waiting for a slot
    job_rows                              the background Bash jobs, as leaves under main
    format_tree                           `/agents live`
"""

from __future__ import annotations

from typing import Optional

from halo_harness.agent.agent_registry import FIELDS, _log_path, agent_key, tree_for
from halo_harness.agent.agent_transcript import first_line

_JOB_STATE = {"running": "running", "completed": "done", "killed": "stopped"}


def job_rows(tree) -> list:
    lister = getattr(getattr(tree.session_of(tree.root_id), "job_registry", None), "list_jobs", None)
    try:
        jobs = lister() if callable(lister) else []
    except Exception:
        return []
    out = []
    for j in jobs:
        state = _JOB_STATE.get(j.get("status"), "failed")
        row = {k: None for k in FIELDS}
        row.update(agent_id=f"job:{j.get('id')}", parent=tree.root_id, name="Bash job", kind="job", turns=0,
                   task=first_line(j.get("description") or j.get("command")), since=j.get("started_at"),
                   state=state, current=first_line(j.get("command")) if state == "running" else "", last_text="")
        out.append(row)
    return out


def turn_started(session, text: str) -> None:
    try:
        tree_for(session).started(agent_key(session), session, text)
    except Exception:
        pass


def observe(session, ev) -> None:
    tree = getattr(session, "_fleet_tree", None)
    if tree is not None:
        try:
            tree.observe(agent_key(session), ev)
        except Exception:
            pass


def turn_ended(session) -> None:
    tree = getattr(session, "_fleet_tree", None)
    if tree is not None:
        try:
            tree.ended(agent_key(session))
        except Exception:
            pass


def register_child(parent, child, *, agent_id: str, spec, model: Optional[str], role: Optional[str],
                   background: bool = False, team_control=None) -> None:
    try:
        tree = tree_for(parent)
        child._fleet_tree = tree
        tree.controls.clear(agent_id)
        entry = (getattr(team_control, "aliases", None) or {}).get(role) if team_control is not None else None
        bio = (entry.get("agent") if isinstance(entry, dict) else None) or getattr(spec, "name", None)
        member = team_control is not None or bool(getattr(spec, "dock_label", None))
        tree.add(agent_id, session=child, parent=agent_key(parent), name=getattr(spec, "dock_label", None) or spec.name,
                 role=role, bio=bio, lineup=getattr(team_control, "name", None), model=model, state="queued",
                 kind="background" if background else ("member" if member else "subagent"), transcript=_log_path(child))
    except Exception:
        pass


def register_queued(parent, agent_id: str, *, name: str, task: str, role: Optional[str] = None) -> None:
    try:
        tree_for(parent).add(agent_id, parent=agent_key(parent), name=name, kind="subagent", task=first_line(task),
                             role=role, state="queued")
    except Exception:
        pass


def format_tree(rows: list) -> list:
    """`/agents live`: one line per agent, indented under its parent."""
    depth: dict = {}
    lines = []
    for r in rows:
        d = depth[r["agent_id"]] = depth.get(r.get("parent"), -1) + 1
        cost = f"${r['cost_usd']:.4f}" if isinstance(r.get("cost_usd"), (int, float)) else "$-"
        what = r.get("current") or r.get("task") or ""
        lines.append(f"{'  ' * d}{r['agent_id']:<10} {r.get('name') or '?':<16} {r.get('state') or '?':<8} "
                     f"{cost:>9}  {r.get('model') or '-'}  {what}".rstrip())
    return lines
