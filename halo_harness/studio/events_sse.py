"""halo_harness.studio.events_sse -- `GET /api/events`, Studio's live feed as
Server-Sent Events (Halo 3.0.3.0 round R3; moved out of studio/events.py in
3.0.5.0 R4, which re-exports `serve_sse`). The token comes in the query (an
EventSource cannot send headers), compared with `hmac.compare_digest`;
loopback, Host and Origin checks as every API call.
"""

from __future__ import annotations

import collections
import hmac
import json
import time
from typing import Optional
from urllib.parse import parse_qs, urlsplit

PING_S = 15.0


def _frame_bytes(frame: dict) -> bytes:
    kind = str(frame.get("event") or "message").replace("\n", " ").replace("\r", " ")
    data = json.dumps(frame, ensure_ascii=False, default=str)
    return f"event: {kind}\ndata: {data}\n\n".encode("utf-8", "replace")


def dropped_notice(q, told: int) -> "tuple[Optional[bytes], int]":
    """A `dropped` frame when `q` lost frames since `told` (3.2.1.0: the browser re-reads the fleet view then), else
    None; returns the count told so far."""
    if q.dropped <= told:
        return None, told
    frame = {"session_id": None, "event": "dropped", "data": {"n": q.dropped - told}, "turn": None, "agent_id": None,
             "ts": time.time()}
    return _frame_bytes(frame), q.dropped


def serve_sse(handler) -> None:
    """`GET /api/events`: stream the live feed to one EventSource."""
    from halo_harness.studio.events import bridge_for
    if not handler._local_only():
        return
    origin = handler.headers.get("Origin")
    if origin and origin not in handler._own_origin():
        handler._json(403, {"error": "foreign origin"})
        return
    query = {k: v[-1] for k, v in parse_qs(urlsplit(handler.path).query).items()}
    presented = query.get("t", "")
    if not presented or not hmac.compare_digest(presented, handler.server.token):
        handler._json(403, {"error": "missing or wrong studio token in ?t="})
        return
    bridge = bridge_for(handler.server)
    q = bridge.subscribe(query.get("sessions") or "all")
    handler.close_connection = True
    try:
        handler.send_response(200)
        for k, v in (("Content-Type", "text/event-stream; charset=utf-8"), ("Cache-Control", "no-store"),
                     ("X-Accel-Buffering", "no"), ("X-Content-Type-Options", "nosniff"), ("Connection", "close")):
            handler.send_header(k, v)
        handler.end_headers()
        handler.wfile.write(b"retry: 3000\n\n")
        handler.wfile.flush()
        next_ping = time.monotonic() + PING_S
        told = 0  # drops told to this browser so far
        slow = getattr(handler.server, "slow_ms", 0) / 1000  # 3.3.0.0 R7: the latency flag (server.slow_ms_from_env)
        held: collections.deque = collections.deque()  # (due, frame): each frame written `slow` s after it came
        while not q.closed and not bridge.closed:
            wait = min(1.0, next_ping - time.monotonic(), (held[0][0] - time.monotonic()) if held else 1.0)
            frame = q.get(max(0.01 if held else 0.05, wait))
            if slow and frame is not None:
                held.append((time.monotonic() + slow, frame))
            due = [frame] if not slow and frame is not None else []
            while held and held[0][0] <= time.monotonic():
                due.append(held.popleft()[1])
            if due:
                for f in due:
                    handler.wfile.write(_frame_bytes(f))
            elif time.monotonic() >= next_ping:
                handler.wfile.write(b": ping\n\n")
            else:
                continue
            notice, told = dropped_notice(q, told)  # 3.2.1.0: frames fell off the bounded queue under a flood
            if notice:
                handler.wfile.write(notice)
            handler.wfile.flush()
            next_ping = time.monotonic() + PING_S
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
        pass
    finally:
        bridge.unsubscribe(q)
