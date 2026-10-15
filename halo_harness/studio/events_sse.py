"""halo_harness.studio.events_sse -- `GET /api/events`, Studio's live feed as
Server-Sent Events (Halo 3.0.3.0 round R3; moved out of studio/events.py in
3.0.5.0 R4, which re-exports `serve_sse`). The token comes in the query (an
EventSource cannot send headers), compared with `hmac.compare_digest`;
loopback, Host and Origin checks as every API call.
"""

from __future__ import annotations

import hmac
import json
import time
from urllib.parse import parse_qs, urlsplit

PING_S = 15.0


def _frame_bytes(frame: dict) -> bytes:
    kind = str(frame.get("event") or "message").replace("\n", " ").replace("\r", " ")
    data = json.dumps(frame, ensure_ascii=False, default=str)
    return f"event: {kind}\ndata: {data}\n\n".encode("utf-8", "replace")


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
        while not q.closed and not bridge.closed:
            frame = q.get(max(0.05, min(1.0, next_ping - time.monotonic())))
            if frame is not None:
                handler.wfile.write(_frame_bytes(frame))
            elif time.monotonic() >= next_ping:
                handler.wfile.write(b": ping\n\n")
            else:
                continue
            handler.wfile.flush()
            next_ping = time.monotonic() + PING_S
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
        pass
    finally:
        bridge.unsubscribe(q)
