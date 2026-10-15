"""halo_harness.fleet.cli -- `halo fleet ...` (Halo 3.0.5.0 "Fleet" round R2).

    halo fleet [--once] [--json]                    the live table (table.py)
    halo fleet serve [--port N] [--bind ADDR] [--name NAME] [--no-tls] [--json]
    halo fleet pair [--ttl 10m] [--ascii] [--json]
    halo fleet join <host:port|url> --code "<six words>" [--share L] [--allow-control L] [--fingerprint HEX] [--json]
    halo fleet leave [hub] [--json]
    halo fleet status [--json]
    halo fleet members [--json]
    halo fleet kick <name> [--json]
    halo fleet record <sid> [--agent <aid>] [--out PATH] [--json]
    halo fleet digest [--since 2h|45m|1d|<unix seconds>|<ISO time>] [--json]
    halo fleet capabilities [name] [--refresh] [--tools] [--json]
    halo fleet who "<query>" [--json]

`serve` starts the hub inside a running Studio (through its loopback API)
or else in the foreground (Ctrl+C stops it); `pair` makes a one-time code
for the hub this machine runs. join / leave / status / members / kick live
in cli_more.py; record / digest (3.0.5.0 R4) in cli_panels.py; capabilities / who (3.0.6.0 R6) in cli_caps.py. Exit codes: 0 done, 1 could not (the reason on stderr), 2 usage.
"""

from __future__ import annotations

import re
import sys
import time
from urllib.parse import quote

from halo_harness.fleet import identity
from halo_harness.remote import cli_common as C

VERBS = ("serve", "pair", "join", "leave", "status", "members", "kick", "record", "digest", "capabilities", "who")
PANEL_VERBS = ("record", "digest")  # 3.0.5.0 R4: fleet/cli_panels.py
CAPS_VERBS = ("capabilities", "who")  # 3.0.6.0 R6: fleet/cli_caps.py
USAGE = """usage: halo fleet [--once] [--json]
       halo fleet serve [--port N] [--bind ADDR] [--name NAME] [--no-tls] [--json]
       halo fleet pair [--ttl 10m] [--ascii] [--json]
       halo fleet join <host:port|url> --code "<six words>" [--share status|events|full]
                       [--allow-control none|ask|all] [--fingerprint HEX] [--json]
       halo fleet leave [hub] [--json]
       halo fleet status [--json]
       halo fleet members [--json]
       halo fleet kick <name> [--json]
       halo fleet record <sid> [--agent <aid>] [--out PATH] [--json]
       halo fleet digest [--since 2h|45m|1d|<unix seconds>|<ISO time>] [--json]
       halo fleet capabilities [name] [--refresh] [--tools] [--json]
       halo fleet who "<query>" [--json]

  (none)    the live table of every harness, session and agent (s steer, k stop, p pause/resume, q quit)
  serve     run the hub other harnesses join (inside Studio when it runs, else here until Ctrl+C)
  pair      a one-time six-word code (and QR) that admits one harness to this machine's hub
  join      join a hub with its code; this harness's sessions then show on it
  leave     leave one hub (or every hub)
  status    this harness's hubs, whether each answers, and the hub this machine serves
  members   the harnesses paired with this machine's hub
  kick      remove a member from this machine's hub (its key stops working)
  record    a session (or one agent) as a self-contained HTML flight recording (~/.halo/recordings)
  digest    what happened since then, per harness: sessions, cost, decisions, files, errors, hand-offs
  capabilities  what each harness can do: hardware, models, craft apps, MCP servers and tools, skills, tags
  who       which harness can do something, ranked: who has gridcraft, a 4090, nmap ..."""


def parse_ttl(text: str) -> float:
    m = re.fullmatch(r"\s*(\d+)\s*([smh]?)\s*", str(text or ""))
    if not m:
        raise ValueError(f"a ttl is a number with s, m or h (10m, 90s, 1h), got {text!r}")
    return float(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600}[m.group(2)]


def cmd_serve(argv: list) -> int:
    p = C.make_parser("serve", "Run the fleet hub: other harnesses join it with `halo fleet join`.")
    p.prog = "halo fleet serve"
    p.add_argument("--port", type=int, default=None, help="the LAN port (default: fleet.hub.port, 7430)")
    p.add_argument("--bind", default="0.0.0.0", help="the address to listen on (default 0.0.0.0, every interface)")
    p.add_argument("--name", default=None, help="the hub's name (default: fleet.name)")
    p.add_argument("--no-tls", action="store_true", help="HMAC-signed plain HTTP even when TLS is available")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    if identity.offline():
        return C.fail(a.json, "offline", "halo fleet serve: offline mode is on (--offline or network.offline); the "
                                         "hub listens on the LAN, so it does not start.")
    home = identity.home()
    from halo_harness.studio.launch import api_call
    asked = api_call(home, "POST", "fleet/hub", {"action": "start", "port": a.port, "bind": a.bind, "name": a.name,
                                                 "tls": False if a.no_tls else None})
    if asked is not None:
        status, body = asked
        if status != 200:
            return C.fail(a.json, "not_started", f"halo fleet serve: {body.get('error') or status}")
        if a.json:
            C.emit_json({**body, "in_studio": True})
        else:
            print(f"The fleet hub {'already runs' if body.get('already') else 'runs'} inside Studio at {body.get('url')}.")
            print("`halo fleet pair` makes a code for another harness; it stops with Studio.")
        return 0
    from halo_harness.fleet import tls
    from halo_harness.fleet.hub import FleetOffline, HubServer
    try:
        hub = HubServer(home, port=a.port, bind=a.bind, name=a.name, tls_on=False if a.no_tls else None).start()
    except FleetOffline as e:
        return C.fail(a.json, "offline", f"halo fleet serve: {e}")
    except (OSError, RuntimeError) as e:
        return C.fail(a.json, "not_started", f"halo fleet serve: cannot listen on {a.bind}:{a.port or identity.hub_port()}: {e}")
    if a.json:
        C.emit_json({"ok": True, "in_studio": False, "url": hub.url(), "port": hub.port, "bind": hub.bind,
                     "tls": bool(hub.fingerprint), "fingerprint": hub.fingerprint, "name": hub.name})
    else:
        how = f"TLS, fingerprint {tls.short(hub.fingerprint)}" if hub.fingerprint else "HMAC-signed HTTP, no TLS"
        print(f"Fleet hub {hub.name} at {hub.url()} ({how}).")
        print("`halo fleet pair` makes a code for another harness. Ctrl+C stops the hub.")
    sys.stdout.flush()
    try:
        while not hub.stopping.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        if not a.json:
            print("\nfleet hub stopped")
    finally:
        hub.stop()
    return 0


def cmd_pair(argv: list) -> int:
    p = C.make_parser("pair", "Make a one-time pairing code that admits one harness to this machine's hub.")
    p.prog = "halo fleet pair"
    p.add_argument("--ttl", default="10m", help="how long the code works (default 10m; 90s, 1h ...)")
    p.add_argument("--ascii", action="store_true", help="draw the QR code with # instead of block glyphs")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    try:
        ttl = parse_ttl(a.ttl)
    except ValueError as e:
        return C.fail(a.json, "usage", f"halo fleet pair: {e}")
    from halo_harness.fleet import hub as H, tls
    from halo_harness.fleet.pairing import HubPairing, hub_dir
    home = identity.home()
    code, expires = HubPairing(home).new_code(ttl)
    info = H.read_info(home)
    if info:
        url, fp = str(info.get("url")), info.get("fingerprint")
    else:
        cert = hub_dir(home) / tls.CERT
        fp = tls.fingerprint_pem(cert.read_text(encoding="ascii")) if cert.is_file() else None
        url = f"{'https' if (fp or tls.available()) else 'http'}://{H.lan_address()}:{identity.hub_port(home)}"
    join = f'halo fleet join {url} --code "{code}"'
    uri = "halo-fleet://join?v=1&url=" + quote(url, safe="") + (f"&fp={fp}" if fp else "")
    if a.json:
        C.emit_json({"ok": True, "code": code, "expires": expires, "url": url, "fingerprint": fp,
                     "hub_running": bool(info), "join": join, "qr": uri})
        return 0
    print(f"Pairing code (one harness, {int(ttl // 60) or 1} min):\n\n    {code}\n")
    print(f"On the other machine:\n\n    {join}\n")
    C.print_qr(uri, ascii_only=a.ascii)
    if fp:
        print(f"hub {url}   fingerprint {tls.short(fp)}")
    else:
        print(f"hub {url}   " + ("(TLS: its certificate is made on the first `halo fleet serve`)"
                                 if url.startswith("https") else "(HMAC-signed HTTP, no TLS)"))
    if not info:
        print("No hub is running on this machine yet: start one with `halo fleet serve` (or `halo studio --fleet`).")
    return 0


def cmd_fleet(argv: list) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    if not argv or argv[0].startswith("-"):
        from halo_harness.fleet.table import cmd_table
        return cmd_table(argv)
    verb, rest = argv[0], argv[1:]
    if verb == "serve":
        return cmd_serve(rest)
    if verb == "pair":
        return cmd_pair(rest)
    if verb in CAPS_VERBS:
        from halo_harness.fleet import cli_caps
        return getattr(cli_caps, "cmd_" + verb)(rest)
    if verb in PANEL_VERBS:
        from halo_harness.fleet import cli_panels
        return getattr(cli_panels, "cmd_" + verb)(rest)
    if verb in VERBS:
        from halo_harness.fleet import cli_more
        return getattr(cli_more, "cmd_" + verb)(rest)
    print(USAGE, file=sys.stderr)
    return 2
