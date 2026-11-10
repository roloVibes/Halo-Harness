"""halo_harness.workflows.offer -- the Workflow tool is offered only when a square is enabled for the session's
lineup (Halo 3.3.16.2, "from a session's own review": on a lineup with no square the tool answered "no square
is enabled for this lineup", a tool that could do nothing and cost prompt tokens every turn).

    drop_unless_enabled(registry, catalog, *, team=None, cwd=None) -> bool   True when it took the tool out

Called once by the session builder (isolation/capabilities.narrow_session), before the wire catalog is
logged: the registry, the session catalog's names and its deferred pool lose `Workflow`, so the tool list
says nothing about squares. A sub-agent inherits the narrowed list.
"""

from __future__ import annotations

from typing import Optional

TOOL = "Workflow"


def squares_on(team: Optional[str] = None, *, cwd=None) -> list:
    try:
        from halo_harness.workflows.registry import enabled_squares
        return enabled_squares(team, cwd=cwd)
    except Exception:
        return []


def drop_unless_enabled(registry, catalog=None, *, team: Optional[str] = None, cwd=None) -> bool:
    if registry is None or registry.get(TOOL) is None or squares_on(team, cwd=cwd):
        return False
    registry.remove_tool(TOOL)
    if catalog is not None:
        if getattr(catalog, "registry", None) is not None and catalog.registry is not registry \
                and catalog.registry.get(TOOL) is not None:
            catalog.registry.remove_tool(TOOL)
        catalog.names[:] = [n for n in catalog.names if n != TOOL]
        getattr(catalog, "deferred", {}).pop(TOOL, None)
    return True
