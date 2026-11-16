"""The facts of a session's map, in one place (3.6.0.2 "Session map", R40 with R21 R24 R41).

F1 started: when this session started on its map (`map_start`'s `t`, kept on the session as `_map_started_at`).
F2 running: the map it runs on (`team_control.map`), and whether that is the default (`compile.is_default`).
F4 new sessions: config `crew.map` (None when unset), and since when: config `crew.map_since {map, at}`, written in the
   same write as `crew.map` (theme.set_config_value, changes_map.config_text); valid only while its `map` equals
   `crew.map` -- else the map was set outside Halo and when is not known (T11): None.
F5 changes: the last `builder_done` outcome of the session (`_builder_built`, crew/map_events.py), no map bodies.

S13 and its terminal tail are the sentence every place says (the Builder card's use row, the result tail main repeats,
the facts note); Studio's twin is `truth.ts`. Times are `%H:%M` (R41: never `%-H`/`%-I`, which raise on Windows).
Nothing here calls a model, writes a file or reads the disk beyond config through the theme's stat-keyed cache.
"""
from __future__ import annotations

import time

S13 = "This session keeps running on {old}, as it started. Start a new session to run on {new}."
TERMINAL_TAIL = "In the terminal: quit and run halo again; /clear keeps {old}."
DEFAULT_WORDS = "{name} (the default)"


def s13(old: str, new: str) -> str:
    return S13.format(old=old, new=new)


def terminal_tail(old: str) -> str:
    return TERMINAL_TAIL.format(old=old)


def hhmm(t) -> str:
    """A time as the person reads it: `%H:%M`, local."""
    return time.strftime("%H:%M", time.localtime(float(t)))


def words_of(name, plain: bool = False) -> str:
    """{A}/{B}/{old}/{new}: "starter (the default)" for the default map (or no map named: new sessions draw the
    default), else the map's name."""
    if plain or not name:
        from halo_harness.crew.compile import DEFAULT_MAP
        return DEFAULT_WORDS.format(name=name or DEFAULT_MAP)
    return str(name)


def _name(v):
    return v.strip() if isinstance(v, str) and v.strip() else None


def since_for(crew_before, value) -> dict:
    """The `crew.map_since` to write with `crew.map` = value: the one already there when it names the same map and the
    map does not change (choosing the map in use again is no switch), else `{map: value, at: now}`."""
    crew_before = crew_before if isinstance(crew_before, dict) else {}
    old = crew_before.get("map_since")
    if (_name(crew_before.get("map")) == _name(value) and isinstance(old, dict)
            and _name(old.get("map")) == _name(value) and _num(old.get("at")) is not None):
        return dict(old)
    return {"map": _name(value), "at": round(time.time(), 3)}


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _crew_config() -> dict:
    """config's `crew` section, read through the theme's stat-keyed cache (never a file opened here)."""
    try:
        from halo_harness.theme import get_config_value
        crew = get_config_value("crew", default=None)
    except Exception:
        return {}
    return crew if isinstance(crew, dict) else {}


def next_map() -> "tuple":
    """F4: (the map new sessions use or None, since when or None). One read of config's `crew` section."""
    crew = _crew_config()
    name = _name(crew.get("map"))
    since = crew.get("map_since")
    at = None
    if isinstance(since, dict) and _name(since.get("map")) == name:
        at = _num(since.get("at"))
    return name, at


def facts(session) -> dict:
    """F1, F2, F4, F5 of `session`: {map, words, plain, since, next, next_words, next_since, built, asked}."""
    tc = getattr(session, "team_control", None)
    on_map = bool(getattr(tc, "is_map", False))
    name = (getattr(tc, "map_name", None) or None) if on_map else None
    plain = False
    if on_map:
        try:
            from halo_harness.crew.compile import is_default
            plain = bool(is_default(getattr(tc, "map", None)))
        except Exception:
            plain = False
    nxt, nxt_at = next_map()
    built = getattr(session, "_builder_built", None)
    built = {k: v for k, v in built.items() if k != "maps"} if isinstance(built, dict) else None
    return {"map": name, "words": words_of(name, plain) if name else None, "plain": plain,
            "since": _num(getattr(session, "_map_started_at", None)), "next": nxt,
            "next_words": words_of(nxt, nxt is None), "next_since": nxt_at, "built": built,
            "asked": bool(getattr(session, "_map_asked", False) or getattr(session, "turn_count", 0))}


def row(session) -> dict:
    """The status row's map facts (R40): map_since, map_plain, map_next, map_next_since, built, asked. Never raises."""
    try:
        f = facts(session)
    except Exception:
        return {}
    return {"map_since": f["since"], "map_plain": f["plain"], "map_next": f["next"], "map_next_since": f["next_since"],
            "built": f["built"], "asked": f["asked"]}
