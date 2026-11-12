"""halo_harness.fleet.cli_join -- `halo fleet join | leave | status`: this
harness's side of a fleet (Halo 3.0.5.0 "Fleet" round R2; 3.1.0.0 R2
renamed it from cli_more.py and moved members / kick to cli_members.py; the
dispatcher and serve / pair are in cli.py). join, leave and status talk to
hubs through fleet/relay.py.
"""

from __future__ import annotations

import argparse

from halo_harness.ext import core as _core
identity = _core.module("peers.identity")
store = _core.module("peers.store")
CONTROL_LEVELS, SHARE_LEVELS = (_core.get("peers.identity", n) for n in ("CONTROL_LEVELS", "SHARE_LEVELS"))
C = _core.module("remote.cli_common")


def _parser(verb: str, description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo fleet {verb}", description=description)
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    return p


def cmd_join(argv: list) -> int:
    p = _parser("join", "Join a fleet hub with the six-word code `halo fleet pair` printed on it.")
    p.add_argument("hub", help="the hub: host:port or http(s)://host:port")
    p.add_argument("--code", required=True, help='the six words, quoted ("acorn badge ...")')
    p.add_argument("--share", choices=SHARE_LEVELS, default=None,
                   help="what this harness sends that hub (default: fleet.share, events)")
    p.add_argument("--allow-control", choices=CONTROL_LEVELS, default=None,
                   help="what that hub may do here (default: fleet.allow_control, ask)")
    p.add_argument("--fingerprint", default=None, help="the hub's certificate fingerprint to insist on (hex)")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    HubError, join = (_core.get("peers.relay", n) for n in ("HubError", "join"))
    me = identity.harness()
    try:
        got = join(a.hub, a.code, me, share=a.share, allow_control=a.allow_control,
                   fingerprint=(a.fingerprint or "").replace(":", "") or None)
    except ValueError as e:
        return C.fail(a.json, "usage", f"halo fleet join: {e}")
    except HubError as e:
        return C.fail(a.json, "refused" if e.status else "unreachable", f"halo fleet join: {e}")
    key = got.pop("key")
    entry = store.add_hub({**got, "share": a.share, "allow_control": a.allow_control}, key)
    share, control = identity.share(entry), identity.allow_control(entry)
    if a.json:
        C.emit_json({"ok": True, "hub": {k: v for k, v in entry.items() if k != "key_ref"}, "share": share,
                     "allow_control": control})
        return 0
    __version__ = _core.version()
    print(f"Joined {entry.get('name')} at {entry['url']} as {entry.get('member_name') or me['name']}.")
    print(f"This harness shares `{share}` with it and control from it is `{control}`"
          f"{' (the owner answers a card for each command)' if control == 'ask' else ''}.")
    print("Sessions running now show on the hub within a few seconds; `halo fleet leave` undoes this.")
    print("This machine is online on the hub while a halo session runs here (a terminal, `halo -p`, a headless session; "
          "Studio alone does not count): with none open it is away and takes no mission part.")  # 3.4.0.1 (defect 14)
    if got.get("hub_version") and got["hub_version"] != __version__:
        print(f"The hub runs Halo {got['hub_version']}, this harness {__version__} (`halo update` on the older one).")
    return 0


def _link(entry: dict):
    HubLink = _core.get("peers.relay", "HubLink")
    key = store.key_for(entry)
    return HubLink(entry, key, identity.harness()["id"], timeout=3.0) if key else None


def cmd_leave(argv: list) -> int:
    p = _parser("leave", "Leave one fleet hub (by name, url or id), or every hub when none is named.")
    p.add_argument("hub", nargs="?", default=None, help="the hub to leave (default: every hub)")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    entries = store.find(a.hub)
    if not entries:
        return C.fail(a.json, "not_joined", "halo fleet leave: " + (f"no joined hub matches {a.hub!r}" if a.hub
                                                                     else "this harness has joined no hub"))
    protocol = _core.module("peers.protocol")
    HubError = _core.get("peers.relay", "HubError")
    told = {}
    for e in entries:
        if e.get("state") == "kicked":  # 3.4.0.1 (defect 27): the hub said so already
            told[e["url"]] = "gone"
            continue
        link = _link(e) if e.get("state", "joined") == "joined" and not identity.offline() else None
        try:
            told[e["url"]] = bool(link and link.request("POST", protocol.PREFIX + "/leave", protocol.doc()))
        except HubError as err:  # 3.4.0.1 (defect 27): a refusal is an answer: it had removed this harness already
            told[e["url"]] = "gone" if err.kicked or err.status in (401, 403, 404) else False
    gone = store.remove(entries)
    if a.json:
        C.emit_json({"ok": True, "left": [{"url": g["url"], "name": g.get("name"), "told": told.get(g["url"]) is True,
                                           "already_removed": told.get(g["url"]) == "gone"}
                                          for g in gone]})
        return 0
    for g in gone:
        note = (" (it had already removed this harness)" if told.get(g["url"]) == "gone" else "" if told.get(g["url"])
                else " (the hub did not answer; it lists this harness until it comes back or kicks it)")
        print(f"Left {g.get('name') or g['url']}{note}.")
    return 0


def _ping(entry: dict) -> dict:
    protocol = _core.module("peers.protocol")
    HubError = _core.get("peers.relay", "HubError")
    if entry.get("state", "joined") != "joined":
        return {"reachable": False, "error": entry.get("state")}
    if identity.offline():
        return {"reachable": False, "error": "offline mode is on"}
    link = _link(entry)
    if link is None:
        return {"reachable": False, "error": "no pair key (join again)"}
    try:
        got = link.request("GET", protocol.PREFIX + "/ping")
    except HubError as e:
        return {"reachable": False, "error": str(e), "kicked": e.kicked}
    finally:
        link.close()
    you = {k: v for k, v in (got.get("you") or {}).items() if k not in ("name", "id")}  # 3.4.0.1 (defect 11): this
    return {"reachable": True, "hub_version": (got.get("hub") or {}).get("version"), **you}  # harness as the hub sees it


def cmd_status(argv: list) -> int:
    a, rc = C.parse(_parser("status", "This harness's hubs (does each answer, does it see us) and the hub it serves."), argv)
    if a is None:
        return rc
    from . import hub as H
    hubs = [{**{k: v for k, v in e.items() if k != "key_ref"}, "share": identity.share(e),
             "allow_control": identity.allow_control(e), **_ping(e)} for e in store.hubs()]
    info, view = H.read_info(), None
    if info:
        view = H.running_view(timeout=10.0)  # a loaded machine answers its own hub late; 3 s dropped the members count
    serving = {"url": info.get("url"), "name": info.get("name"), "tls": info.get("tls"),
               **((view or {}).get("hub") or {}), "firewall": _wall(info)} if info else None
    out = {"harness": identity.harness(), "offline": identity.offline(), "allow_answers": identity.allow_answers(),
           "hubs": hubs, "serving": serving}
    if a.json:
        C.emit_json({"ok": True, **out})
        return 0
    h = out["harness"]
    print(f"This harness: {h['name']} ({h['id'][:8]}), Halo {h['version']}" + ("  [offline: the relay is off]" if out["offline"] else ""))
    if not hubs:
        print("Joined hubs: none (`halo fleet join <host:port> --code ...`).")
    for r in hubs:
        seen = (f"answers, sees this harness {'online' if r.get('online') else 'offline'} with {r.get('sessions', 0)} session(s)"
                if r.get("reachable") else f"not reachable: {r.get('error')}")
        print(f"  {r.get('name') or '?'}  {r['url']}  share {r['share']}  control {r['allow_control']}  {seen}")
    if serving:
        print(f"Serving: hub {serving.get('name')} at {serving.get('url')}: {serving.get('members', '?')} member(s), "
              f"{serving.get('online', '?')} online{', a pairing code is open' if serving.get('pair_code_active') else ''}.")
        if serving.get("firewall"):
            print(serving["firewall"])
    return 0


def _wall(info: dict) -> str:
    """3.4.1.0 R5 (defect 12): the hub this machine serves says the firewall line here too (read-only, peers/firewall.py)."""
    bind = str(info.get("bind") or "")
    if not info.get("port") or bind.startswith("127.") or bind == "localhost":
        return ""
    try:
        return _core.get("peers.firewall", "line")(int(info["port"]), "the fleet hub")
    except Exception:
        return ""
