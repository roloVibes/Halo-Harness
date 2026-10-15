"""halo_harness.remote.cli -- `halo remote ...` (Halo 2.0.9).

    halo remote sessions               live halo sessions that opened a control socket
    halo remote agents|steer|stop ...  one session's agent tree (3.0.5.0, cli_fleet.py)
    halo remote signal <verb> [...]    the Signal bridge: setup, register, link, run,
                                       pair, peers, unpair, reverify, status, off, on

Every `signal` verb takes `--json`. The verbs live in cli_setup.py,
cli_link.py, cli_run.py and cli_pair.py.
"""

from __future__ import annotations

import sys
import time

SIGNAL_VERBS = ("setup", "register", "link", "run", "pair", "peers", "unpair", "reverify", "status", "off", "on")
USAGE = """usage: halo remote sessions
       halo remote agents <session> [--json]
       halo remote steer <session> --agent <id> [--redirect] <text> [--json]
       halo remote stop <session> --agent <id> [--reason <text>] [--json]
       halo remote signal <verb> [--json] [...]

  sessions   list the live halo sessions that opened a control socket
  agents     one session's agents: the main agent and every sub-agent, with state and cost
  steer      a note one agent reads before its next model call (--redirect replaces its task)
  stop       stop one agent and its subtree at the next tool boundary
  signal     control halo from Signal; verbs:
    setup      choose dedicated number or linked device; find or download signal-cli
    register   register the dedicated number (captcha, SMS code, registration lock)
    link       link signal-cli to your own Signal account (QR code)
    run        run the bridge (--daemon writes a service-manager file)
    pair       list contact requests; --approve N issues the pairing code
    peers      list paired phones
    unpair     remove a paired phone
    reverify   trust a blocked phone's new safety number
    status     bridge, signal-cli, account and phones at a glance
    off / on   the kill switch: stop the bridge and disable it / enable it again"""


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
        print("No live sessions with a control socket (start halo; fleet.enabled is on unless you turned it off, "
              "and a --private session never lists itself).")
        return 0
    print(f"{'SESSION':<10} {'PID':>7} {'KIND':<6} {'MODE':<12} {'AGE':>5}  CWD  ->  ENDPOINT   TITLE")
    for r in rows:
        print(f"{str(r.get('session_id'))[:8]:<10} {r.get('pid', '?'):>7} {str(r.get('kind') or '-'):<6} "
              f"{str(r.get('mode') or '-'):<12} {_age(r.get('started')):>5}  {r.get('cwd', '?')}  ->  "
              f"{r.get('endpoint', '?')}   {r.get('title') or ''}")
    return 0


def cmd_signal(argv: list) -> int:
    verb, rest = (argv[0], argv[1:]) if argv else ("", [])
    if verb in ("", "-h", "--help") or verb not in SIGNAL_VERBS:
        print(USAGE, file=sys.stdout if verb in ("", "-h", "--help") else sys.stderr)
        return 0 if verb in ("", "-h", "--help") else 2
    if verb in ("setup", "register"):
        from halo_harness.remote import cli_setup as m
    elif verb == "link":
        from halo_harness.remote import cli_link as m
    elif verb in ("run", "status", "off", "on"):
        from halo_harness.remote import cli_run as m
    else:
        from halo_harness.remote import cli_pair as m
    return getattr(m, "cmd_" + verb)(rest)


def cmd_remote(argv: list) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    if argv and argv[0] == "sessions" and len(argv) == 1:
        return cmd_sessions()
    if argv and argv[0] == "signal":
        return cmd_signal(argv[1:])
    if argv and argv[0] in ("agents", "steer", "stop"):
        from halo_harness.remote import cli_fleet
        return getattr(cli_fleet, "cmd_" + argv[0])(argv[1:])
    print(USAGE, file=sys.stderr)
    return 2
