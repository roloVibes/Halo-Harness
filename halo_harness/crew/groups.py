"""halo_harness.crew.groups -- which group each helper belongs to (Halo 3.6.0.5 "Auto's own groups", B2, B3, B6, B28).

Every helper's row in the live agent tree (agent/agent_registry.py) carries, in every session (data only; Studio draws
the groups on Auto only):

    spawn.task    main's words for the piece of work (the Agent/Task call's `task`), its first 60 characters cut at a
                  word; "" when the call named none
    spawn.group   {key, n, by}, written once at register and never changed; no name (Studio names a group):
                  key "workflow:{W}#{run id}" | "task:{normalized words}" | "reply:{spawn.step}" (at most 120 characters),
                  n 1, 2, 3 ... in the order the groups started, by workflow | task | reply

A child of main is keyed by, first that applies: the workflow run it is a step of (`group_workflow` on its runtime,
tools/workflow.py), main's `task` words (case-blind, runs of spaces one, spaces and . , ; : ! ? dropped at both ends),
the reply that started it. A child of a child is a member of its parent's group. A queued job keeps the group it got
when it was queued. ONE `with tree.lock:` holds the lookup, the new n and `tree.add`, so `tree.add` publishes the row's
frame while the lock is held and group frames leave in the order of their n. Nothing here calls a model or imports the
agent loop.
"""

from __future__ import annotations

import re

from halo_harness.agent.agent_registry import MAIN

TASK_MAX = 60
KEY_MAX = 120
_ENDS = " .,;:!?"


def norm(words) -> str:
    """Lower case; every run of whitespace one space; spaces and . , ; : ! ? stripped at both ends."""
    return re.sub(r"\s+", " ", str(words or "").lower()).strip(_ENDS)


def cut(words, limit: int = TASK_MAX) -> str:
    """The text as is when it fits; else its first `limit` characters cut back to the last space inside them (a hard
    cut at `limit` when there is none)."""
    text = str(words or "")
    if len(text) <= limit:
        return text
    head = text[:limit]
    if text[limit] == " ":
        return head
    at = head.rfind(" ")
    return head[:at] if at > 0 else head


def key_of(step: str, task: str, workflow=None) -> "tuple[str, str]":
    """(key, by) of a child of main: the workflow run, else main's task words, else the reply."""
    if workflow:
        w, run = workflow
        key, by = f"workflow:{w}#{run}", "workflow"
    elif norm(task):
        key, by = f"task:{norm(task)}", "task"
    else:
        key, by = f"reply:{step}", "reply"
    return key[:KEY_MAX], by


def add_in_group(tree, agent_id: str, parent_key: str, spawn: dict, *, task: str = "", workflow=None,
                 row_task=None, **fields) -> None:
    """`tree.add(agent_id, spawn=...)` with the row's `spawn.task` and `spawn.group`, under ONE `tree.lock`. `task` is
    main's words for the piece of work; the row's own `task` field (a queued job's first line), when given, is
    `row_task`."""
    if row_task is not None:
        fields["task"] = row_task
    with tree.lock:
        own = ((tree.rows.get(agent_id) or {}).get("spawn") or {})
        group = own.get("group")
        if group:  # a queued job: the group it got when it was queued
            spawn = {**spawn, "task": own.get("task", cut(task)), "group": dict(group)}
        else:
            if parent_key != MAIN:  # a child of a child: its parent's group, unchanged
                group = ((tree.rows.get(parent_key) or {}).get("spawn") or {}).get("group")
            if group:
                group = dict(group)
            else:
                key, by = key_of(str((spawn or {}).get("step") or ""), task, workflow)
                table = tree.__dict__.setdefault("group_n", {})
                n = table.get(key) or len(table) + 1
                table[key] = n
                group = {"key": key, "n": n, "by": by}
            spawn = {**(spawn or {}), "task": cut(task), "group": group}
        tree.add(agent_id, spawn=spawn, **fields)
