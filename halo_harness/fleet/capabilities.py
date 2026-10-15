"""halo_harness.fleet.capabilities -- what a harness can do, in one catalog
(Halo 3.0.6.0 "Fleet Missions" round R6). Computed in code; no model call.

    gather(home) -> {harness, at, hash, tags, mcp: [{name, transport, tools: [{name, desc}] | null, note?}],
                     skills: [name], roles: [{role, bio, lineup}], providers: [{name, id, ok}],
                     models: [{id, provider, best_for: [kind]}], craft_apps: [name],
                     media: {comfyui, models: [{name, kind}]},
                     hardware: {os, distro, release, cpu, cores, ram_gb, gpu: [{name, vram_gb}], disk_free_gb},
                     clis: {name: version | "installed" | null}, projects: [{name, repo, branch}],
                     integrations: {paperclip, postiz, signal}}

Full local paths never leave the machine: projects are basenames and repo
names, and every string in the catalog is scrubbed of absolute paths (a path
becomes its last component, the home directory `~`). `fleet.tags` (a list)
are the owner's own words for this harness; `fleet.capabilities.hide` names
MCP servers, tools (`tool` or `server/tool`) or skills that are never listed.

The catalog is cached at `<home>/fleet/capabilities.json` with its `hash`
(sha256 over everything but `at`, `hash` and the free disk, so it changes
only when what the harness can do changes). `current(home)` reads it and
gathers afresh when it is missing, stale (STALE_S) or asked to; the relay's
announce carries `summary()` and the hash and never waits on a gather
(`announce_fields`). Sections are in capabilities_sources.py (quick, from
disk), capabilities_probe.py (MCP) and capabilities_host.py (hardware, CLIs).
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Callable, Optional

FILE = "capabilities.json"
STALE_S = 3600.0
_bg: dict = {}
_bg_lock = threading.Lock()
_loaded: dict = {}
_DRIVE = re.compile(r"(?<![\w/])[A-Za-z]:[\\/][^\s\"'<>|,;]*")
_POSIX = re.compile(r"(?<![\w.~])/(?:home|Users|root|mnt|media|opt|srv|tmp|var|private)/[^\s\"'<>|,;]*")


def _home(home=None) -> Path:
    if home is not None:
        return Path(home)
    from halo_harness.fleet.identity import home as h
    return h()


def cache_path(home=None) -> Path:
    return _home(home) / "fleet" / FILE


def config(home=None) -> dict:
    """`{tags: [...], hide: {lower-cased names}}` from fleet.tags and fleet.capabilities.hide."""
    from halo_harness.fleet.identity import config_value
    h = _home(home)
    tags, hide = config_value("fleet.tags", [], h), config_value("fleet.capabilities.hide", [], h)
    tags = [tags] if isinstance(tags, str) else tags if isinstance(tags, list) else []
    hide = [hide] if isinstance(hide, str) else hide if isinstance(hide, list) else []
    clean = [" ".join(str(t).split())[:32] for t in tags if str(t).strip()]
    return {"tags": list(dict.fromkeys(clean))[:16], "hide": {str(n).strip().lower() for n in hide if str(n).strip()}}


def _base(m) -> str:
    text = m.group(0).rstrip("\\/.")
    return re.split(r"[\\/]", text)[-1] or "~"


def scrub(obj, homes: tuple = ()):
    """Every string with its absolute paths cut to their last component (`~` for a home)."""
    if isinstance(obj, dict):
        return {k: scrub(v, homes) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v, homes) for v in obj]
    if not isinstance(obj, str):
        return obj
    obj = _POSIX.sub(_base, _DRIVE.sub(_base, obj))
    for h in homes:
        if h and len(h) > 3:
            obj = obj.replace(h, "~")
    return obj


def apply_hide(cat: dict, hide: set) -> dict:
    if not hide:
        return cat
    mcp = []
    for s in cat.get("mcp") or []:
        if str(s.get("name")).lower() in hide:
            continue
        tools = s.get("tools")
        if isinstance(tools, list):
            low = str(s.get("name")).lower()
            tools = [t for t in tools if str(t.get("name")).lower() not in hide
                     and f"{low}/{str(t.get('name')).lower()}" not in hide
                     and f"mcp__{low}__{str(t.get('name')).lower()}" not in hide]
        mcp.append({**s, "tools": tools})
    return {**cat, "mcp": mcp, "craft_apps": [a for a in cat.get("craft_apps") or [] if a.lower() not in hide],
            "skills": [n for n in cat.get("skills") or [] if str(n).lower() not in hide]}


def digest(cat: dict) -> str:
    body = {k: v for k, v in cat.items() if k not in ("at", "hash")}
    body["hardware"] = {k: v for k, v in (body.get("hardware") or {}).items() if k != "disk_free_gb"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:16]


def _section(fn: Callable, default):
    try:
        got = fn()
        return default if got is None else got
    except Exception:
        return default


def gather(home=None, *, cwd=None, spawn: Optional[bool] = None, mcp_timeout: Optional[float] = None,
           mcp_probe: Optional[Callable] = None) -> dict:
    """The catalog, computed now (never raises; a section that fails is empty). `spawn` (default: not under
    BRIDGE_TEST_NO_BACKGROUND_NET) allows connecting an uncached MCP server and `--version` probes."""
    from halo_harness.config.paths import background_net_disabled
    from halo_harness.fleet import capabilities_host as host, capabilities_probe as probe, capabilities_sources as src
    from halo_harness.fleet.identity import harness
    h = _home(home)
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    spawn = (not background_net_disabled()) if spawn is None else bool(spawn)
    cfg = config(h)
    try:
        from halo_harness.providers.config import load_provider_env_files
        load_provider_env_files()  # what `halo models` reads first; a Halo session has it loaded already
    except Exception:
        pass
    mcp = _section(lambda: probe.mcp_servers(h, cwd, spawn=spawn, timeout=mcp_timeout or probe.MCP_TIMEOUT_S,
                                             probe=mcp_probe), [])
    names = [s["name"] for s in mcp if s.get("transport") != "connector"]
    me = harness(h)
    cat = {"harness": {k: me.get(k) for k in ("id", "name", "host", "os", "version")}, "at": time.time(),
           "tags": cfg["tags"], "mcp": mcp,
           "skills": _section(lambda: src.skills(cwd), []), "roles": _section(lambda: src.roles(h, cwd), []),
           "providers": _section(lambda: src.providers(h), []), "models": _section(lambda: src.models(h), []),
           "craft_apps": _section(lambda: src.craft_apps(names), []),
           "media": _section(lambda: src.media(h, names), {"comfyui": False, "models": []}),
           "hardware": _section(lambda: host.hardware(h, spawn=spawn), {}),
           "clis": _section(lambda: host.clis(spawn=spawn), {}),
           "projects": _section(lambda: src.projects(h, cwd), []),
           "integrations": _section(lambda: src.integrations(h), {})}
    from halo_harness.config.paths import home as user_home
    homes = tuple(sorted({str(user_home()), str(h), str(cwd)}, key=len, reverse=True))
    cat = scrub(apply_hide(cat, cfg["hide"]), homes)
    cat["hash"] = digest(cat)
    return cat


def load(home=None) -> Optional[dict]:
    """The cached catalog (re-read only when the file changed: a relay asks every announce)."""
    path = cache_path(home)
    try:
        mt = path.stat().st_mtime_ns
        hit = _loaded.get(str(path))
        if hit is not None and hit[0] == mt:
            return hit[1]
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    data = data if isinstance(data, dict) and data.get("hash") else None
    _loaded[str(path)] = (mt, data)
    return data


def save(cat: dict, home=None) -> None:
    from halo_harness.privateio import write_private_atomic
    path = cache_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_private_atomic(path, json.dumps(cat, indent=1, ensure_ascii=False))


def stale(cat: Optional[dict], now: Optional[float] = None) -> bool:
    if not cat:
        return True
    at = cat.get("at")
    return not isinstance(at, (int, float)) or (now or time.time()) - at > STALE_S


def refresh(home=None, **kw) -> "tuple[dict, bool]":
    """Gather now and cache it: `(catalog, changed)` (changed: the hash differs from the cached one)."""
    before = load(home)
    cat = gather(home, **kw)
    save(cat, home)
    return cat, (before or {}).get("hash") != cat["hash"]


def current(home=None, *, refresh_now: bool = False, **kw) -> dict:
    """The cached catalog, gathered afresh when missing, older than STALE_S or `refresh_now`."""
    cat = load(home)
    if refresh_now or stale(cat):
        cat, _changed = refresh(home, **kw)
    return cat


def refresh_in_background(home=None, on_done: Optional[Callable] = None) -> bool:
    """One gather at a time per home on a daemon thread; `on_done(catalog, changed)` after. False: one runs."""
    key = str(_home(home))
    with _bg_lock:
        t = _bg.get(key)
        if t is not None and t.is_alive():
            return False

        def run() -> None:
            try:
                cat, changed = refresh(home)
            except Exception:
                return
            if on_done is not None:
                try:
                    on_done(cat, changed)
                except Exception:
                    pass
        t = _bg[key] = threading.Thread(target=run, daemon=True, name="halo-capabilities")
        t.start()
        return True


def invalidate(home=None) -> None:
    """`halo mcp add/remove`: the next announce or read gathers afresh."""
    cat = load(home)
    if cat:
        try:
            save({**cat, "at": 0}, home)
        except OSError:
            pass


def announce_fields(home=None, on_change: Optional[Callable] = None) -> dict:
    """`{capabilities_summary, capabilities_hash}` for a relay's announce, from the cache only; a missing or
    stale cache starts a background gather (`on_change()` when its hash moved) and never waits for it."""
    cat = load(home)
    if stale(cat):
        refresh_in_background(home, (lambda c, changed: on_change() if changed else None) if on_change else None)
    if not cat:
        return {}
    return {"capabilities_summary": summary(cat), "capabilities_hash": cat.get("hash")}


from halo_harness.fleet.capabilities_view import chips, summary  # noqa: E402,F401  (the one-line forms)
