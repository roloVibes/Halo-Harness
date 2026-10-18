#!/usr/bin/env python3
"""tools/live_fleet_check.py -- the owner's scripted two-machine fleet check
(Halo 3.1.2.0 R3, docs/FLEET.md "The two-machine check"). One command on
each box:

    # on this host (the hub):
    python tools/live_fleet_check.py hub [--fake] [--json] [--keep] [--timeout 30]

    # on the other box (the Kali VM), with the code the hub printed:
    python tools/live_fleet_check.py member <host>:<port> --code "acorn ..." [--fake]

`hub` starts Studio with the fleet hub, prints the pairing code and the exact
join command for the other box, waits for it to join, then drives the check
(fleet/live_check.py): `fleet who`, a one-part mission on the member, a team
with a delegated agent stage and a delegated flow stage, and `recall --fleet`.
Each step prints PASS / FAIL with its evidence; the run ends with a summary
and a non-zero exit code if any step failed; `--json` writes
`live-fleet-check.json`. `--fake` runs it with no model call on either box
(the member must be started with `--fake` too); the real configured model
otherwise. `--keep` leaves the hub running after the check.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

JSON_FILE = "live-fleet-check.json"


def write_json(report: dict, path: str = JSON_FILE) -> str:
    Path(path).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return str(Path(path).resolve())


def _state_dir() -> Path:
    from halo_harness.providers.config import default_state_dir
    return Path(default_state_dir())


def cmd_hub(a) -> int:
    from halo_harness.fleet import live_check
    from halo_harness.studio.fleet_hub_api import start_for_flag
    from halo_harness.studio.server import start_server
    import threading
    state_dir = _state_dir()
    server = start_server(port=0, cwd=Path.cwd(), state_dir=state_dir)
    threading.Thread(target=server.serve_forever, daemon=True, name="live-check-studio").start()
    print(start_for_flag(server, state_dir))
    hub = getattr(server, "fleet_hub", None)
    if hub is None:
        print("live-fleet-check: the fleet hub did not start here.", file=sys.stderr)
        return 1
    code = hub.pairing.new_code(1800)[0]
    print(f"\nOn the other box run:\n  python tools/live_fleet_check.py member {hub.url()} "
          f'--code "{code}"{" --fake" if a.fake else ""}\n')
    print(f"Waiting up to {a.join_timeout:g}s for it to join...")
    member = live_check._wait(lambda: live_check.member_of(hub), a.join_timeout)
    if member is None:
        print("live-fleet-check: no member joined in time.", file=sys.stderr)
        return 2
    print(f"{member.get('name')} joined. Running the check...\n")
    report = live_check.run_all(hub, state_dir, member=member, fake=a.fake, timeout=a.timeout)
    print(live_check.render(report))
    if a.json:
        print(f"\nWrote {write_json(report)}")
    if not a.keep:
        hub.stop()
    else:
        print("\n--keep: the hub is still running; Ctrl+C to stop it.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            hub.stop()
    return 0 if report.get("ok") else 1


def cmd_member(a) -> int:
    from halo_harness.fleet import identity, relay, store
    from halo_harness.theme import set_config_value
    set_config_value("fleet.allow_control", "all")
    set_config_value("fleet.recall.share", True)
    identity.forget_cache()
    restore = None
    if a.fake:
        from halo_harness.fleet.live_check_fakes import install
        restore = install()
    try:
        got = relay.join(a.hub, a.code, identity.harness(), allow_control="all")
        store.add_hub(got, got.pop("key"))
    except Exception as e:
        print(f"live-fleet-check: could not join {a.hub}: {e}", file=sys.stderr)
        return 1
    from halo_harness import headless
    from halo_harness.remote import runtime
    build = headless.build_session(cwd=Path.cwd(), print_mode=True)
    act = runtime.start_for_session(build.session, Path.cwd(), kind="tui")
    print(f"Joined {got.get('name')}. This box is live as {identity.fleet_name()}; the hub drives the check.")
    print("Ctrl+C when the hub says it is done.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        if act is not None:
            runtime.stop_one(act)
        if restore is not None:
            restore()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="live_fleet_check", description="The scripted two-machine fleet check.")
    sub = p.add_subparsers(dest="role", required=True)
    h = sub.add_parser("hub", help="run on this host: start the hub, wait for the member, drive the check")
    h.add_argument("--fake", action="store_true", help="no model calls on either box (the member runs --fake too)")
    h.add_argument("--json", action="store_true", help=f"write the report to {JSON_FILE}")
    h.add_argument("--keep", action="store_true", help="leave the hub running after the check")
    h.add_argument("--timeout", type=float, default=30.0, help="seconds each step may take (default 30)")
    h.add_argument("--join-timeout", type=float, default=300.0, help="seconds to wait for the member to join")
    h.set_defaults(fn=cmd_hub)
    m = sub.add_parser("member", help="run on the other box: join the hub and stay live")
    m.add_argument("hub", help="the hub: host:port or http(s)://host:port (the hub printed it)")
    m.add_argument("--code", required=True, help='the six words the hub printed, quoted')
    m.add_argument("--fake", action="store_true", help="no model calls (match the hub's --fake)")
    m.set_defaults(fn=cmd_member)
    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
