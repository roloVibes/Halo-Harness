"""halo_harness.pool_scan_cli -- `halo pool scan` (Halo 3.3.8.0 R1; docs/COMMANDS-pool.md "halo pool scan").

    halo pool scan [--port N] [--subnet CIDR ...] [--no-own-subnet] [--json]

A TCP connect on the RPC port (pool.rpc_port, 50052) to every address of this machine's /24 and of each
`--subnet` / pool.scan_subnets CIDR (a /24 at most each), then to every member; each responder with its connect time
("0.4 ms", "12 ms -- Wi-Fi?"), the paired host at that address, and whether it is a member already. Only when you run
it: nothing in Halo scans on its own. A connect says a port is open and how far away the machine is; it does not say
the far end is rpc-server, nor the link's speed (the host card's link does). Exit codes: 0 done, 2 usage.
"""

from __future__ import annotations

import argparse

from halo_harness.remote import cli_common as C


def cmd_scan(argv: list) -> int:
    p = argparse.ArgumentParser(prog="halo pool scan", description="Probe the RPC port on the LAN and on every member.")
    p.add_argument("--port", type=int, default=None, help="the rpc-server port (default: pool.rpc_port, 50052)")
    p.add_argument("--subnet", action="append", default=None, metavar="CIDR",
                   help="a network to scan besides this machine's /24 (repeatable; default: pool.scan_subnets)")
    p.add_argument("--no-own-subnet", action="store_true", help="skip this machine's own /24")
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.local_pool.scan import scan
    got = scan(port=a.port, subnets=a.subnet, own_subnet=not a.no_own_subnet)
    if a.json:
        C.emit_json({"ok": True, **got})
        return 0
    print(got["line"])
    for c in got["candidates"]:
        who = ", ".join(x for x in ((f"member {c['member']}" if c.get("member") else ""),
                                    (f"paired host {c['paired']}" if c.get("paired") else ""),
                                    (c.get("name") or "")) if x)
        print(f"  {c['line']}" + (f" ({who})" if who else "") + ("" if c.get("member") else
                                                                 f" -- halo pool add <name> {c['host']}:{c['port']}"))
    for m in got["members"]:
        print(f"  member {m['name']}: {m['line']}")
    for n in got["notes"]:
        print(f"  note: {n}")
    return 0
