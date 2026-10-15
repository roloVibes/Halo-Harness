"""halo_harness.studio.fleet_watch_io -- what the fleet watcher and the Fleet
panel routes read and send (Halo 3.0.5.0 "Fleet" round R4): the view, the
local harness id, the flow and Orchestra gates, the hub's open commands, the
claims, the feed tap, and a session command sent the way the Fleet routes
send it (this harness: its control socket; a member: through the hub).
"""

from __future__ import annotations

import time
from pathlib import Path

_repo_cache: dict = {}


def local_id(server) -> str:
    hub = getattr(server, "fleet_hub", None)
    if hub is not None and hub.state.identity.get("id"):
        return str(hub.state.identity["id"])
    from halo_harness.fleet.identity import harness
    return str(harness()["id"])


def is_local(server, hid: str) -> bool:
    return hid in ("local", local_id(server))


def view(server, home) -> dict:
    from halo_harness.studio.fleet_hub_api import view_for
    return view_for(server, home)


def by(home=None) -> str:
    from halo_harness.fleet.identity import fleet_name
    return fleet_name(Path(home) if home is not None else None)


# ---- the feed ----------------------------------------------------------------------
def attach_tap(server, tap) -> None:
    taps = getattr(server, "event_taps", None)
    if taps is None:
        taps = server.event_taps = []
    if tap not in taps:
        taps.append(tap)
    from halo_harness.studio.events import bridge_for
    bridge_for(server).start()  # the local sessions' frames reach the tap with no browser open


def detach_tap(server, tap) -> None:
    for holder in (getattr(server, "event_taps", None), getattr(getattr(server, "events", None), "taps", None)):
        if holder is not None and tap in holder:
            holder.remove(tap)


def publish(server, frame: dict) -> None:
    bridge = getattr(server, "events", None)
    if bridge is not None:
        bridge.publish_local(frame)


# ---- the sources ------------------------------------------------------------------------
def flows(home) -> list:
    try:
        from halo_harness.studio.flow_model import run_rows
        from halo_harness.studio.flow_runs import live_id
        return [r for r in run_rows(home, live_id()) if r.get("waiting_step")]
    except Exception:
        return []


def orchestra(server) -> list:
    """This repo's Orchestra runs the gate stopped, each with its report's `stop_reason`."""
    try:
        from halo_harness.orchestra.report import load_report
        from halo_harness.studio import orchestra_model as OM
        from halo_harness.studio.orchestra_live import live_id
        cwd = str(getattr(server, "cwd", "") or "")
        hit = _repo_cache.get(cwd)
        if hit is None or time.monotonic() - hit[0] > 60:
            hit = _repo_cache[cwd] = (time.monotonic(), OM.repo_of(cwd))
        out = []
        for r in OM.run_rows(hit[1], live_id()):
            if r.get("state") != "stopped":
                continue
            run_dir = OM.find_run(hit[1], str(r.get("run_id")))
            report = (load_report(run_dir) or {}) if run_dir else {}
            out.append({**r, "stop_reason": str(report.get("stop_reason") or "")})
        return out
    except Exception:
        return []


def commands(server) -> list:
    hub = getattr(server, "fleet_hub", None)
    return hub.state.commands.open() if hub is not None else []


def claims(view_: dict, local: str) -> list:
    """The live Orchestra claims of this machine's repos and the ones members' workers announce."""
    from halo_harness.fleet.conflicts import run_claims
    roots, out = [], []
    for h in view_.get("harnesses") or []:
        for s in h.get("sessions") or []:
            if h.get("local") or str(h.get("id")) == local:
                root = (s.get("project") or {}).get("root") if isinstance(s.get("project"), dict) else None
                if root and root not in roots:
                    roots.append(root)
            else:
                out += [c for c in s.get("claims") or [] if isinstance(c, dict)]
    try:
        return run_claims(roots) + out
    except Exception:
        return out


def push_ready(home) -> bool:
    from halo_harness.fleet import identity, push
    if identity.config_value("fleet.attention.signal", True, Path(home)) is False:
        return False
    try:
        return push.ready(home)
    except Exception:
        return False


# ---- commands ------------------------------------------------------------------------------
def session_cmd(server, home, hid: str, sid: str, cmd: str, fields: dict, wait_s: float = 5.0):
    """`(status, body)` of one session command, this harness's or a member's."""
    if is_local(server, hid):
        from halo_harness.studio import fleet_api
        status, result = fleet_api.forward(sid, cmd, {**fleet_api.caller(), **fields})
        return (200, {"ok": True, "result": result}) if status == 200 else (status, result)
    return member_cmd(server, home, hid, sid, cmd, fields, wait_s)


def member_cmd(server, home, hid: str, sid: str, cmd: str, fields: dict, wait_s: float = 5.0):
    hub = getattr(server, "fleet_hub", None)
    if hub is None:
        from halo_harness.fleet.hub import running_call
        got = running_call(home, "POST", "local/command", {"harness": hid, "session_id": sid, "cmd": cmd,
                                                           "fields": fields, "wait_s": wait_s}, timeout=wait_s + 5.0)
        return got if got else (409, {"error": "no fleet hub runs here (`halo studio --fleet`, or `halo fleet serve`)"})
    return hub.state.commands.send(hid, sid, cmd, fields, by=by(hub.home), wait_s=wait_s)
