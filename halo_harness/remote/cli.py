"""halo_harness.remote.cli -- `halo remote ...` (Halo 2.0.9).

    halo remote sessions               live halo sessions that opened a control socket
    halo remote agents|steer|stop ...  one session's agent tree (3.0.5.0, cli_agents.py)
    halo remote transports [--json]    3.3.13.0 R3: the transports listening here (a pack's bridge) and the notes seam
    halo remote signal ...             3.3.13.0 R3: one line -- the Signal bridge is the signal pack now
"""

from __future__ import annotations

import json
import sys
import time

SIGNAL_MOVED = ("halo remote signal: the Signal bridge is the signal pack since 3.3.13.0 -- `halo pack install signal`, "
                "`halo pack enable signal --grant-all`, then `/signal` in a session or Setup -> Signal (docs/REMOTE.md "
                "\"Transports\")")
USAGE = """usage: halo remote sessions
       halo remote agents <session> [--json]
       halo remote steer <session> --agent <id> [--redirect] <text> [--json]
       halo remote stop <session> --agent <id> [--reason <text>] [--json]
       halo remote transports [--json]

  sessions    list the live halo sessions that opened a control socket
  agents      one session's agents: the main agent and every sub-agent, with state and cost
  steer       a note one agent reads before its next model call (--redirect replaces its task)
  stop        stop one agent and its subtree at the next tool boundary
  transports  the transports listening here (a pack's bridge, the signal pack's for one), and remote.enabled
  (the Signal bridge is the signal pack: halo pack install signal)"""


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
        print("No live sessions with a control socket (start halo; control.enabled is on unless you turned it off, "
              "and a --private session never lists itself).")
        return 0
    print(f"{'SESSION':<10} {'PID':>7} {'KIND':<6} {'MODE':<12} {'AGE':>5}  CWD  ->  ENDPOINT   TITLE")
    for r in rows:
        print(f"{str(r.get('session_id'))[:8]:<10} {r.get('pid', '?'):>7} {str(r.get('kind') or '-'):<6} "
              f"{str(r.get('mode') or '-'):<12} {_age(r.get('started')):>5}  {r.get('cwd', '?')}  ->  "
              f"{r.get('endpoint', '?')}   {r.get('title') or ''}")
    return 0


def cmd_transports(argv: list) -> int:
    from halo_harness.remote.session_identity import remote_enabled
    from halo_harness.remote.notify import listening
    names, on = listening(), remote_enabled()
    if "--json" in argv:
        print(json.dumps({"ok": True, "remote_enabled": on, "listening": names}, indent=2))
        return 0
    print(f"remote.enabled: {'true' if on else 'false (every transport stays silent)'}")
    print("transports listening: " + (", ".join(names) if names else
                                      "none (a pack's bridge listens while its service runs: halo supervise services)"))
    return 0


def cmd_remote(argv: list) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    if argv and argv[0] == "sessions" and len(argv) == 1:
        return cmd_sessions()
    if argv and argv[0] == "transports":
        return cmd_transports(argv[1:])
    if argv and argv[0] == "signal":
        print(SIGNAL_MOVED, file=sys.stderr)
        return 2
    if argv and argv[0] in ("agents", "steer", "stop"):
        from halo_harness.remote import cli_agents
        return getattr(cli_agents, "cmd_" + argv[0])(argv[1:])
    print(USAGE, file=sys.stderr)
    return 2
