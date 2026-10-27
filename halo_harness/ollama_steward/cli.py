"""halo_harness.ollama_steward.cli -- `halo ollama hardware [--host NAME]
[--json]` (Halo 3.3.4.0 R1): the hardware card of each configured Ollama
host, or of one, as lines or as JSON. Read-only: the server log, the
server's `/api/version` and `/api/ps`, `nvidia-smi` / `system_profiler`
where local, the ssh GPU read for a remote host with `ssh:`.
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
