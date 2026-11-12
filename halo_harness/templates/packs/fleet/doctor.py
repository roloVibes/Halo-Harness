"""The fleet pack's doctor rows (`contributes.doctor`, Halo 3.4.0.1 "Found live", defect 7): `halo doctor` shows them
under "From packs" while the pack is enabled and granted `doctor`.

- the pack runs, and whether this machine serves a hub (its address, members);
- on Windows, whether the firewall lets other machines reach the hub's port (read-only, peers/firewall.py): the same
  line the hub says when it starts, with the command an administrator runs;
- each hub this harness joined, and whether it answers (a short ping; offline mode reads none).
"""

from __future__ import annotations

from halo_harness.ext import core as _core


def _serving(ctx) -> list:
    from .fleet import hub as H
    identity = _core.module("peers.identity")
    info = H.read_info(ctx.state_dir)
    port = int(info["port"]) if info else identity.hub_port()
    head = (f"the fleet pack runs; this machine serves the hub {info.get('name') or ''} at {info.get('url')}".replace("  ", " ")
            if info else f"the fleet pack runs; no hub runs here (halo studio --fleet or halo fleet serve, port {port})")
    out: list = [head]
    if info and str(info.get("bind") or "").startswith("127."):
        return out
    wall = _core.get("peers.firewall", "line")(port, "the fleet hub")
    if wall:
        out.append({"ok": False, "text": wall if info else f"when this machine serves the hub: {wall}", "fix": ""})
    return out


def _joined() -> list:
    from .fleet.cli_join import _ping
    store = _core.module("peers.store")
    out = []
    for e in store.hubs():
        name = e.get("name") or e.get("url")
        got = _ping(e)
        if got.get("reachable"):
            out.append(f"joined {name} ({e.get('url')}): it answers and sees this harness "
                       f"{'online' if got.get('online') else 'offline (no halo session open here)'}")
        else:
            out.append({"ok": False, "text": f"joined {name} ({e.get('url')}): {got.get('error') or 'no answer'}",
                        "fix": "halo fleet status; a hub that removed this harness: halo fleet leave, then join again"})
    return out or ["this harness joined no hub (halo fleet join <host:port> --code ...)"]


def rows(ctx) -> list:
    return _serving(ctx) + _joined()
