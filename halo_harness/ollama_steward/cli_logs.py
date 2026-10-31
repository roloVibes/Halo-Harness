"""halo_harness.ollama_steward.cli_logs -- the server log's commands (Halo 3.3.4.0 R2, 3.3.6.0 R2-R3).

- `halo ollama log [--host H] [-n N] [--kind fit|headroom|truncation|failure|all] [--follow]` (3.3.6.0 R3): the
  bounded raw tail of a host's server log -- this machine's rotation set, journald on a Linux with no file, or that
  machine's over its `ssh:` entry -- each line marked with its group; `--follow` reads again every FOLLOW_S until
  Ctrl-C. First the log status line (log_status.py).
- `halo ollama events [--host H] [--since] [--kind K] [--watch] [--from-start] [--json]` (3.3.4.0 R2; 3.3.6.0 R3:
  `--host` reads that host's log, over ssh for a host served elsewhere, and lists only its events).
- `halo ollama crashes [--host H] [--why] [--json]` (3.3.6.0 R2; R3: `--why` prints each fingerprint's evidence: the
  load it died in, the settings in force, the request's window, the load command, and the fixes when it repeats).
"""

from __future__ import annotations

import argparse
import json
import sys
import time

FOLLOW_S = 2.0
SEAMS: dict = {}  # "rounds": how many --follow reads before it stops (the tests' seam), "sleep": fn(s)


def _state_dir():
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def _host(name: str, prog: str):
    from halo_harness.fleet.ollama_share import served_here
    from halo_harness.providers.ollama import resolve_ollama_hosts
    hosts = resolve_ollama_hosts()
    named = [h for h in hosts if not name or h.name.lower() == name.lower()]
    if name and not named:
        print(f"{prog}: no configured host named {name!r} (see `ollama.hosts` in ~/.halo/config.json)", file=sys.stderr)
        return None, False
    return next((h for h in named if served_here(h.url)), named[0] if named else None), True


def _show(lines: list, kind: str) -> None:
    from halo_harness.ollama_steward.log_status import group_of
    for line in lines:
        g = group_of(line)
        if kind in ("", "all") or g == kind:
            print(f"[{g or '-':<10}] {line}")


def cmd_ollama_log(argv: list) -> int:
    from halo_harness.ollama_steward.log_status import status
    from halo_harness.ollama_steward.log_tail import local_tail, remote_tail, tail_lines
    parser = argparse.ArgumentParser(
        prog="halo ollama log", add_help=True,
        description="The newest lines of a host's Ollama server log, read-only: this machine's server.log and its "
                    "rotated files, journald on a Linux service, or that machine's log over its ssh: entry. Each line "
                    "is marked fit, headroom, truncation or failure.")
    parser.add_argument("--host", default=None, help="the configured host (default: the one this machine serves)")
    parser.add_argument("-n", type=int, default=200, help="how many lines (default 200)")
    parser.add_argument("--kind", default="all", choices=("fit", "headroom", "truncation", "failure", "all"),
                        help="only the lines of one group")
    parser.add_argument("--follow", action="store_true", help=f"read again every {FOLLOW_S:g} s (Ctrl+C stops)")
    args = parser.parse_args(argv)
    host, ok = _host(args.host, "halo ollama log")
    if not ok:
        return 1
    if host is None:
        print("No Ollama hosts configured.", file=sys.stderr)
        return 0
    n = max(1, min(int(args.n), 5000))
    print(f"log of '{host.name}': {status(_state_dir(), host)['line']}")
    lines, source, why = tail_lines(host, n)
    if why:
        print(f"no log lines: {why}")
        return 1
    print(f"# {source} (the newest {len(lines)} lines)")
    _show(lines, args.kind)
    rounds, sleep = SEAMS.get("rounds"), SEAMS.get("sleep") or time.sleep
    last = lines[-1] if lines else None
    try:
        while args.follow and (rounds is None or rounds > 0):
            rounds = None if rounds is None else rounds - 1
            sleep(FOLLOW_S)
            fresh = (local_tail(source, n) if source and not source.startswith(("ssh ", "journalctl", "via host")) else
                     remote_tail(host, n)[0] if source.startswith("ssh ") else tail_lines(host, n)[0])
            new = fresh[fresh.index(last) + 1:] if last in fresh else fresh
            _show(new, args.kind)
            last = fresh[-1] if fresh else last
    except KeyboardInterrupt:
        pass
    return 0


def cmd_ollama_events(argv: list) -> int:
    """`halo ollama events [--host H] [--since 24h] [--kind K] [--watch] [--from-start] [--json]`."""
    from halo_harness.ollama_steward import server_log
    from halo_harness.ollama_steward.server_events import format_event, read_events
    parser = argparse.ArgumentParser(
        prog="halo ollama events", add_help=True,
        description="An Ollama server's own words as events (trims, cut replies, 500s, a client that gave up, a CPU "
                    "spill, loads and their result ...), newest last. The server log is read read-only (over ssh for "
                    "a host with an ssh: entry); nothing is sent to the server but /api/version and /api/ps.")
    parser.add_argument("--host", default=None, help="the host whose server log this is (default: the local one); "
                        "only its events are listed")
    parser.add_argument("--since", default="24h", help="how far back: 1h, 24h (the default), 7d, ...")
    parser.add_argument("--kind", default=None, help="only this kind (prompt-trimmed, http-500, cpu-spill, ...)")
    parser.add_argument("--watch", action="store_true", help="keep reading: print each new event (Ctrl+C stops)")
    parser.add_argument("--from-start", action="store_true", help="read the server log from its top, not its end")
    parser.add_argument("--json", action="store_true", help="print the events as JSON lines")
    args = parser.parse_args(argv)
    host, ok = _host(args.host, "halo ollama events")
    if not ok:
        return 1
    show = (lambda e: print(json.dumps(e, default=str))) if args.json else (lambda e: print(format_event(e)))
    _written, why = server_log.scan(_state_dir(), host, from_start=args.from_start)
    try:
        rows = read_events(_state_dir(), since=args.since, kind=args.kind, host=host.name if args.host and host else None)
    except ValueError as e:
        print(f"halo ollama events: {e}", file=sys.stderr)
        return 2
    for e in rows:
        show(e)
    if not rows and not args.watch:
        name = host.name if host is not None else "this host"
        print(f"no events yet: {name}'s server log is read from 3.3.4.0 on" + (f" ({why})" if why else
              " (--from-start reads it from the top)"))
    if args.watch:
        import threading
        stop = threading.Event()
        try:
            server_log.watch(_state_dir(), host, stop, on_event=lambda e: (not args.kind or e["kind"] == args.kind)
                             and show(e))
        except KeyboardInterrupt:
            stop.set()
    return 0


def cmd_ollama_crashes(argv: list) -> int:
    """`halo ollama crashes [--host H] [--why] [--json]`: every crash fingerprint, newest first."""
    from halo_harness.ollama_steward.fingerprint_facts import why_lines
    from halo_harness.ollama_steward.fingerprints import read
    from halo_harness.ollama_steward.rules_crash import fixes_for
    parser = argparse.ArgumentParser(
        prog="halo ollama crashes", add_help=True,
        description="The crash fingerprints the steward recorded from each host's server events: the model, its "
                    "family and quant, the window it ran at, the KV type, flash attention, whether it spilled, and "
                    "the signature (a CUDA illegal memory access, a runner that died, a failed load). Read-only.")
    parser.add_argument("--host", default=None, help="only this host's fingerprints")
    parser.add_argument("--why", action="store_true", help="each one's evidence: the load it died in, the settings in "
                        "force then, the request's window, the load command, and the fixes when it repeats")
    parser.add_argument("--json", action="store_true", help="print the fingerprints as JSON lines")
    args = parser.parse_args(argv)
    rows = read(_state_dir(), host=args.host)
    for fp in rows:
        if args.json:
            print(json.dumps(fp, default=str))
            continue
        bits = [f"{fp.get('family') or '?'} {fp.get('quant') or ''}".strip(), f"model from {fp.get('model_from')}"]
        print(f"{fp.get('host') or '?'} {fp.get('model') or '(model unknown)'}: {fp['line']}")
        if not args.why:
            print(f"    {' · '.join(bits)}" + (f" · {fp['evidence'][0][:140]}" if fp.get("evidence") else ""))
            continue
        for line in why_lines(fp):
            print(f"  {line}")
        if int(fp.get("count") or 1) >= 2:
            for f in fixes_for(fp):
                print(f"    fix ({'Halo' if f['side'] == 'halo' else 'on the host'}): {f['line']} (costs: {f['cost']})")
    if not rows and not args.json:
        print("no crash fingerprints" + (f" for {args.host}" if args.host else "") +
              ": they are written from the server's events (halo ollama events) as crashes happen")
    return 0
