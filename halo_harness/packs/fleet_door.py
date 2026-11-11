"""halo_harness.packs.fleet_door -- the core's one door to the shipped `fleet` pack (Halo 3.4.0.0 C: the fleet, its hub,
members and missions, left the core for halo_harness/templates/packs/fleet/).

The core imports nothing from the pack. Where a core path used to reach a fleet module (a mission's attention rows,
the hub's view in Studio, a joined hub's relay when a session opens, `halo studio --fleet`), it asks here: the pack's
module when the pack runs here (enabled, its grants given), else None -- and the core path goes on without it, the
way it does on a machine that never joined a fleet.

    running(cwd=, state_dir=)          the fleet pack (packs/registry Pack) when it runs here, else None
    module(rel, cwd=, state_dir=)      its module `rel` ("fleet/mission_attention.py"), imported through its folder
                                       as `halo_packs.fleet.<path>` (packs/contrib_cli.load), else None
    call(rel, attr, *a, default=None, **kw)   module(rel).attr(*a, **kw), else `default`
    line()                             the one line a fleet door says when the pack is off (halo_harness/left.py)
"""

from __future__ import annotations

from typing import Optional

PACK = "fleet"


def running(*, cwd=None, state_dir=None):
    """The fleet pack when it is enabled here, else None (never raises)."""
    try:
        from halo_harness.packs import registry
        snap = registry.snapshot(cwd=cwd, state_dir=state_dir)
    except Exception:
        return None
    return next((p for p in snap.active if p.id == PACK), None)


def module(rel: str, *, cwd=None, state_dir=None):
    """The fleet pack's module `rel`, or None when the pack does not run here (or does not import)."""
    pack = running(cwd=cwd, state_dir=state_dir)
    if pack is None:
        return None
    from halo_harness.packs.contrib_cli import load
    try:
        return load(PACK, pack.root, rel)
    except Exception:
        return None


def call(rel: str, attr: str, *args, default=None, cwd=None, state_dir=None, **kw):
    """`module(rel).<attr>(*args, **kw)`, or `default` when the pack does not run here."""
    mod = module(rel, cwd=cwd, state_dir=state_dir)
    fn: Optional[object] = getattr(mod, attr, None) if mod is not None else None
    return fn(*args, **kw) if callable(fn) else default


def line() -> str:
    from halo_harness.left import packed_line
    return packed_line(PACK)
