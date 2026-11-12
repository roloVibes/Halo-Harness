"""halo_harness.packs.grants -- what a pack requests, what you grant, and
enable / disable (Halo 3.2.0.0 R1).

A pack requests permissions in pack.yaml (`mcp:<server>`, `hooks`, `bash`,
`network`, `home-write`). `halo pack enable <id> --grant NAME` (or
`--grant-all`) grants them; the grants live in state.json beside the
enabled flag. A contribution whose permission is not granted does not run:
an MCP server stays out of the session's servers, a hooks file is not
loaded. Grants add up across `enable` calls; `disable` turns the pack off
and clears its grants, so the next `enable` states them again.
"""

from __future__ import annotations

from halo_harness.packs import manifest as MF


#: What each grant lets the pack do, one line (the Pack Manager, `halo pack inspect`, the enable prompt, the README
#: `halo pack new` writes). 3.4.1.2 (PACKS-6, SERVERS-2): said as it is; no grant has a blank line.
WHAT = {"hooks": "its hooks run as commands with your rights (a policy's hooks too): they can read what you can, "
                 "Halo's key file included",
        "bash": "its code may run commands", "network": "its code may reach the network",
        "home-write": "its code may write outside its data folder",
        "studio-script": ("runs this pack's code INSIDE Studio's page with Studio's own power: it can do what you can do "
                          "in Studio, including starting sessions that run commands"),
        "studio-routes": ("runs this pack's Python inside halo (Studio's server) with your rights, Halo's keys and "
                          "Studio's token; turning it off takes effect at Studio's restart for work already started"),
        "services": ("runs a program of this pack in the background while the supervisor runs, with your rights: it can "
                     "read what you can, Halo's key file included"),
        "doctor": "runs this pack's Python inside halo on every halo doctor, with your rights and Halo's keys"}
CLI_WHAT = "runs this pack's Python inside halo for halo {verb} and /{verb}, with your rights and Halo's keys"
#: 3.4.1.2: the grants that run a pack's code with your power; a pack Halo does not ship gets them only on an explicit yes.
POWER = ("studio-script", "studio-routes", "doctor", "services", "hooks")
SHIPPED_ONLY = ("bash", "network", "home-write")  # fences: once any POWER grant is given they fence nothing


def what(perm: str) -> str:
    """The one line a grant's row says; `mcp:<server>` is that server starting, `cli:<verb>` the pack's Python."""
    perm = str(perm)
    if perm.startswith("mcp:"):
        return f"its MCP server {perm[4:]} starts as a program with your rights"
    if perm.startswith("cli:"):
        return CLI_WHAT.format(verb=perm[4:])
    return WHAT.get(perm, "")


def is_power(perm: str) -> bool:
    """3.4.1.2: a grant that runs the pack's code with your power (POWER, cli:<verb>)."""
    return str(perm) in POWER or str(perm).startswith("cli:")


def shipped(pack, state_dir=None) -> bool:
    """3.4.1.2: the pack is one Halo ships (its folder, or its record's source, is halo_harness/templates/packs/<id>)."""
    from halo_harness.packs import state as S
    from halo_harness.packs.discover import same_path
    from halo_harness.packs.fetch import shipped_folder
    folder = shipped_folder(pack.id)
    if folder is None:
        return False
    rec = S.entry(pack.id, state_dir) or {}
    return same_path(pack.root, folder) or same_path(str(rec.get("source") or "?"), folder)


def power_lines(pack, wanted, state_dir=None) -> "list[str]":
    """For a pack Halo does not ship: one line per POWER grant in `wanted`, what it gives ([] for a shipped pack)."""
    if shipped(pack, state_dir):
        return []
    return [f"  {g}: {what(g)}" for g in wanted if is_power(g)]


def needs(pack) -> "list[tuple[str, str]]":
    """`[(permission, what needs it)]` for the pack's contributions."""
    return MF.needed(pack.manifest, pack.root)


def missing(pack, granted) -> "list[tuple[str, str]]":
    """The needs not covered by `granted`."""
    have = set(granted or [])
    return [(perm, why) for perm, why in needs(pack) if perm not in have]


def request_lines(pack, granted) -> "list[str]":
    """One line per permission the pack requests: what needs it, granted or not."""
    have = set(granted or [])
    why = {}
    for perm, what in needs(pack):
        why.setdefault(perm, []).append(what)
    out = []
    for perm in MF.requested(pack.manifest):
        state = "granted" if perm in have else "not granted"
        uses = f" ({', '.join(why[perm])})" if perm in why else ""
        out.append(f"  {perm}{uses}: {state}")
    return out or ["  (it requests no permissions)"]


def _record(pack, data: dict) -> dict:
    from halo_harness.packs import state as S
    rec = dict(S.entry(pack.id, data=data) or {})
    from halo_harness.packs.discover import same_path
    if rec.get("root") and not same_path(rec["root"], pack.root):
        rec = {}  # a record for another folder with this id: this folder starts fresh
    if not rec:
        rec = {"version": pack.version, "source": f"{pack.root} (found in place)", "installed": S.now(),
               "granted": [], "scope": pack.scope, "root": str(pack.root)}
    rec.pop("removed", None)
    return rec


def no_pack_line(pack_id: str) -> str:
    return f"no pack {pack_id!r} here (halo pack list; halo pack install <path|git url>)"


def _not_requested(pack, wanted) -> "list[str]":
    asked = MF.requested(pack.manifest)
    bad = [g for g in wanted if g not in asked]
    return [f"{pack.id} does not request {', '.join(bad)}; it requests: {', '.join(asked) or 'nothing'}"] if bad else []


def enable(pack, *, grant=None, grant_all: bool = False, state_dir=None, confirm=None) -> "tuple[bool, list[str]]":
    """Enable `pack` with the grants given; `(False, [line])` for a grant it does not request. 3.4.1.2: `grant_all` on a
    pack Halo does not ship, with a POWER grant among what it asks, needs `confirm(lines) -> bool` to say yes (the CLI
    asks in a terminal; `--yes`); naming each grant (`grant=[...]`) is that yes."""
    from halo_harness.packs import state as S
    data = S.load(state_dir)
    asked = MF.requested(pack.manifest)
    wanted = list(asked) if grant_all else list(grant or [])
    bad = _not_requested(pack, wanted)
    if bad:
        return False, bad
    power = power_lines(pack, wanted, state_dir) if grant_all else []
    if power and not (confirm is not None and confirm([f"{pack.id} is not a pack Halo ships; --grant-all gives it:"] + power)):
        return False, ([f"{pack.id} is not a pack Halo ships, and --grant-all would give it:"] + power +
                       [f"name each one to grant it (halo pack enable {pack.id} --grant NAME), or answer yes in a "
                        "terminal (--yes without one)"])
    rec = _record(pack, data)
    rec["granted"] = sorted(set(rec.get("granted") or []) | set(wanted))
    rec["enabled"] = True
    rec["version"] = pack.version or rec.get("version", "")
    S.replace(pack.id, rec, state_dir)
    changed(state_dir)
    lines = [f"enabled {pack.id} {pack.version}".rstrip(), "it requests:"] + request_lines(pack, rec["granted"])
    for perm, why in missing(pack, rec["granted"]):
        lines.append(f"not running until granted: {why} (halo pack enable {pack.id} --grant {perm})")
    from halo_harness.packs.setup_state import enable_lines  # 3.3.11.0 R3: its Setup blocks still waiting
    from halo_harness.supervise.services_rows import enable_lines as service_lines  # 3.3.13.0 R3: its services
    return True, lines + enable_lines(pack, state_dir) + service_lines(pack, rec["granted"], state_dir)


def enable_id(pack_id: str, *, grant=None, grant_all: bool = False, cwd=None, state_dir=None,
              confirm=None) -> "tuple[bool, list[str]]":
    """`halo pack enable <id>` (and Studio's Enable, 3.2.0.0 R6): the pack found here by id, then enable."""
    from halo_harness.packs.discover import find
    pack = find(pack_id, cwd=cwd, state_dir=state_dir)
    if pack is None:
        return False, [no_pack_line(pack_id)]
    return enable(pack, grant=grant, grant_all=grant_all, state_dir=state_dir, confirm=confirm)


def grant(pack_id: str, names, *, on: bool = True, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    """`halo pack grant <id> NAME... [--off]` (3.2.0.0 R6, Studio's Grant toggle): give an enabled pack more of
    what it requests (the same as enable --grant), or take grants back; a disabled pack gets its grants as it is enabled."""
    from halo_harness.packs import state as S
    from halo_harness.packs.discover import find
    pack = find(pack_id, cwd=cwd, state_dir=state_dir)
    if pack is None:
        return False, [no_pack_line(pack_id)]
    names = [str(n) for n in names or [] if str(n).strip()]
    if not names:
        return False, [f"name what to grant: halo pack grant {pack.id} NAME (it requests: "
                       f"{', '.join(MF.requested(pack.manifest)) or 'nothing'})"]
    bad = _not_requested(pack, names)
    if bad:
        return False, bad
    data = S.load(state_dir)
    if not S.enabled_for(pack, data):
        return False, [f"{pack.id} is disabled; its grants are given as you enable it: halo pack enable {pack.id} "
                       + " ".join(f"--grant {n}" for n in names)]
    if on:
        return enable(pack, grant=names, state_dir=state_dir)
    have = S.granted(pack.id, data)
    left = [g for g in have if g not in names]
    gone = [n for n in names if n in have]
    S.put(pack.id, {"granted": left}, state_dir)
    changed(state_dir)
    lines = [f"took back {', '.join(gone)} from {pack.id}" if gone else f"{pack.id} had no {', '.join(names)} grant; nothing changed",
             "it requests:"] + request_lines(pack, left)
    for perm, why in missing(pack, left):
        if perm in gone:
            lines.append(f"not running until granted: {why} (halo pack enable {pack.id} --grant {perm})")
    return True, lines


def disable(pack_id: str, *, state_dir=None) -> "tuple[bool, list[str]]":
    from halo_harness.packs import state as S
    rec = S.entry(pack_id, state_dir)
    if rec is None:
        return False, [f"no pack {pack_id!r} is installed (halo pack list)"]
    if not rec.get("enabled"):
        return True, [f"{pack_id} is already disabled; its files stay"]
    cleared = list(rec.get("granted") or [])
    S.put(pack_id, {"enabled": False, "granted": []}, state_dir)
    changed(state_dir)
    lines = [f"disabled {pack_id}: nothing of it runs from now on; its files stay"]
    if cleared:
        lines.append(f"grants cleared: {', '.join(cleared)} (halo pack enable {pack_id} --grant ... states them again)")
    from halo_harness.themes.restore import on_pack_off  # 3.3.12.0 R2: its palette was the theme: the one before it
    return True, lines + on_pack_off(pack_id, verb="disabled", state_dir=state_dir)


def changed(state_dir=None, unload: str = "") -> None:
    """A pack turned on or off: Fleet's capabilities catalog gathers afresh on its next read. `unload`: a pack whose
    files changed (an update, a rollback), whose Studio routes load afresh (notify_studio)."""
    from halo_harness.packs import registry
    registry.invalidate()
    try:
        from halo_harness.peers.catalog import invalidate
        invalidate(state_dir)
    except Exception:
        pass
    notify_studio(unload=unload)


def notify_studio(why: str = "changed", unload: str = "") -> None:
    """3.2.0.0 R3: a Studio this process serves reloads its packs registry now (Studio is never imported here).
    3.3.14.0 R1 (#8): `unload` names a pack updated or rolled back here: its routes module is dropped too."""
    import sys
    routes = sys.modules.get("halo_harness.studio.packs_routes")  # 3.3.13.0 R2: a pack turned off unloads its routes
    if routes is not None:
        if unload:
            routes.unload(unload)
        routes.drop_inactive()
    live = sys.modules.get("halo_harness.studio.packs_studio_live")
    if live is not None:
        live.notify(why)
