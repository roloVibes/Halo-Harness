"""halo_harness.agent.agent_hooks -- where the rest of the harness touches the
live agent tree (Halo 3.0.5.0 "Fleet" round R1; the tree is
agent/agent_registry.py). Every hook swallows its own errors: the tree never
breaks a turn or a spawn.

    turn_started / observe / turn_ended   Session.turn() (agent/loop.py); a child's task and hand-back talk
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
        tree = tree_for(session)
        tree.started(agent_key(session), session, text)
        from halo_harness.live.talk import on_turn_started  # 3.3.16.2: a child's task is its parent's words to it
        on_turn_started(tree, agent_key(session), text)
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
            from halo_harness.live.talk import on_turn_ended  # 3.3.16.2: a child's hand-back, its words to its parent
            on_turn_ended(tree, agent_key(session), session)
        except Exception:
            pass
        try:
            tree.ended(agent_key(session))
        except Exception:
            pass


def spawn_of(tree, parent_aid: str, text: str) -> dict:
    """3.3.16.3 (Live in groups): the step of the parent that started a child -- `step` is the parent's id and its
    reply count at the spawn (every Agent call of one reply shares it), `description` the call's description (else the
    first line of its prompt), `lead` the last line the parent wrote in that reply. Studio's Live groups the children
    of one step and titles the group from these words; nothing here calls a model."""
    with tree.lock:
        turns = (tree.rows.get(parent_aid) or {}).get("turns") or 0
        said = [ln.strip() for ln in str(tree._said.get(parent_aid, "")).splitlines() if ln.strip()]
    return {"step": f"{parent_aid}#{turns}", "description": first_line(text, 80), "lead": first_line(said[-1], 120) if said else ""}


def register_child(parent, child, *, agent_id: str, spec, model: Optional[str], role: Optional[str],
                   background: bool = False, team_control=None, model_reason: Optional[str] = None,
                   task_text: str = "") -> None:
    try:
        tree = tree_for(parent)
        child._fleet_tree = tree
        tree.controls.clear(agent_id)
        entry = (getattr(team_control, "aliases", None) or {}).get(role) if team_control is not None else None
        bio = (entry.get("agent") if isinstance(entry, dict) else None) or getattr(spec, "name", None)
        # 3.1.9.0 R2: under the default lineup only a child on one of its cards is a member
        member = team_control is not None and (entry is not None or not getattr(team_control, "default", False))
        spawn = (tree.row(agent_id) or {}).get("spawn") or spawn_of(tree, agent_key(parent), task_text)  # a queued job keeps its step
        tree.add(agent_id, session=child, parent=agent_key(parent), name=spec.name,
                 role=role, bio=bio, lineup=getattr(team_control, "name", None), model=model, state="queued",
                 kind="background" if background else ("member" if member else "subagent"), transcript=_log_path(child),
                 model_reason=model_reason, opt_ins=getattr(child, "opt_ins", None), spawn=spawn)
    except Exception:
        pass


def register_queued(parent, agent_id: str, *, name: str, task: str, role: Optional[str] = None,
                    description: str = "") -> None:
    try:
        tree = tree_for(parent)
        tree.add(agent_id, parent=agent_key(parent), name=name, kind="subagent", task=first_line(task),
                 role=role, state="queued", spawn=spawn_of(tree, agent_key(parent), f"{description}\n{task}"))
    except Exception:
        pass


def pick_line(r: dict) -> str:
    """3.3.11.0 R2: an `auto` pick's reason, in the words Studio's Roles Live puts on the node."""
    reason = r.get("model_reason")
    if not reason:
        return ""
    model = r.get("model")
    return f"picked at spawn: {r.get('role') or r.get('name') or r.get('agent_id')}{f' on {model}' if model else ''} -- {reason}"


def format_tree(rows: list) -> list:
    """`/agents live`: one line per agent, indented under its parent; 3.3.11.0 R2: the pick's reason on the
    line under it, and an agent whose parent is not in the tree under one "unknown parent" line (Roles Live's tree)."""
    depth: dict = {}
    ids = {r["agent_id"] for r in rows}
    lines: list = []
    for r in rows:
        parent = r.get("parent")
        if parent is not None and parent not in ids:
            if "unknown parent (not in this session's tree)" not in lines:
                lines.append("unknown parent (not in this session's tree)")
            d = 1
        else:
            d = depth.get(parent, -1) + 1
        depth[r["agent_id"]] = d
        cost = f"${r['cost_usd']:.4f}" if isinstance(r.get("cost_usd"), (int, float)) else "$-"
        what = r.get("current") or r.get("task") or ""
        lines.append(f"{'  ' * d}{r['agent_id']:<10} {r.get('name') or '?':<16} {r.get('state') or '?':<8} "
                     f"{cost:>9}  {r.get('model') or '-'}  {what}".rstrip())
        if pick_line(r):
            lines.append(f"{'  ' * (d + 1)}{pick_line(r)}")
    return lines
