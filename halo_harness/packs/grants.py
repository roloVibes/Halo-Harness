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


def enable(pack, *, grant=None, grant_all: bool = False, state_dir=None) -> "tuple[bool, list[str]]":
    """Enable `pack` with the grants given; `(False, [line])` for a grant it does not request."""
    from halo_harness.packs import state as S
    data = S.load(state_dir)
    asked = MF.requested(pack.manifest)
    wanted = list(asked) if grant_all else list(grant or [])
    bad = [g for g in wanted if g not in asked]
    if bad:
        return False, [f"{pack.id} does not request {', '.join(bad)}; it requests: {', '.join(asked) or 'nothing'}"]
    rec = _record(pack, data)
    rec["granted"] = sorted(set(rec.get("granted") or []) | set(wanted))
    rec["enabled"] = True
    rec["version"] = pack.version or rec.get("version", "")
    S.replace(pack.id, rec, state_dir)
    changed(state_dir)
    lines = [f"enabled {pack.id} {pack.version}".rstrip(), "it requests:"] + request_lines(pack, rec["granted"])
    for perm, why in missing(pack, rec["granted"]):
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
    return True, lines


def changed(state_dir=None) -> None:
    """A pack turned on or off: Fleet's capabilities catalog gathers afresh on its next read."""
    from halo_harness.packs import registry
    registry.invalidate()
    try:
        from halo_harness.fleet.capabilities import invalidate
        invalidate(state_dir)
    except Exception:
        pass
    notify_studio()


def notify_studio(why: str = "changed") -> None:
    """3.2.0.0 R3: a Studio this process serves reloads its packs registry now (Studio is never imported here)."""
    import sys
    live = sys.modules.get("halo_harness.studio.packs_studio_live")
    if live is not None:
        live.notify(why)
