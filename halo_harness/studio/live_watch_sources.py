"""halo_harness.studio.live_watch_sources -- what Studio's watcher and the Live panel routes read (Halo 3.0.5.0
R4; 3.1.0.0 R2 moved the feed tap to live_feed.py and the session commands to live_send.py): the view, this
harness's id and name, the Orchestra gates, the claims and whether attention pushes are ready.
"""

from __future__ import annotations

import time
from pathlib import Path

_repo_cache: dict = {}


def local_id(server) -> str:
    from halo_harness.peers.identity import harness
    return str(harness()["id"])


def is_local(server, hid: str) -> bool:
    return hid in ("local", local_id(server))


def view(server, home) -> dict:
    from halo_harness.studio.live_api import view_for
    return view_for(server, home)


def by(home=None) -> str:
    from halo_harness.peers.identity import harness_name
    return harness_name(Path(home) if home is not None else None)


# ---- the sources ------------------------------------------------------------------------
def packs(server) -> list:
    """The row files of the running packs' declared attention kinds (3.2.0.0 R3, live/pack_attention.py)."""
    try:
        from halo_harness.live.pack_attention import pending
        return pending(getattr(server, "cwd", None), getattr(server, "state_dir", None))
    except Exception:
        return []


def pages(server) -> int:
    """3.3.11.0 R2: how many Studio pages the feed serves now (studio/events.py listeners); 0 without a feed."""
    try:
        bridge = getattr(server, "events", None)
        return int(bridge.listeners()) if bridge is not None else 0
    except Exception:
        return 0


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


def claims(view_: dict, local: str) -> list:
    """The live Orchestra claims of this machine's repos."""
    from halo_harness.live.conflicts import run_claims
    roots = []
    for h in view_.get("harnesses") or []:
        for s in h.get("sessions") or []:
            root = (s.get("project") or {}).get("root") if isinstance(s.get("project"), dict) else None
            if root and root not in roots:
                roots.append(root)
    try:
        return run_claims(roots)
    except Exception:
        return []


def push_ready(home) -> bool:
    from halo_harness.peers import identity
    from halo_harness.live import push
    if identity.config_value("attention.signal", True, Path(home)) is False:
        return False
    try:
        return push.ready(home)
    except Exception:
        return False
