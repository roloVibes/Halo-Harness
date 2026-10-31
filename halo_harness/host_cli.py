"""halo_harness.host_cli -- `halo host ...` (Halo 3.3.7.0 R1; docs/COMMANDS-host.md, docs/HOST.md).

    halo host [serve] [--port N] [--bind ADDR] [--foreground] [--no-tls] [--json]
    halo host status [--peer NAME] [--json]
    halo host stop [--json]
    halo host pair [--ttl 10m] [--ascii] [--json]                                (host_pair_cli.py)
    halo host join <host:port|url> --code "<six words>" [--fingerprint HEX] [--json]   (host_pair_cli.py)
    halo host install [--port N] [--bind ADDR] [--os OS] [--anyway] [--json]   (host_install.py)
    halo host uninstall [--os OS] [--json]                                       (host_install.py)

`serve` starts the host in the background (a detached `halo host serve --foreground`) and returns once its
serve.json is written; `--foreground` runs it here until Ctrl+C or `halo host stop`. Exit codes: 0 done, 1 could
not (the reason on stderr), 2 usage.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from halo_harness.fleet import identity
from halo_harness.remote import cli_common as C

VERBS = ("serve", "status", "stop", "pair", "join", "install", "uninstall")
SEAMS: dict = {}  # "spawn": fn(argv) -> a Popen-like (the tests' seam: no detached process in a test)
USAGE = """usage: halo host [serve] [--port N] [--bind ADDR] [--foreground] [--no-tls] [--json]
       halo host status [--peer NAME] [--json]
       halo host stop [--json]
       halo host pair [--ttl 10m] [--ascii] [--json]
       halo host join <host:port|url> --code "<six words>" [--fingerprint HEX] [--json]
       halo host install [--port N] [--bind ADDR] [--os linux|macos|windows] [--anyway] [--json]
       halo host uninstall [--os linux|macos|windows] [--json]

  serve      run halo host: the model-free monitor of this machine's model servers, serving paired peers
  status     is it running, since when, its port, peers, last request, what it watches (--peer: a paired host's)
  stop       stop the halo host this machine runs
  pair       a one-time six-word code that pairs one peer with this host (the view grant)
  join       pair this harness with a host (its code); fleet.json's hosts list keeps it
  install    write the service file (systemd user unit, launchd agent, Task Scheduler at logon); prints the enable line
  uninstall  remove the service file it wrote; prints the disable line"""


def _parser(verb: str, description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo host {verb}", description=description)
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    return p


def _when(t) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) if isinstance(t, (int, float)) else "?"


def cmd_serve(argv: list) -> int:
    from halo_harness.host import state as S
    p = _parser("serve", "Run halo host: no TUI, no session, no model; LAN only, every request signed and audited.")
    p.add_argument("--port", type=int, default=None, help="the LAN port (default: host.port, 7431; 0 picks a free one)")
    p.add_argument("--bind", default=None, help="the address to listen on (default: host.bind, 0.0.0.0)")
    p.add_argument("--foreground", action="store_true", help="run here until Ctrl+C or `halo host stop`")
    p.add_argument("--no-tls", action="store_true", help="HMAC-signed plain HTTP even when TLS is available")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.fleet.hub import FleetOffline
    from halo_harness.host.service import OFFLINE_LINE, HostService
    if identity.offline():
        return C.fail(a.json, "offline", f"halo host serve: {OFFLINE_LINE}")
    home = identity.home()
    if not S.enabled(home):
        return C.fail(a.json, "disabled", "halo host serve: host.enabled is false on this machine "
                                          "(`halo config set host.enabled true`)")
    info = S.read_info(home)
    if info:
        if a.json:
            C.emit_json({"ok": True, "already": True, **{k: info.get(k) for k in ("pid", "port", "url", "fingerprint")}})
        else:
            print(f"halo host already runs (pid {info.get('pid')}) at {info.get('url')} since {_when(info.get('started'))}.")
        return 0
    if not a.foreground:
        return _detach(a, home)
    try:
        svc = HostService(home, port=a.port, bind=a.bind, tls_on=False if a.no_tls else None).start()
    except FleetOffline as e:
        return C.fail(a.json, "offline", f"halo host serve: {e}")
    except (OSError, RuntimeError) as e:
        return C.fail(a.json, "not_started", f"halo host serve: cannot listen on {a.bind or S.bind(home)}:"
                                             f"{a.port if a.port is not None else S.port(home)}: {e}")
    if a.json:
        C.emit_json({"ok": True, **svc.public(), "watches": svc.watches()})
    else:
        from halo_harness.fleet import tls
        how = f"TLS, fingerprint {tls.short(svc.fingerprint)}" if svc.fingerprint else "HMAC-signed HTTP, no TLS"
        print(f"halo host {svc.name} at {svc.url()} ({how}); watching {', '.join(svc.watches()) or 'no local Ollama host'}.")
        print("`halo host pair` makes a code for a peer. Ctrl+C or `halo host stop` stops it.")
    sys.stdout.flush()
    try:
        while not svc.stopping.is_set():
            svc.stopping.wait(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        svc.stop()
    return 0


def _detach(a, home) -> int:
    from halo_harness.host import state as S
    argv = [sys.executable, "-u", "-m", "halo_harness", "host", "serve", "--foreground"]
    argv += (["--port", str(a.port)] if a.port is not None else []) + (["--bind", a.bind] if a.bind else [])
    argv += ["--no-tls"] if a.no_tls else []
    import subprocess
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        kwargs["start_new_session"] = True
    try:
        proc = (SEAMS["spawn"](argv) if "spawn" in SEAMS else subprocess.Popen(argv, **kwargs))
    except OSError as e:
        return C.fail(a.json, "not_started", f"halo host serve: could not start it: {e}")
    deadline = time.time() + 15.0
    while time.time() < deadline and S.read_info(home) is None:
        if proc.poll() is not None:
            return C.fail(a.json, "not_started", "halo host serve: it exited before it listened "
                                                 "(`halo host serve --foreground` shows why)")
        time.sleep(0.2)
    info = S.read_info(home)
    if info is None:
        return C.fail(a.json, "not_started", "halo host serve: it did not write serve.json within 15 s")
    if a.json:
        C.emit_json({"ok": True, **{k: info.get(k) for k in ("pid", "port", "url", "fingerprint", "watches")}})
    else:
        print(f"halo host runs in the background (pid {info.get('pid')}) at {info.get('url')}; `halo host stop` stops it.")
    return 0


def status_lines(home) -> "tuple[dict, list]":
    from halo_harness.host import state as S
    info = S.read_info(home)
    if not info:
        return {"running": False}, ["halo host: not running (`halo host serve` starts it; `halo host install` makes it "
                                    "a service)"]
    peers = S.HostPairing(home).members()
    au = S.audit_summary(home)
    last = au.get("last") or {}
    out = {"running": True, **info, "peers": len(peers), "requests": au["count"], "last_request": last or None}
    lines = [f"halo host: running since {_when(info.get('started'))} (pid {info.get('pid')}) at {info.get('url')}",
             f"  port {info.get('port')} on {info.get('bind')}, " + (f"TLS {info.get('fingerprint', '')[:16]}"
                                                                      if info.get("tls") else "HMAC-signed HTTP"),
             f"  peers paired: {len(peers)}" + (f" ({', '.join(sorted(str(r.get('name')) for r in peers.values()))})"
                                                 if peers else " (`halo host pair` makes a code)"),
             "  last request: " + (f"{_when(last.get('at'))} {last.get('peer') or '?'} {last.get('path')} "
                                   f"({'ok' if last.get('ok') else 'refused'})" if last else "none yet")
             + f"; {au['count']} in the audit",
             f"  watches: {', '.join(info.get('watches') or []) or 'no Ollama host served here'}"
             + ("; the steward's watch runs here" if info.get("steward_job") else
                "; the steward's watch runs in another process here (or ollama.steward.job is off)")]
    return out, lines


def cmd_status(argv: list) -> int:
    p = _parser("status", "Is halo host running here (or, with --peer, on a paired host), and what it sees.")
    p.add_argument("--peer", default=None, help="a paired host by name or url (halo host join)")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    if a.peer:
        from halo_harness.host_pair_cli import peer_status
        return peer_status(a.peer, a.json)
    out, lines = status_lines(identity.home())
    if a.json:
        C.emit_json({"ok": True, **out})
    else:
        print("\n".join(lines))
    return 0


def cmd_stop(argv: list) -> int:
    from halo_harness.host import state as S
    a, rc = C.parse(_parser("stop", "Stop the halo host this machine runs."), argv)
    if a is None:
        return rc
    home = identity.home()
    info = S.read_info(home)
    if not info:
        if a.json:
            C.emit_json({"ok": True, "was_running": False})
        else:
            print("halo host was not running.")
        return 0
    S.request_stop(home)
    deadline = time.time() + 10.0
    while time.time() < deadline and S.read_info(home) is not None:
        time.sleep(0.2)
    pid = info.get("pid")
    if S.read_info(home) is not None and isinstance(pid, int) and pid != os.getpid():
        import signal
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    if a.json:
        C.emit_json({"ok": True, "was_running": True, "pid": pid})
    else:
        print(f"halo host stopped (pid {pid}).")
    return 0


def cmd_host(argv: list) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    verb, rest = (argv[0], argv[1:]) if argv and not argv[0].startswith("-") else ("serve", list(argv))
    if verb in ("serve", "status", "stop"):
        return {"serve": cmd_serve, "status": cmd_status, "stop": cmd_stop}[verb](rest)
    if verb in ("pair", "join"):
        from halo_harness import host_pair_cli
        return getattr(host_pair_cli, "cmd_" + verb)(rest)
    if verb in ("install", "uninstall"):
        from halo_harness import host_install
        return getattr(host_install, "cmd_" + verb)(rest)
    print(USAGE, file=sys.stderr)
    return 2
