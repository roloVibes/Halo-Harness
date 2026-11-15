"""halo_harness.providers.local_view_cache -- Studio's local models view, read once and shared (Halo 3.6.0.0 R14).

`build_local_view` (providers/local_models.py) asks every Ollama host for its version, catalog and loaded models,
probes the local server ports and reads the GPU: a second or more per host, and on Windows about a second for each
closed loopback port. Studio's model picker read it on every `GET /api/models`, `models/best-for`,
`models/fallback` and `models/status` -- Session waited 5.6 s on a fresh Windows home, and a page that asks three of
them at once ran three builds.

    view(env, state_dir) -> rows    the shared view: one build for every caller at once; for FRESH_S seconds the
                                    same answer; after that the last answer at once while one build in the
                                    background reads the hosts again (the next read has it)
    forget()                        the next read builds again (an explicit refresh, a host added, a test's reset);
                                    a build already under way when forget() ran never stores its answer, and no
                                    read waits on it (3.6.0.0 fix pass: a generation counter)

A stale answer is served at once only while it is younger than 2 x FRESH_S; an older one (the first read after a
long idle) is built again before it is shown.

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
_gen = 0               # forget() moves it on: a build of an older generation stores nothing


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
    global _gen
    with _lock:
        _gen += 1
        _views.clear()
        _building.clear()  # a read after this builds anew; the old flight's waiters find no view and build too


def _stale_max_s() -> float:
    return 2 * FRESH_S


def _build(k, env, state_dir, flight, gen) -> list:
    from halo_harness.providers.local_models import build_local_view
    try:
        rows = build_local_view(env=env, state_dir=state_dir)
        with _lock:
            if gen == _gen:  # forget() ran meanwhile: this answer is from before the change, keep it out
                if len(_views) > 16:
                    _views.clear()
                _views[k] = (time.monotonic(), rows)
        return rows
    finally:
        with _lock:
            if _building.get(k) is flight:
                _building.pop(k, None)
        flight.set()


def view(env, state_dir) -> list:
    k = key(env, state_dir)
    while True:
        with _lock:
            hit = _views.get(k)
            flight = _building.get(k)
            gen = _gen
            age = time.monotonic() - hit[0] if hit is not None else 0.0
            if hit is not None and age < FRESH_S:
                return list(hit[1])
            if hit is not None and age >= _stale_max_s():  # too old to show even once: built before the answer
                hit = None
            if flight is None:
                flight = _building[k] = threading.Event()
                if hit is not None:  # stale: this answer now, the hosts read again behind it
                    threading.Thread(target=_build, args=(k, env, state_dir, flight, gen), name="halo-local-view",
                                     daemon=True).start()
                    return list(hit[1])
                break
            if hit is not None:  # stale and a build is under way: the last answer
                return list(hit[1])
        flight.wait(120)
        with _lock:
            hit = _views.get(k)
        if hit is not None and time.monotonic() - hit[0] < _stale_max_s():
            return list(hit[1])
    return list(_build(k, env, state_dir, flight, gen))
