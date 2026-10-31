"""halo_harness.ollama_steward.profiles_role -- a lane's own steward profile (Halo 3.3.7.0 R3; profiles.py has the
store): `ollama.profiles["<host>|<model>|<role>"]` carries one lane's window, keep_alive, tools_max or host_for.

    split_role(key) -> (host, model, role | None)     a two- or three-part key
    lane(role)      `with lane(role):` -- profile lookups on this thread read the lane's key first (agent/loop.py)
    current_lane() -> the thread's lane | None
    resolve(every, host_name, model, role=None) -> the profile: the lane's fields over `<host>|<model>`'s, with
        `role` set when the lane's key exists; `role` defaults to the thread's lane; "main" is no lane

profiles.lookup / key_for / split_key read through here; profiles.py re-exports these names.
"""

from __future__ import annotations

import threading
from typing import Optional

_LANE = threading.local()


def split_role(key: str) -> "tuple[str, str, Optional[str]]":
    host, _, rest = str(key).partition("|")
    model, _, role = rest.partition("|")
    return host, model, role or None


class lane:
    """`with lane(role):` -- profile lookups on this thread read `<host>|<model>|<role>` first."""

    def __init__(self, role: Optional[str]) -> None:
        self.role = role if isinstance(role, str) and role and role != "main" else None

    def __enter__(self):
        self._was = getattr(_LANE, "role", None)
        _LANE.role = self.role
        return self

    def __exit__(self, *exc):
        _LANE.role = self._was


def current_lane() -> Optional[str]:
    return getattr(_LANE, "role", None)


def resolve(every: dict, host_name: str, model, role: Optional[str] = None) -> Optional[dict]:
    from halo_harness.ollama_steward.profiles import key_for
    base = every.get(key_for(host_name, model))
    role = role if role is not None else current_lane()
    mine = every.get(key_for(host_name, model, role)) if role and role != "main" else None
    if mine is None:
        return base
    return {**(base or {}), **mine, "role": role}
