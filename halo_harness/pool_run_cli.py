"""halo_harness.pool_run_cli -- the pool's running verbs (Halo 3.3.8.0 R3; docs/COMMANDS-pool.md).

    halo pool preflight <model> [--window N] [--allow-wifi] [--json]   every check before a launch (local_pool/preflight)
    halo pool rpc <member> on | off | status [--json]                  a worker's rpc-server through its halo host
    halo pool status [--json]                                          the running pool: health, degraded, claims
    halo pool stop [--json]                                            stop it (a change: changes_pool.stop)
    halo local serve --pool <model> [--window N] [--allow-wifi] [--keep] [--json]   serve_pool: warm it

`serve --pool` holds the pool in the foreground (its claims renewed by this process; Ctrl+C stops it, releases the
claims and says how the models it pivoted out come back); `--keep` returns once it serves -- the pool outlives the
command and a Studio on this home renews its claims while it runs, else they end with their lease. Exit codes: 0 done,
1 could not (the line says why), 2 usage.
"""

from __future__ import annotations

import argparse
import sys
import time

from halo_harness.remote import cli_common as C

SEAMS: dict = {}  # "hold": fn() -> None (the tests' stand-in for waiting on Ctrl+C)


def _print(got: dict, as_json: bool, ok_key: str = "ok") -> int:
    if as_json:
        C.emit_json(got)
    else:
        for line in got.get("lines") or [got.get("line") or got.get("say") or ""]:
            print(line, file=sys.stdout if got.get(ok_key) else sys.stderr)
    return 0 if got.get(ok_key) else 1


def _hold() -> None:
    if "hold" in SEAMS:
        return SEAMS["hold"]()
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        return None


def serve_pool(model: str, *, window=None, keep: bool = False, allow_wifi=None, as_json: bool = False) -> int:
    from halo_harness.ollama_steward import changes_pool
    got = changes_pool.warm(model, allow_wifi=allow_wifi, window=window, keep=keep, by="user")
    view = {k: v for k, v in got.items() if k != "preflight"}
    if not got.get("ok") or keep:
        if got.get("ok"):
            view["lines"] = list(got["lines"]) + ["--keep: the pool outlives this command; a Studio on this home renews "
                                                  "its claims while it runs, else they end with their lease "
                                                  "(pool.claim_lease_s)"]
        return _print(view, as_json)
    if not as_json:
        for line in got["lines"]:
            print(line)
        print("the pool runs while this command does: Ctrl+C stops it and releases the claims")
    _hold()
    done = changes_pool.stop(by="user", why="halo local serve --pool ended")
    if as_json:
        C.emit_json({**view, "stopped": done})
    else:
        for line in done["lines"]:
            print(line)
    return 0


def cmd_preflight(argv: list) -> int:
    p = argparse.ArgumentParser(prog="halo pool preflight", description="Every check before the pool launches a model.")
    p.add_argument("model", help="a pool catalog model")
    p.add_argument("--window", type=int, default=None, help="the window to check (default: the fit's F16 window)")
    p.add_argument("--allow-wifi", action="store_true", help="keep a Wi-Fi member")
    p.add_argument("--json", action="store_true")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.local_pool.catalog import names
    from halo_harness.local_pool.preflight import preflight
    pf = preflight(a.model, allow_wifi=a.allow_wifi or None, window=a.window)
    if pf is None:
        return C.fail(a.json, "unknown_model", f"halo pool preflight: {a.model!r} is not in the pool catalog "
                                               f"({', '.join(names())})")
    if a.json:
        C.emit_json({k: v for k, v in pf.items() if k != "rows"})
        return 0 if pf["ok"] else 1
    print(pf["line"])
    for c in pf["checks"]:
        print(f"  {c['check']:<9} {'ok' if c['ok'] else 'BLOCKS'}")
        for line in c["lines"]:
            print(f"            {line}")
    return 0 if pf["ok"] else 1


def cmd_rpc(argv: list) -> int:
    p = argparse.ArgumentParser(prog="halo pool rpc", description="A member's rpc-server, through its halo host.")
    p.add_argument("member", help="a pool member's name")
    p.add_argument("to", choices=("on", "off", "status"))
    p.add_argument("--json", action="store_true")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.local_pool.hosts import rpc
    from halo_harness.local_pool.members import load
    m = next((x for x in load() if x["name"].lower() == a.member.lower()), None)
    if m is None:
        return C.fail(a.json, "unknown_member", f"halo pool rpc: no member named {a.member!r} "
                                                f"({', '.join(x['name'] for x in load()) or 'none yet'})")
    return _print(rpc(m, a.to), a.json)


def cmd_status(argv: list) -> int:
    p = argparse.ArgumentParser(prog="halo pool status", description="The running pool: its health and its claims.")
    p.add_argument("--json", action="store_true")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.local_pool.degrade import status
    got = status()
    return _print({**got, "ok": True}, a.json)


def cmd_stop(argv: list) -> int:
    p = argparse.ArgumentParser(prog="halo pool stop", description="Stop the pool (a change under the steward contract).")
    p.add_argument("--json", action="store_true")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.ollama_steward import changes_pool
    return _print(changes_pool.stop(by="user", why="halo pool stop"), a.json)


VERBS = {"preflight": cmd_preflight, "rpc": cmd_rpc, "status": cmd_status, "stop": cmd_stop}
