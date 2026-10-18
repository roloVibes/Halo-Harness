"""halo_harness.studio.events -- Studio's live feed (Halo 3.0.3.0 round R3).

`EventBridge` watches the live-session registry (`~/.halo/run/sessions.json`,
`remote/registry.py`) every `poll_s` seconds and attaches one daemon thread
per live session: a `remote.client.ControlClient` (1 s timeout on every call)
that sends `subscribe` and then reads `next_event`. Each frame becomes
`{session_id, harness, event, data, turn, agent_id, ts}` (kinds: feed_kinds.py) and is copied into every
browser's bounded queue (512 frames, the oldest dropped first). Attaching and
detaching a session publish a `sessions` frame (`harness`: this harness's id, 3.0.5.0 R2)
with the public fields of every attached session (never an endpoint or token). A pump that
errors detaches and is not retried for `RETRY_S`. `publish_local` adds a
frame made in this process (the Orchestra runner: `orchestra:<run id>`).
`serve_sse(handler)` (studio/events_sse.py) is `GET /api/events?t=<token>&sessions=all|<sid>`.
`taps` (3.0.5.0 R4) see every published frame, browsers or not (the fleet watcher).
"""

from __future__ import annotations

import collections
import threading
import time
from typing import Optional

from halo_harness.studio.feed_kinds import DEFAULT_KINDS, PUBLIC_FIELDS, local_harness_id  # noqa: F401  (re-exported)

QUEUE_MAX = 512
RETRY_S = 10.0
CALL_TIMEOUT_S = 1.0


class BrowserQueue:
    """One EventSource's frames: bounded, the oldest dropped when full."""

    def __init__(self, sessions: str = "all", maxlen: int = QUEUE_MAX):
        self.sessions = sessions or "all"
        self._q: "collections.deque" = collections.deque(maxlen=maxlen)
        self._cv = threading.Condition()
        self.closed = False
        self.dropped = 0

    def wants(self, frame: dict) -> bool:
        return self.sessions == "all" or frame.get("event") == "sessions" or frame.get("session_id") == self.sessions

    def put(self, frame: dict) -> None:
        with self._cv:
            if len(self._q) == self._q.maxlen:
                self.dropped += 1
            self._q.append(frame)
            self._cv.notify()

    def get(self, timeout: float) -> Optional[dict]:
        with self._cv:
            if not self._q and not self.closed:
                self._cv.wait(timeout)
            return self._q.popleft() if self._q else None

    def close(self) -> None:
        with self._cv:
            self.closed = True
            self._cv.notify_all()


class EventBridge:
    def __init__(self, *, poll_s: float = 2.0, kinds=DEFAULT_KINDS, list_live=None, harness_id=None):
        self.poll_s, self.kinds = poll_s, (list(kinds) if kinds else None)
        self.harness_id = harness_id  # the `sessions` frame's harness (None: this home's fleet-id)
        self._list_live = list_live
        self._lock = threading.Lock()
        self._clients: "list[BrowserQueue]" = []
        self._attached: "dict[str, dict]" = {}
        self._stops: "dict[str, threading.Event]" = {}
        self._cooldown: "dict[str, float]" = {}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.taps: list = []  # 3.0.5.0 R4: callables that see every frame (the fleet watcher); each must not block

    # -- browsers ---------------------------------------------------------------
    def subscribe(self, sessions: str = "all") -> BrowserQueue:
        q = BrowserQueue(sessions)
        with self._lock:
            self._clients.append(q)
            q.put(self._sessions_frame())
        self.start()
        return q

    def unsubscribe(self, q: BrowserQueue) -> None:
        q.close()
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)

    def listeners(self) -> int:
        """How many browsers (EventSources) are open right now (3.1.1.0 R3: `halo studio --edit` focuses one)."""
        with self._lock:
            return sum(1 for q in self._clients if not q.closed)

    def publish(self, frame: dict) -> None:
        for tap in list(self.taps):
            try:
                tap(frame)
            except Exception:
                pass
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            if q.wants(frame):
                q.put(frame)

    def publish_local(self, frame: dict) -> None:
        """A frame from this process, not a session's socket: completed to the usual shape."""
        self.publish({"session_id": None, "event": "message", "data": None, "turn": None, "agent_id": None,
                      "ts": time.time(), **frame})

    # -- sessions ---------------------------------------------------------------
    def start(self) -> "EventBridge":
        with self._lock:
            if self._thread is None and not self._stop.is_set():
                self._thread = threading.Thread(target=self._watch, name="halo-studio-events", daemon=True)
                self._thread.start()
        return self

    def close(self) -> None:
        self._stop.set()
        with self._lock:
            clients, self._clients = self._clients, []
            stops = list(self._stops.values())
        for ev in stops:
            ev.set()
        for q in clients:
            q.close()

    closed = property(lambda self: self._stop.is_set())

    def _watch(self) -> None:
        while not self._stop.is_set():
            self.scan()
            self._stop.wait(self.poll_s)

    def scan(self) -> None:
        try:
            if self._list_live is not None:
                rows = self._list_live()
            else:
                from halo_harness.remote import registry
                rows = registry.list_live()
        except Exception:
            return
        live = {r.get("session_id"): r for r in rows if isinstance(r, dict) and r.get("session_id")}
        now = time.monotonic()
        with self._lock:
            gone = [sid for sid in self._stops if sid not in live]
            new = [r for sid, r in live.items() if sid not in self._stops and self._cooldown.get(sid, 0) <= now]
        for sid in gone:
            self._stops[sid].set()
        for entry in new:
            self._attach(entry)

    def _attach(self, entry: dict) -> None:
        sid = entry["session_id"]
        stop = threading.Event()
        with self._lock:
            if sid in self._stops or self._stop.is_set():
                return
            self._stops[sid] = stop
        threading.Thread(target=self._pump, args=(entry, stop), name=f"halo-studio-pump-{sid[:8]}", daemon=True).start()

    def _pump(self, entry: dict, stop: threading.Event) -> None:
        from halo_harness.remote.client import ControlClient, default_token_for
        sid = entry["session_id"]
        client = None
        try:
            client = ControlClient(str(entry.get("endpoint") or ""), default_token_for(entry), timeout=CALL_TIMEOUT_S)
            resp = client.call("subscribe", kinds=self.kinds) if self.kinds else client.call("subscribe")
            if not resp.get("ok"):
                return
            with self._lock:
                self._attached[sid] = {k: entry.get(k) for k in PUBLIC_FIELDS}
            self.publish(self._sessions_frame(attached=sid))
            while not stop.is_set() and not self._stop.is_set():
                ev = client.next_event(CALL_TIMEOUT_S)
                if ev is not None:
                    self.publish({"session_id": sid, "harness": ev.get("harness"), "event": ev.get("event"),
                                  "data": ev.get("data"), "turn": ev.get("turn"), "agent_id": ev.get("agent_id"),
                                  "ts": ev.get("ts") or time.time()})
        except Exception:  # a dead or closed socket: detach (and cool down, below)
            pass
        finally:
            if client is not None:
                client.close()
            with self._lock:
                self._stops.pop(sid, None)
                was = self._attached.pop(sid, None)
                if not stop.is_set():  # an error, not a registry removal: wait before trying again
                    self._cooldown[sid] = time.monotonic() + RETRY_S
            if was is not None and not self._stop.is_set():
                self.publish(self._sessions_frame(detached=sid))

    def _sessions_frame(self, **extra) -> dict:
        rows = sorted(list(self._attached.values()), key=lambda r: (r.get("started") or 0, r.get("session_id") or ""))
        return {"session_id": None, "event": "sessions", "data": {"sessions": rows, **extra},
                "turn": None, "agent_id": None, "ts": time.time(), "harness": self.harness_id or local_harness_id()}


def bridge_for(server) -> EventBridge:
    """The server's one bridge, made on the first EventSource (or the fleet watcher's first tick); the
    server's `event_taps` (3.0.5.0 R4: studio/fleet_watch.py) are attached to it."""
    with server.events_lock:
        if server.events is None:
            server.events = EventBridge()
        for tap in getattr(server, "event_taps", None) or []:
            if tap not in server.events.taps:
                server.events.taps.append(tap)
        return server.events


from halo_harness.studio.events_sse import _frame_bytes, serve_sse  # noqa: E402,F401  (the SSE route, re-exported)


