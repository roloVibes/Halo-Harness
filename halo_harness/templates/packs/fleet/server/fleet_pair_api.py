"""halo_harness.studio.fleet_pair_api -- the Fleet section's own routes (Halo
3.0.5.0 "Fleet" round R3), appended to studio/fleet_hub_api.py's ROUTES; the
same loopback + token guard as every Studio route.

    POST fleet/pair {ttl?}          a one-time pair code for this machine's hub (the Start view):
                                    {code, expires, ttl, url, fingerprint, hub_running, join, qr, matrix}
    GET  fleet/settings             {name, share, allow_control, levels, hubs: [...], members: [...], hub}
    POST fleet/settings {share?, allow_control?}   writes fleet.share / fleet.allow_control
    POST fleet/kick {harness}       removes a member from this hub (its pair key goes with it)
    GET  fleet/history?role=&bio=   past runs under a role or bio (studio/fleet_api.py `get_history`)

The code, the join line and the QR text are exactly `halo fleet pair`'s
(fleet/cli.py): the QR carries the hub's address and fingerprint, the six
words are typed on the other machine. `matrix` is the QR as rows of 0/1 so
the page draws it without a library. Settings live in the state directory's
config.json (the keys docs/FLEET.md lists); `hubs` are this harness's joined
hubs (`~/.halo/fleet.json`, never a key), `members` the harnesses paired to
this machine's hub (never a key).
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from halo_harness.ext import core as _core
get_history = _core.get("studio.fleet_api", "get_history")

HUB_FIELDS = ("url", "name", "hub_id", "fingerprint", "tls", "share", "allow_control", "member_name", "joined_at",
              "state")


def _hub(req):
    return getattr(req.server, "fleet_hub", None)


def _home(req) -> Path:
    hub = _hub(req)
    return Path(hub.home) if hub is not None else Path(req.state_dir)


def _address(req, home: Path):
    """`(url, fingerprint, running)` of the hub other harnesses join (`halo fleet pair`'s rule)."""
    from ..fleet import hub as H
    identity = _core.module("peers.identity")
    tls = _core.module("peers.tls")
    hub_dir = _core.get("peers.pairing", "hub_dir")
    hub = _hub(req)
    if hub is not None and hub.server is not None:
        return hub.url(), hub.fingerprint, True
    info = H.read_info(home)
    if info:
        return str(info.get("url")), info.get("fingerprint"), True
    cert = hub_dir(home) / tls.CERT
    fp = tls.fingerprint_pem(cert.read_text(encoding="ascii")) if cert.is_file() else None
    scheme = "https" if (fp or tls.available()) else "http"
    return f"{scheme}://{H.lan_address()}:{identity.hub_port(home)}", fp, False


def post_pair(req):
    CODE_TTL_S = _core.get("peers.pairing", "CODE_TTL_S")
    MAX_TTL_S = _core.get("peers.pairing", "MAX_TTL_S")
    HubPairing = _core.get("peers.pairing", "HubPairing")
    encode = _core.get("remote.qr", "encode")
    body = req.body if isinstance(req.body, dict) else {}
    try:
        ttl = float(body.get("ttl") or CODE_TTL_S)
    except (TypeError, ValueError):
        return 422, {"error": f"ttl is a number of seconds, got {body.get('ttl')!r}", "problems": []}
    home = _home(req)
    hub = _hub(req)
    pairing = hub.pairing if hub is not None else HubPairing(home)
    code, expires = pairing.new_code(ttl)
    url, fp, running = _address(req, home)
    join = f'halo fleet join {url} --code "{code}"'
    uri = "halo-fleet://join?v=1&url=" + quote(url, safe="") + (f"&fp={fp}" if fp else "")
    return 200, {"ok": True, "code": code, "expires": expires, "ttl": round(max(30.0, min(ttl, MAX_TTL_S))), "url": url,
                 "fingerprint": fp, "hub_running": running, "join": join, "qr": uri, "matrix": encode(uri)}


def _level(home: Path, key: str, allowed: tuple, default: str) -> str:
    identity = _core.module("peers.identity")
    value = str(identity.config_value(key, default, home) or "").strip().lower()
    return value if value in allowed else default


def get_settings(req):
    identity = _core.module("peers.identity")
    store = _core.module("peers.store")
    CONTROL_LEVELS = _core.get("peers.identity", "CONTROL_LEVELS")
    DEFAULT_CONTROL = _core.get("peers.identity", "DEFAULT_CONTROL")
    DEFAULT_SHARE = _core.get("peers.identity", "DEFAULT_SHARE")
    SHARE_LEVELS = _core.get("peers.identity", "SHARE_LEVELS")
    HubPairing, public = (_core.get("peers.pairing", n) for n in ("HubPairing", "public"))
    home, state = _home(req), Path(req.state_dir)
    hubs = [{k: h.get(k) for k in HUB_FIELDS} for h in store.hubs(state)]
    members = sorted((public(m) for m in HubPairing(home).members().values()), key=lambda m: str(m.get("name") or ""))
    hub = _hub(req)
    return 200, {"name": identity.fleet_name(state), "share": _level(state, "fleet.share", SHARE_LEVELS, DEFAULT_SHARE),
                 "allow_control": _level(state, "fleet.allow_control", CONTROL_LEVELS, DEFAULT_CONTROL),
                 "levels": {"share": list(SHARE_LEVELS), "allow_control": list(CONTROL_LEVELS)},
                 "hubs": hubs, "members": members,
                 "hub": {"serving": hub is not None and hub.server is not None,
                         "url": hub.url() if hub is not None and hub.server is not None else None}}


_set_config = _core.get("studio.fleet_panels_api", "_set_config")  # 3.4.0.0 C: core (the caps write it too)
def post_settings(req):
    identity = _core.module("peers.identity")
    CONTROL_LEVELS, SHARE_LEVELS = (_core.get("peers.identity", n) for n in ("CONTROL_LEVELS", "SHARE_LEVELS"))
    body = req.body if isinstance(req.body, dict) else {}
    wanted = {"share": ("fleet.share", SHARE_LEVELS), "allow_control": ("fleet.allow_control", CONTROL_LEVELS)}
    changes = {k: str(body[k]).strip().lower() for k in wanted if k in body}
    if not changes:
        return 422, {"error": "send share (status | events | full) or allow_control (none | ask | all)", "problems": []}
    bad = [f"{k} is one of {', '.join(wanted[k][1])}, got {v!r}" for k, v in changes.items() if v not in wanted[k][1]]
    if bad:
        return 422, {"error": bad[0], "problems": bad}
    try:
        for k, v in changes.items():
            _set_config(Path(req.state_dir), wanted[k][0], v)
    except Exception as e:  # a config.json that does not parse is never overwritten
        return 409, {"error": f"config.json was not changed: {e}"}
    identity.forget_cache()
    return get_settings(req)


def post_kick(req):
    HubPairing = _core.get("peers.pairing", "HubPairing")
    body = req.body if isinstance(req.body, dict) else {}
    hid = str(body.get("harness") or "").strip()
    if not hid:
        return 422, {"error": "name the member to kick: {harness: <id>}", "problems": []}
    hub = _hub(req)
    pairing = hub.pairing if hub is not None else HubPairing(_home(req))
    gone = pairing.remove(hid)
    if gone is None:
        return 404, {"error": f"no member {hid!r} on this hub"}
    if hub is not None:
        hub.state.reload()
    return 200, {"ok": True, "kicked": gone}


ROUTES = [("POST", r"^fleet/pair$", post_pair),
          ("GET", r"^fleet/settings$", get_settings),
          ("POST", r"^fleet/settings$", post_settings),
          ("POST", r"^fleet/kick$", post_kick),
          ("GET", r"^fleet/history$", get_history)]
