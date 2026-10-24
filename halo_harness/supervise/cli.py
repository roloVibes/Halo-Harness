"""halo_harness.supervise.cli -- `halo supervise` (Halo 3.1.8.0 R1,
docs/COMMANDS-supervise.md).

    halo supervise                 run the daemon in the foreground (Ctrl+C stops it)
    halo supervise --daemon        detach it (studio/launch.py's way; Windows DETACHED_PROCESS) and return
    halo supervise --service [--os OS]   write the service-manager file (never enabled) and print the one enable command
    halo supervise status [--json] the pulse: pid, state, the goal counts, what waits on you
    halo supervise stop            ask a running supervisor to end (a stop file it polls)

One supervisor per state dir: a second `halo supervise` sees the live pulse
and says who runs. Exit codes: 0 done, 1 could not (the reason on stderr),
2 usage.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

from halo_harness.supervise import pulse, queue
from halo_harness.supervise.settings import settings


def _state_dir():
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def cmd_supervise(argv: list) -> int:
    p = argparse.ArgumentParser(prog="halo supervise", description="The supervisor: a goal queue that runs without a TUI.")
    p.add_argument("--daemon", action="store_true", help="detach and return (runs in the background)")
    p.add_argument("--service", action="store_true", help="write the service-manager file (never enabled) and print the enable command")
    p.add_argument("--os", choices=("linux", "macos", "windows"), help="write the service file for another OS (with --service)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    sub = p.add_subparsers(dest="cmd")
    st = sub.add_parser("status", help="the pulse: pid, state, the goal counts")
    st.add_argument("--json", action="store_true", help="machine-readable output")
    sp = sub.add_parser("stop", help="ask a running supervisor to end")
    sp.add_argument("--json", action="store_true", help="machine-readable output")
    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    state_dir = _state_dir()
    if a.cmd == "status":
        return _status(state_dir, a.json)
    if a.cmd == "stop":
        return _stop(state_dir, a.json)
    if a.service:
        return _service(state_dir, a.os, a.json)
    if a.daemon:
        return _daemon(state_dir, a.json)
    return run_foreground(state_dir)


def _status(state_dir, as_json: bool) -> int:
    row = pulse.read(state_dir)
    counts = queue.counts(state_dir)
    if as_json:
        print(json.dumps({"ok": True, **row, "goals": counts}, indent=2, default=str))
        return 0
    if not row["running"]:
        print("supervisor: not running. `halo supervise` starts it; `halo supervise --daemon` in the background.")
        return 0
    g = counts
    print(f"supervisor: {row['state']} (pid {row['pid']})")
    print(f"goals: {g['queued']} queued, {g['running']} running, {g['parked']} parked, {g['done']} done")
    from halo_harness.supervise import decisions
    from halo_harness.supervise.replan_rows import line as replan_line
    for goal in queue.all_goals(state_dir):  # R2: what each goal's replans did
        if replan_line(goal):
            print(f"  {goal['id']}: {replan_line(goal)}")
        elif goal.get("replan_off") and goal.get("state") not in ("done", "stopped"):  # 3.2.1.0 R2: a workflow run
            print(f"  {goal['id']}: replan off -- {goal['replan_off']}")
    waiting = decisions.open_rows(state_dir)
    if waiting:
        print(f"{len(waiting)} decision(s) wait on you (Studio's Attention):")
        for d in waiting[:8]:
            print(f"  {d['kind']}  {d.get('what')}")
    return 0


def _stop(state_dir, as_json: bool) -> int:
    was = pulse.request_stop(state_dir)
    if as_json:
        print(json.dumps({"ok": True, "was_running": was}))
    else:
        print("asked the supervisor to stop." if was else "no supervisor was running (the stop file is set anyway).")
    return 0


def _unit():
    from halo_harness.remote.daemon_units import files_for
    return {"stem": "halo-supervise", "label": "dev.halo.supervise", "desc": "Halo supervisor (the goal queue)",
            "task": "Halo Supervise", "files": files_for}


def _service(state_dir, os_n: Optional[str], as_json: bool) -> int:
    from halo_harness.remote.daemon_units import run_argv, write_unit
    argv = run_argv()[:-3] + ["supervise"]  # `halo supervise`, not `remote signal run`
    path, enable = write_unit(os_n, argv, env={}, unit=_unit(), out_dir=queue.root(state_dir))
    if as_json:
        print(json.dumps({"ok": True, "unit": str(path), "enable": enable}))
    else:
        print(f"Wrote {path}\nHalo does not enable it. To start the supervisor at login, run:\n  {enable}")
    return 0


def _daemon(state_dir, as_json: bool) -> int:
    live = pulse.read(state_dir)
    if live["running"]:
        msg = f"a supervisor is already running (pid {live['pid']})."
        print(json.dumps({"ok": False, "error": msg, "pid": live["pid"]}) if as_json else msg, file=None if as_json else sys.stderr)
        return 1
    import subprocess
    argv = [sys.executable, "-u", "-m", "halo_harness", "supervise"]
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(argv, **kwargs)
    except OSError as e:
        print(f"could not start the supervisor: {e}", file=sys.stderr)
        return 1
    deadline = time.time() + 15.0
    while time.time() < deadline:
        if pulse.read(state_dir)["running"]:
            break
        if proc.poll() is not None:
            print("the supervisor exited before it registered (see its config).", file=sys.stderr)
            return 1
        time.sleep(0.2)
    row = pulse.read(state_dir)
    print(json.dumps({"ok": row["running"], "pid": row["pid"]}) if as_json else
          f"supervisor running in the background (pid {row['pid']}). `halo supervise status` shows it.")
    return 0 if row["running"] else 1


def run_foreground(state_dir, *, ticks: Optional[int] = None, popen=None, feed: Optional[callable] = None) -> int:
    """Run the loop until the stop file appears or Ctrl+C; `ticks` (tests) stops after that many."""
    from halo_harness.supervise.loop import Supervisor
    live = pulse.read(state_dir)
    if live["running"]:
        print(f"a supervisor is already running (pid {live['pid']}). `halo supervise stop` ends it.", file=sys.stderr)
        return 1
    pulse.clear_stop(state_dir)
    cfg = settings(state_dir)
    drain, closer = (feed, None) if feed is not None else _bridge_feed()
    sup = Supervisor(state_dir, popen=popen, feed=drain)
    sup.pulse.write("starting", queue.counts(state_dir))
    print(f"Halo supervisor: the goal queue is running. Ctrl+C or `halo supervise stop` ends it. "
          f"(tick {cfg['tick_s']:g}s, {cfg['max_running']} at a time)", flush=True)
    n = 0
    try:
        while not pulse.stop_requested(state_dir):
            try:
                sup.tick()
            except Exception as e:  # one bad tick never ends the daemon; the next one tries again
                print(f"halo supervise: a tick failed: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            n += 1
            if ticks is not None and n >= ticks:
                break
            time.sleep(cfg["tick_s"])
    except KeyboardInterrupt:
        pass
    finally:
        sup.close()
        if closer is not None:
            closer()
        pulse.clear_stop(state_dir)
    return 0


def _bridge_feed():
    """`(drain, close)`: a live EventBridge (studio/events.py) watches every session's control socket and
    its frames collect in a deque the loop drains each tick -- so `on: event`/`on: message` triggers armed by
    the supervisor fire. None (no feed) under BRIDGE_TEST_NO_BACKGROUND_NET: a test passes its own `feed`."""
    import os
    if os.environ.get("BRIDGE_TEST_NO_BACKGROUND_NET"):
        return None, None
    import collections
    from halo_harness.studio.events import EventBridge
    frames: "collections.deque" = collections.deque(maxlen=4000)
    bridge = EventBridge()
    bridge.taps.append(lambda f: frames.append(f) if isinstance(f, dict) else None)
    bridge.start()

    def drain() -> list:
        out = []
        while frames:
            out.append(frames.popleft())
        return out
    return drain, bridge.close
