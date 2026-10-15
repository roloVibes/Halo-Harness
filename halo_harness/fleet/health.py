"""halo_harness.fleet.health -- a harness's health in one small, read-only
answer (Halo 3.0.5.0 "Fleet" round R4): the doctor subset Fleet's Health
panel shows per harness. On this harness it is computed directly; a member
answers the fleet protocol's read-only `doctor` command with the same dict
(fleet/control.py), so the hub asks over the relay.

    subset(probe=True) -> {version, python, os, providers: [{name, configured, reachable, note}],
                           disk: {free_gb, total_gb, free_pct}, sockets, studio: {version, running}, status}

`providers`: OpenRouter, Databricks and Anthropic, each configured or not
(credentials only, never a key) and, when configured and `probe`, reachable
(a connect-phase probe through providers/http.py's choke point, so offline
mode skips it; no request is sent, no token spent). `sockets` counts the
live control sockets in this harness's registry. `status` is ok, warn (a
configured provider unreachable, or under 10 % disk free) or bad (no
provider configured, or under 2 % free). Nothing here writes a file.
"""

from __future__ import annotations

import platform
import shutil
import sys
import threading
import time
from typing import Optional

PROVIDERS = (("openrouter", "OpenRouter"), ("databricks", "Databricks"), ("anthropic", "Anthropic"))
PROBE_TIMEOUT_S = 3
CACHE_S = 60.0
_cache: dict = {}
_lock = threading.Lock()


def _provider(name: str, label: str, probe: bool) -> dict:
    out = {"name": label, "configured": False, "reachable": None, "note": ""}
    try:
        from halo_harness.providers.enablement import credentials_present
        out["configured"] = bool(credentials_present(name))
    except Exception as e:
        out["note"] = f"could not check ({type(e).__name__})"
        return out
    if not out["configured"]:
        out["note"] = "not configured"
        return out
    if not probe:
        return out
    try:
        from halo_harness.providers.reachability import probe_host_reachable, provider_base_url
        url = provider_base_url(name)
        if url:
            ok, why = probe_host_reachable(url, connect_timeout=PROBE_TIMEOUT_S)
            out["reachable"], out["note"] = ok, "" if ok else " ".join(str(why or "").split())[:120]
    except Exception as e:  # offline mode raises before a socket opens
        out["reachable"], out["note"] = False, f"{type(e).__name__}: {e}"[:120]
    return out


def _disk() -> dict:
    from halo_harness.config.paths import bridge_home
    try:
        u = shutil.disk_usage(str(bridge_home()))
    except OSError:
        return {"free_gb": None, "total_gb": None, "free_pct": None}
    return {"free_gb": round(u.free / 1e9, 1), "total_gb": round(u.total / 1e9, 1),
            "free_pct": round(100.0 * u.free / u.total, 1) if u.total else None}


def _sockets() -> int:
    """Live control sockets in the registry, read without `list_live` (which prunes the file)."""
    try:
        from halo_harness.config.paths import bridge_home
        from halo_harness.remote import registry
        path = bridge_home() / "run" / registry.FILENAME
        if not path.is_file():
            return 0
        return sum(1 for e in registry._load(path) if isinstance(e, dict) and not e.get("private") and registry._entry_alive(e))
    except Exception:
        return 0


def _studio() -> dict:
    from halo_harness import __version__
    try:
        from halo_harness.config.paths import bridge_home
        from halo_harness.studio.launch import read_info
        running = read_info(bridge_home()) is not None
    except Exception:
        running = False
    return {"version": __version__, "running": running}


def status_of(h: dict) -> str:
    provs = h.get("providers") or []
    free = (h.get("disk") or {}).get("free_pct")
    if not any(p.get("configured") for p in provs) or (isinstance(free, (int, float)) and free < 2):
        return "bad"
    if any(p.get("configured") and p.get("reachable") is False for p in provs) or (isinstance(free, (int, float)) and free < 10):
        return "warn"
    return "ok"


def subset(probe: bool = True) -> dict:
    from halo_harness import __version__
    got: dict = {}
    threads = [threading.Thread(target=lambda n=n, lb=lb: got.__setitem__(n, _provider(n, lb, probe)), daemon=True,
                                name="halo-fleet-health") for n, lb in PROVIDERS]
    for t in threads:
        t.start()
    for t in threads:
        t.join(PROBE_TIMEOUT_S + 2)
    out = {"version": __version__, "python": platform.python_version(), "os": (platform.system() or sys.platform).lower(),
           "providers": [got.get(n) or {"name": lb, "configured": None, "reachable": None, "note": "no answer"}
                         for n, lb in PROVIDERS],
           "disk": _disk(), "sockets": _sockets(), "studio": _studio(), "checked": time.time()}
    out["status"] = status_of(out)
    return out


def cached(key: str, fetch, refresh: bool = False, ttl: float = CACHE_S) -> "tuple[dict, bool]":
    """`(value, from_cache)`: `fetch()` at most once per `ttl` per key."""
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
    if hit is not None and not refresh and now - hit[0] < ttl:
        return hit[1], True
    value = fetch()
    with _lock:
        _cache[key] = (now, value)
    return value, False


def forget() -> None:
    with _lock:
        _cache.clear()


def member_subset(status: Optional[dict], doctor: Optional[dict]) -> dict:
    """A member's row from its `status` and `doctor` answers (either may be missing)."""
    d = dict(doctor or {})
    if not d:
        d = {"version": None, "providers": [], "disk": {}, "sockets": None, "studio": {}, "status": "unknown"}
    elif "status" not in d:
        d["status"] = status_of(d)
    if isinstance(status, dict):
        d["session_model"] = status.get("model")
    return d
