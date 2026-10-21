"""halo_harness.fleet.agent_tokens -- each agent's own tokens in and out,
read from its transcript (Halo 3.1.5.0 R3, for Studio's Session Cost
panel).

An agent row (agent/agent_registry.py) carries its cost and turns, and
since 3.1.8.0 R6 its own meter's tokens from each `message_end` (a row that
carries them is kept as it is: the meter counts a resumed agent's current
invocation only). A row without them (before its first model call, a row from
an older harness) is read here. Every model call appends a `usage` node to the agent's own log
(agent/log.py `append_usage`): its sum is the agent's tokens, counted the way
the session's own meter counts them (`input_tokens` in, `output_tokens` out).
A sub-agent's rolled-up total on its PARENT's log is tagged `agent_id` and is
not the parent's own, so it is skipped. The read is incremental: each
transcript is read from where the last read stopped (its offset and running
totals are kept per path), so a snapshot every second costs only the lines
written since; a file that shrank is read again from the start.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Optional

MAX_READ = 4 * 1024 * 1024  # per call: a huge backlog is caught up over a few snapshots
_lock = threading.Lock()
_seen: dict = {}  # path -> (offset, tokens_in, tokens_out, the incomplete last line)


def totals(path) -> Optional[tuple]:
    """(tokens_in, tokens_out) of the transcript at `path`, or None without one."""
    if not path:
        return None
    path = str(path)
    try:
        size = os.stat(path).st_size
    except OSError:
        return None
    with _lock:
        off, tin, tout, rest = _seen.get(path, (0, 0, 0, b""))
        if size < off:
            off, tin, tout, rest = 0, 0, 0, b""
        if size > off:
            try:
                with open(path, "rb") as f:
                    f.seek(off)
                    chunk = f.read(min(size - off, MAX_READ))
            except OSError:
                return (tin, tout) if off else None
            off += len(chunk)
            lines = (rest + chunk).split(b"\n")
            rest = lines.pop()
            for raw in lines:
                got = _usage(raw)
                if got:
                    tin += got[0]
                    tout += got[1]
        _seen[path] = (off, tin, tout, rest)
        return tin, tout


def _usage(raw: bytes) -> Optional[tuple]:
    if b'"usage"' not in raw:
        return None
    try:
        node = json.loads(raw.decode("utf-8", errors="replace"))
    except ValueError:
        return None
    if not isinstance(node, dict) or node.get("type") != "usage" or node.get("agent_id"):
        return None
    usage = node.get("usage") if isinstance(node.get("usage"), dict) else {}
    tin, tout = usage.get("input_tokens"), usage.get("output_tokens")
    return (tin if isinstance(tin, int) else 0, tout if isinstance(tout, int) else 0)


def _carries(a: dict) -> bool:
    return all(isinstance(a.get(k), int) and not isinstance(a.get(k), bool) for k in ("tokens_in", "tokens_out"))


def with_tokens(agents: list) -> list:
    """The agent rows, each with `tokens_in` / `tokens_out` from its transcript when the row has none
    (3.1.8.0 R6: a live row carries its meter's own from `message_end`; None until its first call)."""
    for a in agents:
        if not isinstance(a, dict) or _carries(a):
            continue
        got = totals(a.get("transcript"))
        if got is not None:
            a["tokens_in"], a["tokens_out"] = got
    return agents


def forget() -> None:
    with _lock:
        _seen.clear()
