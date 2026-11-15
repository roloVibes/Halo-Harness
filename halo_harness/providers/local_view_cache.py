"""halo_harness.providers.local_view_cache -- Studio's local models view, read once and shared (Halo 3.6.0.0 R14).

`build_local_view` (providers/local_models.py) asks every Ollama host for its version, catalog and loaded models,
probes the local server ports and reads the GPU: a second or more per host, and on Windows about a second for each
closed loopback port. Studio's model picker read it on every `GET /api/models`, `models/best-for`,
`models/fallback` and `models/status` -- Session waited 5.6 s on a fresh Windows home, and a page that asks three of
them at once ran three builds.

    view(env, state_dir) -> rows    the shared view: one build for every caller at once; for FRESH_S seconds the
                                    same answer; after that the last answer at once while one build in the
                                    background reads the hosts again (the next read has it)
    forget()                        the next read builds again (an explicit refresh, a host added, a test's reset)

The answer depends on what `key` names: the state dir, the configured hosts (config.json's stamp) and the env
values the view reads (OLLAMA_HOST, HF_HOME, HF_HUB_CACHE, HF_LOCAL_PROBE_PORTS); any of them changed is a new
build, never an old answer.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

FRESH_S = 20.0
_ENV_KEYS = ("OLLAMA_HOST", "HF_HOME", "HF_HUB_CACHE", "HF_LOCAL_PROBE_PORTS")
_lock = threading.Lock()
_views: dict = {}      # key -> (monotonic when built, rows)
_building: dict = {}   # key -> Event


def _stamp(path: Path):
    try:
        st = path.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def key(env, state_dir) -> tuple:
    env = env or {}
    return (str(state_dir), _stamp(Path(state_dir) / "config.json"), tuple(str(env.get(k) or "") for k in _ENV_KEYS))


def forget() -> None:
    with _lock:
        _views.clear()


def _build(k, env, state_dir, flight) -> list:
    from halo_harness.providers.local_models import build_local_view
    try:
        rows = build_local_view(env=env, state_dir=state_dir)
        with _lock:
            if len(_views) > 16:
                _views.clear()
            _views[k] = (time.monotonic(), rows)
        return rows
    finally:
        with _lock:
            _building.pop(k, None)
        flight.set()


def view(env, state_dir) -> list:
    k = key(env, state_dir)
    while True:
        with _lock:
            hit = _views.get(k)
            flight = _building.get(k)
            if hit is not None and time.monotonic() - hit[0] < FRESH_S:
                return list(hit[1])
            if flight is None:
                flight = _building[k] = threading.Event()
                if hit is not None:  # stale: this answer now, the hosts read again behind it
                    threading.Thread(target=_build, args=(k, env, state_dir, flight), name="halo-local-view",
                                     daemon=True).start()
                    return list(hit[1])
                break
            if hit is not None:  # stale and a build is under way: the last answer
                return list(hit[1])
        flight.wait(120)
        with _lock:
            hit = _views.get(k)
        if hit is not None:
            return list(hit[1])
    return list(_build(k, env, state_dir, flight))
