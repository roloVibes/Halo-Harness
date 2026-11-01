"""halo_harness.host_rpc_cli -- `halo host rpc on | off | status [--port N] [--mem MIB] [--json]` (Halo 3.3.8.0 R3;
docs/COMMANDS-host.md "halo host rpc"): the owner of a pool worker starts or stops llama.cpp's rpc-server on this
machine, the same op a paired controller asks for through the host (`halo pool rpc <member> on`; host/ops_rpc.py).

It binds the LAN address this machine's `halo host` serves on (its serve.json url when it runs, else the address of
the interface the default route uses), on `pool.rpc_port` (50052), with `--mem` from this machine's free VRAM (the
card's usable memory with the helper, minus the resident models and the claims). The owner needs no grant here.
Exit codes: 0 done, 1 could not (the reason on stderr), 2 usage.
"""

from __future__ import annotations

import argparse
import sys

from halo_harness.remote import cli_common as C


def _addr(home) -> str:
    """The address this machine's halo host serves on (its serve.json url), else its bind, else the LAN address of
    the default route's interface (127.0.0.1 under the test flag: a test never reads this machine's own address)."""
    from halo_harness.config.paths import background_net_disabled
    from halo_harness.fleet.hub import lan_address
    from halo_harness.host import state as S
    from halo_harness.ollama_steward.host_client import _addr_port
    lan = (lambda: "127.0.0.1") if background_net_disabled() else lan_address
    info = S.read_info(home) or {}
    if info.get("url"):
        return _addr_port(str(info["url"]), 7431)[0] or lan()
    b = S.bind(home)
    return lan() if b in ("0.0.0.0", "", "::") else b


def cmd_rpc(argv: list) -> int:
    p = argparse.ArgumentParser(prog="halo host rpc", description="Start, stop or show llama.cpp's rpc-server for a "
                                "pool on this machine (the LAN address this host serves on).")
    p.add_argument("to", choices=("on", "off", "status"))
    p.add_argument("--port", type=int, default=None, help="the RPC port (default: pool.rpc_port, 50052)")
    p.add_argument("--mem", type=int, default=None, help="--mem in MiB (default: this machine's free VRAM)")
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.fleet import identity
    from halo_harness.host import ops_rpc as R
    home = identity.home()
    if a.to == "status":
        got = {"ok": True, "rpc": R.status(home), "say": R.status(home)["line"]}
    elif a.to == "off":
        got = R.turn_off(home, by="owner")
    else:
        from halo_harness.host.routes_view import View
        addr = _addr(home)
        got = R.turn_on(home, addr=addr, card_rows=View(home).card().get("hosts") or [], port=a.port, mem_mib=a.mem)
        if got.get("ok") and not got.get("already"):
            got["notes"] = [R.lan_line(addr)]
    if a.json:
        C.emit_json(got)
        return 0 if got.get("ok") else 1
    print(got.get("say") or "", file=sys.stdout if got.get("ok") else sys.stderr)
    for n in got.get("notes") or []:
        print(f"  note: {n}")
    return 0 if got.get("ok") else 1
