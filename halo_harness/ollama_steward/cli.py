"""halo_harness.ollama_steward.cli -- the steward's commands (Halo 3.3.4.0).

- `halo ollama hardware [--host NAME] [--json]` (R1): the hardware card of
  each configured Ollama host, or of one. Read-only: the server log, the
  server's `/api/version` and `/api/ps`, `nvidia-smi` / `system_profiler`
  where local, the ssh GPU read for a remote host with `ssh:`.
- `halo ollama traffic [--host H] [--model M] [--since 1h|24h|7d] [--json]`
  (R2): the ledger's rollups per host and model (traffic.py).
- `halo ollama events [--host H] [--since] [--kind K] [--watch]
  [--from-start] [--json]` (R2): the local server's events (server_log.py).
- `halo ollama crashes [--host H] [--why] [--json]` (3.3.6.0 R2, R3) and
  `halo ollama log` (3.3.6.0 R3) live in cli_logs.py with `events`.
"""

from __future__ import annotations

import argparse
import json
import sys


def cmd_ollama_hardware(argv: list) -> int:
    from halo_harness.ollama_steward.hardware import format_card, hardware_card
    from halo_harness.providers.ollama import resolve_ollama_hosts

    parser = argparse.ArgumentParser(
        prog="halo ollama hardware", add_help=True,
        description="Each Ollama host's hardware card: the GPUs and their memory, the server's own settings "
                    "(from its log's startup lines), what is loaded, and what else holds the card. Nothing is "
                    "sent to a model and no server setting changes.")
    parser.add_argument("--host", default=None, help="only this configured host (by name), not every one")
    parser.add_argument("--json", action="store_true", help="print the card(s) as JSON instead of lines")
    args = parser.parse_args(argv)

    hosts = resolve_ollama_hosts()
    if args.host:
        hosts = [h for h in hosts if h.name.lower() == args.host.lower()]
        if not hosts:
            print(f"halo ollama hardware: no configured host named {args.host!r} (see `ollama.hosts` in "
                  f"~/.halo/config.json)", file=sys.stderr)
            return 1
    if not hosts:
        print("No Ollama hosts configured.", file=sys.stderr)
        return 0
    cards = [(h, hardware_card(h)) for h in hosts]
    if args.json:
        print(json.dumps({h.name: card for h, card in cards}, indent=2, default=str))
        return 0
    for i, (host, card) in enumerate(cards):
        if i:
            print()
        for line in format_card(card, host_name=host.name):
            print(line)
    return 0


def _state_dir():
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def _hosts_named(name):
    from halo_harness.providers.ollama import resolve_ollama_hosts
    hosts = resolve_ollama_hosts()
    return [h for h in hosts if not name or h.name.lower() == name.lower()], hosts


def cmd_ollama_traffic(argv: list) -> int:
    """`halo ollama traffic [--host H] [--model M] [--since 1h|24h|7d] [--json]` (3.3.4.0 R2)."""
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.ollama_steward.traffic import format_rollups, rollup
    parser = argparse.ArgumentParser(
        prog="halo ollama traffic", add_help=True,
        description="Per host and model, the calls this machine's ledger holds (its own and, on a hub, every "
                    "member's): prompt sizes against the window sent, trims, cut replies, errors, reloads, the "
                    "eval rate and which machine called. Read from ~/.halo/ollama/traffic.jsonl.")
    parser.add_argument("--host", default=None, help="only this host (its name here, or its url)")
    parser.add_argument("--model", default=None, help="only this model")
    parser.add_argument("--since", default="24h", help="how far back: 1h, 24h (the default), 7d, ...")
    parser.add_argument("--json", action="store_true", help="print the rollups as JSON")
    args = parser.parse_args(argv)
    try:
        lines = read_calls(_state_dir(), since=args.since, model=args.model)
    except ValueError as e:
        print(f"halo ollama traffic: {e}", file=sys.stderr)
        return 2
    _named, hosts = _hosts_named(None)
    rows = rollup(lines, hosts)
    if args.host:
        rows = [r for r in rows if r["host"].lower() == args.host.lower()
                or str(getattr(r["host_obj"], "url", "")).rstrip("/") == args.host.rstrip("/")]
    if args.json:
        print(json.dumps([{k: v for k, v in r.items() if k != "host_obj"} for r in rows], indent=2, default=str))
        return 0
    if not rows:
        name = args.host or (hosts[0].name if hosts else "this host")
        print(f"no ledger yet: calls to {name} are recorded from 3.3.4.0 on")
        return 0
    for line in format_rollups(rows):
        print(line)
    return 0


from halo_harness.ollama_steward.cli_logs import cmd_ollama_crashes, cmd_ollama_events, cmd_ollama_log  # noqa: E402,F401
