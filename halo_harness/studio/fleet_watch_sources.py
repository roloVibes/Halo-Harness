"""halo_harness.studio.fleet_watch_sources -- what the fleet watcher and the
Fleet panel routes read (Halo 3.0.5.0 "Fleet" round R4; 3.1.0.0 R2 renamed
it from fleet_watch_io.py and moved the feed tap to fleet_feed.py and the
session commands to fleet_send.py): the view, the local harness id and the
fleet name, the flow, team and Orchestra gates, the hub's open commands,
the claims and whether attention pushes are ready.
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


# ---- the sources ------------------------------------------------------------------------
def flows(home) -> list:
    try:
        from halo_harness.studio.flow_model import run_rows
        from halo_harness.studio.flow_runs import live_id
        return [r for r in run_rows(home, live_id()) if r.get("waiting_step")]
    except Exception:
        return []


def teams(server) -> list:
    """The open gates of the team run of Studio's repo (3.0.8.0 R2, fleet/team_attention.py)."""
    try:
        from halo_harness.fleet.team_attention import gated
        return gated(getattr(server, "cwd", None), getattr(server, "state_dir", None))
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
