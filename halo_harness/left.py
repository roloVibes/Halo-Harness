"""halo_harness.left -- what a verb that left the core says (Halo 3.4.0.0 B, "the experiments leave the core").

    LEFT     a verb removed outright: the one line that says when it left and what does its job now
    PACKED   a verb that is a shipped pack's now: (pack id, what it is)

`line(verb)` is that one line (empty for any other verb). `halo <verb>` prints it and exits 2 unless an enabled pack
contributes the verb (packs/contrib_cli.py); `/<verb>` in the terminal says the same.
"""

from __future__ import annotations

LEFT = {
    "team": ("the team file left in 3.4.0.0; a lineup's tiers and blocks (Agents -> Cast, halo teams) and a run's "
             "lanes with their owns lines (a goal run on Agents -> Live, halo orchestra) do its job now"),
}
PACKED = {
    "start": ("first-run", "the guided first run"),
    "coach": ("coach", "the coach"),
    "improve": ("coach", "/improve, the coach's improvement candidates,"),
    "fleet": ("fleet", "the fleet (a hub, its members, missions across halos)"),  # 3.4.0.0 C
    "mission": ("fleet", "a fleet mission (one goal split across halos)"),  # 3.4.0.0 C: `halo mission` = `halo fleet mission`
}


def packed_line(verb: str) -> str:
    pack, what = PACKED[verb]
    here = _installed(pack)  # 3.4.0.1 (live check, defect 3): never "install" what is installed
    if here == "enabled":
        return f"the {pack} pack is enabled but does not run here: halo pack doctor says why"
    if here == "installed":
        return f"the {pack} pack is installed but off: halo pack enable {pack} --grant-all"
    return f"{what} is a pack now: halo pack install {pack}, then halo pack enable {pack} --grant-all"


def _installed(pack: str) -> str:
    """'enabled' (enabled, does not run), 'installed' (installed, off) or '' (not here, or it runs)."""
    try:
        from halo_harness.packs import registry
        snap = registry.snapshot()
    except Exception:
        return ""
    if snap.pack(pack) is None or pack in snap.order:
        return ""
    return "enabled" if pack in snap.enabled else "installed"


def line(verb: str) -> str:
    """The one line for a verb that left the core, else ''."""
    v = str(verb or "").strip().lstrip("/").lower()
    if v in LEFT:
        return LEFT[v]
    return packed_line(v) if v in PACKED else ""
