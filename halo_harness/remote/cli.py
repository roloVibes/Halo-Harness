"""halo_harness.remote.cli -- `halo remote ...` (Halo 2.0.9 round 2: only
`halo remote sessions`; the Signal subcommands arrive in later rounds)."""

from __future__ import annotations

import sys
import time

USAGE = "usage: halo remote sessions\n  sessions   list the live halo sessions that opened a control socket"


def _age(started) -> str:
    try:
        secs = max(0, int(time.time() - float(started)))
    except (TypeError, ValueError):
        return "?"
    if secs < 90:
        return f"{secs}s"
    if secs < 5400:
        return f"{secs // 60}m"
    return f"{secs // 3600}h"


def cmd_sessions() -> int:
    from halo_harness.remote import registry
    rows = registry.list_live()
    if not rows:
        print("No live sessions with a control socket (set remote.enabled to true and start halo).")
        return 0
    print(f"{'SESSION':<10} {'PID':>7} {'KIND':<6} {'MODE':<12} {'AGE':>5}  CWD  ->  ENDPOINT   TITLE")
    for r in rows:
        print(f"{str(r.get('session_id'))[:8]:<10} {r.get('pid', '?'):>7} {str(r.get('kind') or '-'):<6} "
              f"{str(r.get('mode') or '-'):<12} {_age(r.get('started')):>5}  {r.get('cwd', '?')}  ->  "
              f"{r.get('endpoint', '?')}   {r.get('title') or ''}")
    return 0


def cmd_remote(argv: list) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    if argv and argv[0] == "sessions" and len(argv) == 1:
        return cmd_sessions()
    print(USAGE, file=sys.stderr)
    return 2
