"""halo_harness.fleet.cli_members -- `halo fleet members | kick`: the hub
side of a fleet (Halo 3.0.5.0 "Fleet" round R2; 3.1.0.0 R2 cut it out of
cli_more.py; the dispatcher is cli.py). members and kick read and edit this
machine's hub files (pairing.py), which a running hub rereads within a
second.
"""

from __future__ import annotations

import time

from halo_harness.fleet import identity
from halo_harness.fleet.cli_join import _parser
from halo_harness.remote import cli_common as C


def cmd_members(argv: list) -> int:
    a, rc = C.parse(_parser("members", "The harnesses paired with this machine's hub."), argv)
    if a is None:
        return rc
    from halo_harness.fleet import hub as H
    from halo_harness.fleet.pairing import HubPairing, public
    view = H.running_view() or {}
    online = {h.get("id"): h.get("online") for h in view.get("harnesses") or [] if not h.get("local")}
    rows = [{**public(r), "online": bool(online.get(r.get("id")))} for r in HubPairing(identity.home()).members().values()]
    if a.json:
        C.emit_json({"ok": True, "members": rows, "hub_running": bool(view)})
        return 0
    if not rows:
        print("No members yet: `halo fleet pair` makes a code another harness joins with.")
        return 0
    print(f"{'NAME':<24} {'ID':<10} {'HOST':<16} {'VERSION':<10} {'SHARE':<7} {'CONTROL':<8} {'ONLINE':<7} PAIRED")
    for r in sorted(rows, key=lambda r: str(r.get("name")).lower()):
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(r.get("paired_at") or 0))
        print(f"{str(r.get('name'))[:24]:<24} {str(r.get('id'))[:8]:<10} {str(r.get('host') or '')[:16]:<16} "
              f"{str(r.get('version') or '')[:10]:<10} {str(r.get('share') or '-'):<7} {str(r.get('allow_control') or '-'):<8} "
              f"{'yes' if r['online'] else ('?' if not view else 'no'):<7} {when}")
    return 0


def cmd_kick(argv: list) -> int:
    p = _parser("kick", "Remove a member from this machine's hub; its pair key stops working.")
    p.add_argument("name", help="the member's name, or a prefix of its id")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.fleet.pairing import HubPairing
    pairing = HubPairing(identity.home())
    hits = pairing.find(a.name)
    if len(hits) != 1:
        why = f"no member named {a.name!r}" if not hits else f"{len(hits)} members match {a.name!r}; give an id prefix"
        return C.fail(a.json, "no_member" if not hits else "ambiguous", f"halo fleet kick: {why} (`halo fleet members`)")
    rec = pairing.remove(hits[0]["id"], kicked=True)
    if a.json:
        C.emit_json({"ok": True, "kicked": rec})
    else:
        print(f"Kicked {rec.get('name')} ({str(rec.get('id'))[:8]}): its pair key no longer works and a running hub "
              "closes its links within a second. It can join again only with a new code.")
    return 0
