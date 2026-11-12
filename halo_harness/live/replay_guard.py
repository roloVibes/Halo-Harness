"""halo_harness.live.replay_guard -- a hostile `.halo-replay` file (Halo 3.4.1.2, PACKS-7): replay_file.parse reads
a file someone sent, so it refuses one nested deeper than MAX_DEPTH before json.loads recurses into it (a RecursionError
was a 500 on `POST replays/import` and a traceback in the CLI), and drops every control character from its strings
and keys (an OSC 52 clipboard write or a link spoof in a title reached the terminal through `halo replay list / open
/ compare` and `halo report`).

    _depth_ok(data) -> bool        _plain(obj) -> obj
"""

from __future__ import annotations

MAX_DEPTH = 64  # 3.4.1.2 (PACKS-7): a replay nests a few levels; a file nested deeper is not one


def _depth_ok(data) -> bool:
    """No list or object nested more than MAX_DEPTH deep (json.loads itself raises RecursionError far deeper)."""
    stack = [(data, 1)]
    while stack:
        obj, depth = stack.pop()
        if isinstance(obj, (list, dict)):
            if depth > MAX_DEPTH:
                return False
            stack.extend((v, depth + 1) for v in (obj.values() if isinstance(obj, dict) else obj))
    return True


def _plain(obj):
    """3.4.1.2 (PACKS-7): every string and key without control characters (no terminal escape reaches a title)."""
    from halo_harness.live.replay_private import _CONTROLS
    if isinstance(obj, str):
        return _CONTROLS.sub("", obj)
    if isinstance(obj, list):
        return [_plain(v) for v in obj]
    if isinstance(obj, dict):
        return {(_plain(k) if isinstance(k, str) else k): _plain(v) for k, v in obj.items()}
    return obj
