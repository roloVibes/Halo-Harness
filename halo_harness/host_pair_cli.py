"""halo_harness.host_pair_cli -- `halo host pair | join` and `halo host status --peer` (Halo 3.3.7.0 R1;
docs/COMMANDS-host.md). The host is the code issuer: `pair` on the host prints six words, `join` on the peer spends
them (host/join.py, the hub's exchange) and keeps the host in fleet.json's `hosts` list.
"""

from __future__ import annotations

import time
from urllib.parse import quote

from halo_harness.fleet import identity
from halo_harness.remote import cli_common as C


def _parser(verb: str, description: str):
    import argparse
    p = argparse.ArgumentParser(prog=f"halo host {verb}", description=description)
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    return p


def host_url(home) -> "tuple[str, str | None, bool]":
    """(the url peers reach this host at, its fingerprint, running)."""
    from halo_harness.fleet import tls
    from halo_harness.fleet.hub import lan_address
    from halo_harness.host import state as S
    info = S.read_info(home)
    if info:
        return str(info.get("url")), info.get("fingerprint"), True
    cert = S.host_dir(home) / tls.CERT
    fp = tls.fingerprint_pem(cert.read_text(encoding="ascii")) if cert.is_file() else None
    return f"{'https' if (fp or tls.available()) else 'http'}://{lan_address()}:{S.port(home)}", fp, False


def cmd_pair(argv: list) -> int:
    p = _parser("pair", "Make a one-time six-word code that pairs one peer with this host (the view grant).")
    p.add_argument("--ttl", default="10m", help="how long the code works (default 10m; 90s, 1h ...)")
    p.add_argument("--ascii", action="store_true", help="draw the QR code with # instead of block glyphs")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.fleet.cli import parse_ttl
    from halo_harness.fleet import tls
    from halo_harness.host.state import HostPairing
    try:
        ttl = parse_ttl(a.ttl)
    except ValueError as e:
        return C.fail(a.json, "usage", f"halo host pair: {e}")
    home = identity.home()
    code, expires = HostPairing(home).new_code(ttl)
    url, fp, running = host_url(home)
    join = f'halo host join {url} --code "{code}"'
    uri = "halo-host://join?v=1&url=" + quote(url, safe="") + (f"&fp={fp}" if fp else "")
    if a.json:
        C.emit_json({"ok": True, "code": code, "expires": expires, "url": url, "fingerprint": fp, "host_running": running,
                     "join": join, "qr": uri, "grants": ["view"]})
        return 0
    print(f"Pairing code (one peer, {int(ttl // 60) or 1} min, the view grant):\n\n    {code}\n")
    print(f"On the other machine:\n\n    {join}\n")
    C.print_qr(uri, ascii_only=a.ascii)
    print(f"host {url}   " + (f"fingerprint {tls.short(fp)}" if fp else "(its certificate is made on the first serve)"))
    if not running:
        print("halo host is not running here yet: `halo host serve` (or `halo host install`).")
    return 0


def cmd_join(argv: list) -> int:
    p = _parser("join", "Pair this harness with a halo host, with the six-word code `halo host pair` printed there.")
    p.add_argument("host", help="the host: host:port (default port 7431) or http(s)://host:port")
    p.add_argument("--code", required=True, help='the six words, quoted ("acorn badge ...")')
    p.add_argument("--fingerprint", default=None, help="the host's certificate fingerprint to insist on (hex)")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.fleet import store
    from halo_harness.fleet.relay import HubError
    from halo_harness.host.join import join
    try:
        got = join(a.host, a.code, identity.harness(), fingerprint=(a.fingerprint or "").replace(":", "") or None)
    except ValueError as e:
        return C.fail(a.json, "usage", f"halo host join: {e}")
    except HubError as e:
        return C.fail(a.json, "refused" if e.status else "unreachable", f"halo host join: {e}")
    key = got.pop("key")
    entry = store.add_host(got, key)
    serves = ", ".join(f"{r.get('name')} ({r.get('addr')}:{r.get('port')})" for r in entry.get("serves") or [])
    if a.json:
        C.emit_json({"ok": True, "host": {k: v for k, v in entry.items() if k != "key_ref"}})
        return 0
    print(f"Paired with halo host {entry.get('name')} at {entry['url']} (grants: {', '.join(entry.get('grants') or [])}).")
    print(f"It serves {serves or 'no Ollama host yet'}; an ollama.hosts entry at that address now reads through it "
          "(`halo local hosts` shows the rung).")
    return 0


def peer_status(name: str, as_json: bool) -> int:
    from halo_harness.fleet import store
    from halo_harness.ollama_steward.host_client import HostClient, HostError
    rows = store.find_host(name)
    if not rows:
        return C.fail(as_json, "not_paired", f"halo host status: no paired host matches {name!r} (`halo host join`)")
    e = rows[0]
    key = store.key_for(e)
    if key is None:
        return C.fail(as_json, "no_key", f"halo host status: the pair key for {e.get('name')} is missing; join it again")
    c = HostClient(e, key, identity.harness()["id"])
    try:
        got = c.card(fresh=True)
    except HostError as ex:
        return C.fail(as_json, "unreachable", f"halo host status: {e.get('name')} at {e['url']}: {ex}")
    h, au = got.get("host") or {}, got.get("audit") or {}
    if as_json:
        C.emit_json({"ok": True, "host": h, "audit": au, "hosts": [{k: r.get(k) for k in ("name", "port", "footprint",
                                                                                        "log")} for r in got.get("hosts") or []]})
        return 0
    started = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(h["started"])) if h.get("started") else "?"
    print(f"halo host {h.get('name')} at {e['url']}: running since {started}, Halo {h.get('version')}, "
          f"{au.get('count', 0)} requests in its audit")
    for r in got.get("hosts") or []:
        print(f"  {r.get('name')} (port {r.get('port')}): {r.get('footprint')}; log: {(r.get('log') or {}).get('line')}")
    return 0
