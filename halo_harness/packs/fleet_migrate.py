"""halo_harness.packs.fleet_migrate -- a halo that had a fleet before 3.4.0.0 keeps it (Halo 3.4.0.0 C: the fleet
left the core for the shipped `fleet` pack).

On the first run after the update, `halo` (any verb, cli.py) looks once for fleet state in this home:

    a joined hub        fleet.json lists one (peers/store.has_hubs)
    a hub of its own    <state>/fleet/hub/members.json (members paired with `halo fleet pair`)
    missions            <state>/fleet/missions/ holds one
    fleet keys          config.json `fleet.` keys only the pack reads (share, hub, mission, recall, shared_dir, ...)

When it finds any and the fleet pack is not installed here, it installs the shipped pack, enables it with every grant
it asks for (cli:fleet, cli:mission) and says so in one line. Nothing in the home is deleted or rewritten; the marker
`<state>/packs/.fleet-migrated` keeps it from asking again (a pack you disable later stays disabled).

    run(state_dir=None) -> str     the one line ('' when nothing was done)
    say()                          run() for this home, its line on stderr
"""

from __future__ import annotations

from pathlib import Path

MARKER = ".fleet-migrated"
PACK_KEYS = ("share", "allow_answers", "share_captures", "hub", "tags", "capabilities", "ollama", "recall", "shared_dir",
             "mission")
LINE = ("halo: the fleet is a pack since 3.4.0.0, and this halo had a fleet, so the fleet pack is installed and on "
        "(halo pack disable fleet turns it off; docs/FLEET.md)")


def _home(state_dir=None) -> Path:
    if state_dir is not None:
        return Path(state_dir)
    from halo_harness.peers.identity import home
    return home()


def had_fleet(state_dir=None) -> bool:
    home = _home(state_dir)
    from halo_harness.peers.store import has_hubs
    if has_hubs(home) or (home / "fleet" / "hub" / "members.json").is_file():
        return True
    try:
        if any((home / "fleet" / "missions").iterdir()):
            return True
    except OSError:
        pass
    from halo_harness.peers.identity import _read_config
    fleet = _read_config(home / "config.json").get("fleet")
    return isinstance(fleet, dict) and any(k in fleet for k in PACK_KEYS)


def run(state_dir=None, cwd=None) -> str:
    """Install and enable the fleet pack once for a home that had a fleet; the line to print, else ''."""
    home = _home(state_dir)
    marker = home / "packs" / MARKER
    if marker.exists() or not home.is_dir():
        return ""
    try:
        if not had_fleet(home):
            return ""
        from halo_harness.packs import grants as G, registry
        from halo_harness.packs.discover import find
        from halo_harness.packs.install import install
        line = ""
        if find("fleet", cwd=cwd, state_dir=home) is None:
            ok, _lines = install("fleet", cwd=cwd, state_dir=home)
            registry.invalidate()
            pack = find("fleet", cwd=cwd, state_dir=home) if ok else None
            if pack is not None and G.enable(pack, grant_all=True, state_dir=home)[0]:
                line = LINE
            registry.invalidate()
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("3.4.0.0\n", encoding="utf-8")
        return line
    except Exception:  # a migration never stands in the way of the verb that was asked for
        return ""


def say() -> None:
    import sys
    line = run()
    if line:
        print(line, file=sys.stderr)
