"""halo_harness.remote.cli_run -- `halo remote signal run | status | off | on`
(Halo 2.0.9 round 4).

run     the bridge in the foreground (`--daemon` writes the service-manager
        file for this OS and prints the one command that enables it)
status  bridge pid and state, signal-cli version, account, peers, last audit
off     the kill switch: ask a running bridge to end (a stop file it polls)
        and set remote.signal.enabled to false; `on` sets it back
"""

from __future__ import annotations

import json
import threading
from datetime import datetime

from halo_harness.remote import bridge_state as BS
from halo_harness.remote import cli_common as C
from halo_harness.remote import daemon_units, signal_install as inst
from halo_harness.remote.signal_config import (bridge_settings, load_signal_config, remote_dir, set_signal_enabled,
                                               signal_enabled)


def make_transport(cfg: dict):
    """The real signal-cli transport (tests replace this)."""
    from halo_harness.remote.signal_transport import SignalTransport
    return SignalTransport(cfg)


def cmd_run(argv: list) -> int:
    p = C.make_parser("run", "Run the Signal bridge in the foreground.")
    p.add_argument("--daemon", action="store_true", help="write the service-manager file instead of running")
    p.add_argument("--os", choices=daemon_units.OS_NAMES, help="write the file for another OS (with --daemon)")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    if a.daemon:
        path, enable = daemon_units.write_unit(a.os)
        if a.json:
            C.emit_json({"ok": True, "unit": str(path), "enable": enable})
        else:
            print(f"Wrote {path}\nHalo does not enable it. To start the bridge at login, run:\n  {enable}")
        return 0
    cfg = load_signal_config()
    if not cfg.get("account"):
        return C.fail(a.json, "no_account", "No Signal account yet. Run `halo remote signal setup`, then `register` or `link`.")
    if not signal_enabled():
        print("remote.signal.enabled is false, so the bridge is not started. Turn it on with `halo remote signal on`.")
        return 0
    live = BS.read()
    if live["running"]:
        return C.fail(a.json, "already_running", f"A bridge is already running (pid {live['pid']}). "
                      "`halo remote signal off` stops it.")
    from halo_harness.remote import runtime
    BS.clear_stop()
    config = {**bridge_settings(), "identity_model": cfg.get("identity_model"), "own_aci": cfg.get("own_aci")}
    pulse, stop = BS.BridgeState(), threading.Event()
    if not a.json:
        tail = str(cfg["account"])[-4:]
        print(f"Halo remote control: bridge running for the account ending {tail}. Ctrl+C or `halo remote signal off` stops it."
              + ("" if runtime.enabled() else "\nNote: remote.enabled is false, so no session opens a control socket to attach to."))
    from halo_harness.remote.bridge import run_bridge
    try:
        run_bridge(config, make_transport(cfg), stop=stop, pulse=pulse)
    except KeyboardInterrupt:
        stop.set()
    finally:
        BS.clear_stop()
    return 0


def _last_audit_ts():
    try:
        lines = (remote_dir() / "audit.jsonl").read_text(encoding="utf-8").splitlines()
        return json.loads(lines[-1]).get("ts") if lines else None
    except (OSError, ValueError, IndexError):
        return None


def status_report() -> dict:
    from halo_harness.remote.pairing import Pairing
    cfg, pairing, bridge = load_signal_config(), Pairing(), BS.read()
    peers = pairing.peers()
    version = inst.version_of(C.binary_words(cfg)) if cfg.get("account") or cfg.get("binary") != "signal-cli" else None
    return {"enabled": signal_enabled(), "bridge": bridge, "signal_cli_version": version, "pinned_version": inst.VERSION,
            "account": cfg.get("account") or None, "identity_model": cfg.get("identity_model"),
            "peers": len(peers), "blocked": sum(1 for p in peers.values() if p.get("blocked_until_reverified")),
            "pending_requests": len(pairing.pending()), "notices": len(pairing.notices()), "last_audit_ts": _last_audit_ts()}


def cmd_status(argv: list) -> int:
    a, rc = C.parse(C.make_parser("status", "Show the bridge, signal-cli, the account and the paired phones."), argv)
    if a is None:
        return rc
    r = status_report()
    if a.json:
        C.emit_json({"ok": True, **r})
        return 0
    b = r["bridge"]
    pid = f" (pid {b['pid']})" if b.get("pid") and b["running"] else ""
    print(f"bridge:       {b['state']}{pid}   remote.signal.enabled: {str(r['enabled']).lower()}")
    print(f"signal-cli:   {r['signal_cli_version'] or 'not found'} (pinned {r['pinned_version']})")
    print(f"account:      {r['account'] or 'none yet'} ({r['identity_model']})")
    print(f"peers:        {r['peers']} paired, {r['blocked']} blocked; {r['pending_requests']} contact request(s) waiting")
    last = r["last_audit_ts"]
    print("last command: " + (datetime.fromtimestamp(last).strftime("%Y-%m-%d %H:%M:%S") if last else "none yet"))
    if r["notices"]:
        print(f"{r['notices']} notice(s) waiting; `halo remote signal pair` shows them.")
    return 0


def cmd_off(argv: list) -> int:
    a, rc = C.parse(C.make_parser("off", "Stop the bridge and set remote.signal.enabled to false."), argv)
    if a is None:
        return rc
    from halo_harness.remote.dialog_model import kill_switch
    res = kill_switch()
    was_running, stopped = res["was_running"], res["stopped"]
    if a.json:
        C.emit_json({"ok": True, "was_running": was_running, "stopped": stopped, "enabled": False})
    else:
        print(("The bridge stopped. " if was_running and stopped else
               "The bridge is still shutting down. " if was_running else "No bridge was running. ")
              + "remote.signal.enabled is false; `halo remote signal on` turns it back on.")
    return 0


def cmd_on(argv: list) -> int:
    a, rc = C.parse(C.make_parser("on", "Set remote.signal.enabled to true."), argv)
    if a is None:
        return rc
    set_signal_enabled(True)
    C.emit_json({"ok": True, "enabled": True}) if a.json else print("remote.signal.enabled is true. Start the bridge with `halo remote signal run`.")
    return 0
