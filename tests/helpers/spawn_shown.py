"""What an assertion message may show of a spawn's keyword arguments.

A failing check prints its message into a local log. The keyword arguments of a spawn carry the whole environment
(every token and key of the developer's shell), so a message shows the creation flags, the session switch and the
names of the other arguments, and of an environment only its key names, never a value.
"""
from __future__ import annotations

from collections.abc import Mapping


def env_keys(env) -> list:
    """The key names of an environment mapping (never its values)."""
    return sorted(str(k) for k in env) if isinstance(env, Mapping) else []


def kw_shown(kw) -> dict:
    """A spawn's keyword arguments as a message may print them."""
    if not isinstance(kw, Mapping):
        return {"type": type(kw).__name__}
    shown: dict = {"args": sorted(str(k) for k in kw)}
    if "creationflags" in kw:
        try:
            shown["creationflags"] = hex(int(kw.get("creationflags") or 0))
        except (TypeError, ValueError):
            shown["creationflags"] = "?"
    if "start_new_session" in kw:
        shown["start_new_session"] = bool(kw.get("start_new_session"))
    if "keep" in kw:
        shown["keep"] = kw.get("keep")
    for name, value in kw.items():
        if str(name).endswith("env") and isinstance(value, Mapping):
            shown[f"{name} keys"] = env_keys(value)
    return shown


def env_values_hidden(d) -> dict:
    """A copy of a mapping (an update plan, say) where every environment mapping in it is its key names."""
    if not isinstance(d, Mapping):
        return d
    return {k: (env_keys(v) if str(k).endswith("env") and isinstance(v, Mapping) else v) for k, v in d.items()}


def spawns_shown(spawns) -> list:
    """A list of recorded (argv, kwargs) spawns: the argv as it was, the kwargs through kw_shown."""
    return [(argv, kw_shown(kw)) for argv, kw in spawns]
