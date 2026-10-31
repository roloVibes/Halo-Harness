"""halo_harness.host.stream -- the host's `GET stream` (server-sent events; Halo 3.3.7.0 R1, moved out of host/http.py in
R2 for the 250-line cap). Frames:

    card        on open and every STREAM_CARD_S (60 s)
    event       a new classified server event (events.jsonl), and R2's own: a fix landed, its verdict, a load,
                an unload, a delete (host/jobs.Bus `event` frames)
    resources   a new resources sample per served host
    job         R2: a job's progress (rerun_battery, bench, verify_twin, pull)
    note        R2: a new note in the host's steward notes (the duty steward's pass)
    : ping      every PING_S
"""

from __future__ import annotations

import json
import time

STREAM_EVENT_S, STREAM_RES_S, STREAM_CARD_S, STREAM_BUS_S = 2.0, 5.0, 60.0, 0.5


def frame(handler, kind: str, data) -> None:
    doc = json.dumps({"type": kind, "ts": time.time(), "data": data}, ensure_ascii=False, default=str)
    handler.wfile.write(f"event: {kind}\ndata: {doc}\n\n".encode("utf-8"))
    handler.wfile.flush()


def _notes_size(home) -> int:
    from halo_harness.ollama_steward.steward import journal_path
    try:
        p = journal_path(home)
        return p.stat().st_size if p.exists() else 0
    except Exception:
        return 0


def _new_notes(home, since: float) -> list:
    """The steward notes (steward.jsonl's `note` lines) written after `since`, each with its time as `t`."""
    from halo_harness.ollama_steward import notes
    from halo_harness.ollama_steward.ledger import parse_at
    try:
        rows = [{**r, "t": parse_at(r.get("at")) or 0} for r in notes.read(home, since_s=3600)]
    except Exception:
        return []
    return [r for r in rows if r["t"] > since]


def serve(handler) -> None:
    from halo_harness.fleet import protocol
    from halo_harness.host.jobs import of
    from halo_harness.ollama_steward.resources import STORE
    from halo_harness.ollama_steward.server_events import events_path
    svc = handler.svc
    handler.close_connection = True
    handler.send_response(200)
    for k, v in (("Content-Type", "text/event-stream; charset=utf-8"), ("Cache-Control", "no-store"),
                 ("Connection", "close"), ("X-Accel-Buffering", "no")):
        handler.send_header(k, v)
    handler.end_headers()
    handler._status = 200
    view, names, bus = svc.view, [h.name for h in svc.view.hosts()], of(svc).bus
    path = events_path(svc.home)
    size, nsize, note_t, seq = (path.stat().st_size if path.exists() else 0), _notes_size(svc.home), time.time(), bus.last_seq()
    frame(handler, "card", view.card())
    now = time.monotonic()
    nxt = {"event": now + STREAM_EVENT_S, "res": now, "card": now + STREAM_CARD_S, "ping": now + protocol.PING_S}
    seen_t: dict = {}
    while not svc.stopping.is_set():
        now = time.monotonic()
        for f in bus.since(seq):
            seq = f["seq"]
            frame(handler, f["type"], f["data"])
        if now >= nxt["event"]:
            nxt["event"] = now + STREAM_EVENT_S
            cur = path.stat().st_size if path.exists() else 0
            if cur != size:
                size = cur
                for ev in view.events(since=STREAM_EVENT_S * 3)["events"]:
                    key = (ev.get("at"), ev.get("kind"), ev.get("model"))
                    if key not in seen_t:
                        seen_t[key] = 1
                        frame(handler, "event", ev)
            ncur = _notes_size(svc.home)
            if ncur != nsize:
                nsize = ncur
                for r in _new_notes(svc.home, note_t):
                    note_t = max(note_t, float(r.get("t") or 0))
                    frame(handler, "note", {k: r.get(k) for k in ("say", "lines", "where", "at", "t", "cost")})
        if now >= nxt["res"]:
            nxt["res"] = now + STREAM_RES_S
            for n in names:
                s = STORE.latest(n)
                if s and s.get("t") != seen_t.get(("res", n)):
                    seen_t[("res", n)] = s.get("t")
                    frame(handler, "resources", s)
        if now >= nxt["card"]:
            nxt["card"] = now + STREAM_CARD_S
            frame(handler, "card", view.card())
        if now >= nxt["ping"]:
            nxt["ping"] = now + protocol.PING_S
            handler.wfile.write(b": ping\n\n")
            handler.wfile.flush()
        if len(seen_t) > 4096:
            seen_t.clear()
        svc.stopping.wait(STREAM_BUS_S / 2)
