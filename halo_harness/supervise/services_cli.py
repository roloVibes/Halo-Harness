"""halo_harness.supervise.services_cli -- `halo supervise services` and `halo supervise service start|stop` (Halo
3.3.13.0 R3; docs/COMMANDS-supervise.md), the services' lines in `halo supervise status`, and the lane that answers a
transport's session requests between two ticks (remote/session_start.py).

    halo supervise services [--json]                every pack service: <pack>/<name>  <state line>  -- <description>
    halo supervise service start|stop <pack>/<name> [--json]   asked of the running supervisor; its next tick applies it
"""

from __future__ import annotations

import json
import threading

LANE_S = 0.5


def _lines(rows: list) -> "list[str]":
    from halo_harness.supervise.services_rows import state_line
    return [f"  {r['key']}  {state_line(r)}" + (f" -- {r['description']}" if r.get("description") else "")
            for r in rows]


def status_lines(state_dir) -> "list[str]":
    from halo_harness.supervise.services_rows import rows
    got = rows(state_dir)
    return ([f"services ({len(got)}):"] + _lines(got)) if got else []


def cmd(a, state_dir) -> int:
    from halo_harness.supervise.services_rows import row, rows, want
    if a.cmd == "services":
        got = rows(state_dir)
        if a.json:
            print(json.dumps({"ok": True, "services": got}, indent=2, default=str))
        elif not got:
            print("no pack service: a pack that is enabled and granted `services` brings one (halo pack list)")
        else:
            print("\n".join(_lines(got)))
        return 0
    known = row(a.key, state_dir)
    if known is None and "/" not in a.key:
        msg = f"{a.key!r}: name a service as <pack>/<name> (halo supervise services lists them)"
        print(json.dumps({"ok": False, "error": msg}) if a.json else msg)
        return 2
    line = want(a.key, a.verb, state_dir)
    if known is None:
        line += " -- it is not in the supervisor's list yet (is the pack enabled and granted services?)"
    print(json.dumps({"ok": True, "line": line}) if a.json else line)
    return 0


def start_lane(state_dir) -> threading.Event:
    """A thread that serves session requests every LANE_S seconds until the event is set (the tick is 5 s)."""
    from halo_harness.remote import session_start
    done = threading.Event()

    def run() -> None:
        while not done.wait(LANE_S):
            try:
                session_start.serve(state_dir)
            except Exception:
                pass
    threading.Thread(target=run, name="halo-supervise-sessions", daemon=True).start()
    return done
