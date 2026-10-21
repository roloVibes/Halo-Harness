"""halo_harness.packs.registry -- the packs that run here (Halo 3.2.0.0 R1).

`snapshot(cwd=..., state_dir=...)` is one read of everything: the packs on
disk (packs/discover.py), state.json (packs/state.py), which are enabled for
their own folder, and `resolve` over them. `active(...)` is the packs that
run, in order: discovered, enabled and with no problem. A disabled pack, or
one with a problem, contributes nothing.

Every bio and lineup lookup reads this (the pack tier of
`agent_search_dirs` / `team_search_dirs`), so the snapshot is cached by what
it depends on (each packs folder, each pack.yaml and state.json: mtime and
size); every write Halo makes calls `invalidate()`. A home with no packs
folder costs two `stat` calls.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

_lock = threading.Lock()
_cache: dict = {}


@dataclass
class Snapshot:
    packs: list = field(default_factory=list)       # every discovered Pack
    state: dict = field(default_factory=dict)       # state.json
    enabled: list = field(default_factory=list)     # ids enabled for their own folder
    order: list = field(default_factory=list)       # ids that run, dependencies first
    problems: dict = field(default_factory=dict)    # id -> lines (resolve's)

    def pack(self, pack_id: str):
        return next((p for p in self.packs if p.id == pack_id), None)

    @property
    def active(self) -> list:
        return [self.pack(pid) for pid in self.order]


def invalidate() -> None:
    with _lock:
        _cache.clear()


def _key(cwd, state_dir) -> tuple:
    from halo_harness.packs import discover as D
    from halo_harness.packs import state as S
    base = (str(D.project_packs_dir(cwd)), str(D.user_packs_dir(state_dir)))
    return base + (D.signature(cwd=cwd, state_dir=state_dir), S.signature(state_dir))


def _build(cwd, state_dir) -> Snapshot:
    from halo_harness.packs import discover as D
    from halo_harness.packs import state as S
    from halo_harness.packs.resolve import resolve
    packs = D.discover(cwd=cwd, state_dir=state_dir)
    data = S.load(state_dir)
    enabled = [p.id for p in packs if S.enabled_for(p, data)]
    order, problems = resolve(packs, enabled=enabled) if enabled else ([], {})
    return Snapshot(packs=packs, state=data, enabled=enabled, order=order, problems=problems)


def snapshot(*, cwd=None, state_dir=None) -> Snapshot:
    from halo_harness.packs import discover as D
    if not D.project_packs_dir(cwd).is_dir() and not D.user_packs_dir(state_dir).is_dir():
        return Snapshot()
    key = _key(cwd, state_dir)
    with _lock:
        hit = _cache.get(key)
    if hit is not None:
        return hit
    snap = _build(cwd, state_dir)
    with _lock:
        if len(_cache) > 32:
            _cache.clear()
        _cache[key] = snap
    return snap


def active(*, cwd=None, state_dir=None) -> list:
    """The packs that run here, dependencies first."""
    return snapshot(cwd=cwd, state_dir=state_dir).active


def active_roots(*, cwd=None, state_dir=None) -> "list[Path]":
    return [p.root for p in active(cwd=cwd, state_dir=state_dir)]
