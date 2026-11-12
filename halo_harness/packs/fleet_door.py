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

3.4.1.2 (PACKS-1): the door imports a `fleet` pack's Python into halo only when it is the pack Halo ships (its record's
source, or its folder, is halo_harness/templates/packs/fleet) or the owner granted it `studio-routes` (a fork that asks
for it); any other pack under the id `fleet` is not opened, and `line()` says so.
"""

from __future__ import annotations

from typing import Optional

PACK = "fleet"


def running(*, cwd=None, state_dir=None):
    """The fleet pack when it is enabled here and it is Halo's own (or granted `studio-routes`), else None (never
    raises)."""
    try:
        from halo_harness.packs import registry
        snap = registry.snapshot(cwd=cwd, state_dir=state_dir)
        pack = next((p for p in snap.active if p.id == PACK), None)
        if pack is None or shipped_or_granted(pack, snap, state_dir):
            _refused.pop("why", None)
            return pack
    except Exception:
        return None
    _refused["why"] = (f"the fleet pack at {pack.root} is not the one Halo ships, so halo does not open its Python "
                       "(halo pack remove fleet, then halo pack install fleet; a fork of it asks for studio-routes)")
    return None


_refused: dict = {}  # 3.4.1.2 (PACKS-1): why an enabled `fleet` pack is not opened


def shipped_or_granted(pack, snap=None, state_dir=None) -> bool:
    """3.4.1.2 (PACKS-1): the pack Halo ships (its record's source or its folder), or one granted `studio-routes`."""
    from halo_harness.packs.discover import same_path
    from halo_harness.packs.fetch import shipped_folder
    shipped = shipped_folder(PACK)
    rec = ((getattr(snap, "state", None) or {}).get("installed") or {}).get(PACK) or {}
    if not rec:
        from halo_harness.packs import state as S
        rec = S.entry(PACK, state_dir) or {}
    if shipped is not None and (same_path(pack.root, shipped) or same_path(str(rec.get("source") or "?"), shipped)):
        return True
    return "studio-routes" in (rec.get("granted") or [])


def module(rel: str, *, cwd=None, state_dir=None):
    """The fleet pack's module `rel`, or None when the pack does not run here (or does not import)."""
    pack = running(cwd=cwd, state_dir=state_dir)
    if pack is None:
        return None
    from halo_harness.packs.contrib_cli import load
    try:
        mod = load(PACK, pack.root, rel)
    except Exception as e:  # 3.4.0.1 (defect 4): kept, so line() says the real error, not "install the pack"
        _failed[rel] = f"{type(e).__name__}: {e}"[:300]
        return None
    _failed.pop(rel, None)
    return mod


_failed: dict = {}  # rel -> why the pack's module did not import (the pack runs)


def call(rel: str, attr: str, *args, default=None, cwd=None, state_dir=None, **kw):
    """`module(rel).<attr>(*args, **kw)`, or `default` when the pack does not run here."""
    mod = module(rel, cwd=cwd, state_dir=state_dir)
    fn: Optional[object] = getattr(mod, attr, None) if mod is not None else None
    return fn(*args, **kw) if callable(fn) else default


def line() -> str:
    from halo_harness.left import packed_line
    if _refused.get("why"):
        return _refused["why"]
    if _failed and running() is not None:
        rel, why = next(reversed(_failed.items()))
        return f"the fleet pack runs, but its {rel} did not load: {why}"
    return packed_line(PACK)
