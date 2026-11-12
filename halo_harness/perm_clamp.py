"""halo_harness.perm_clamp -- a child engine's mode never above its parent's, now and later (Halo 3.4.1.2, ENGINE-5).

A sub-agent's engine was built once with its clamped mode; the person switching the main session to plan (or from
auto to default) never reached a running or background child, which kept editing. `PermissionEngine.mode` now reads
`clamp(own mode, the parent engine's mode now)` when the engine has a parent (`PermissionEngine(parent=...)`,
agent/subagent.py at spawn), so a parent's change reaches every live child at its next decision; the child's own
mode is kept and comes back when the parent's allows it again, never above it.

    RANK                          dontAsk < default < acceptEdits < auto < bypassPermissions (plan is a write ban)
    clamp(child_mode, parent_mode) -> str
    ref(parent_engine) / link(child_engine, parent_engine)
"""

from __future__ import annotations

import weakref

RANK = {"dontAsk": 0, "default": 1, "acceptEdits": 2, "auto": 3, "bypassPermissions": 4}


def clamp(child: str, parent: str) -> str:
    """plan is sticky either way; otherwise the less permissive of the two (an unknown mode ranks above all)."""
    if parent == "plan" or child == "plan":
        return "plan"
    return parent if RANK.get(child, 99) > RANK.get(parent, 1) else child


def ref(parent_engine):
    """What `PermissionEngine(parent=...)` keeps: a weak reference (a finished parent does not stay alive), or None."""
    return weakref.ref(parent_engine) if parent_engine is not None else None


def link(child_engine, parent_engine) -> None:
    child_engine._parent_engine = ref(parent_engine)


def effective(engine, own: str) -> str:
    ref = getattr(engine, "_parent_engine", None)
    parent = ref() if ref is not None else None
    return own if parent is None else clamp(own, parent.mode)
