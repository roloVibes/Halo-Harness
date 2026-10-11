"""halo_harness.remote.feed -- the event fan-out behind the control socket's
`subscribe` feed (Halo 2.0.9 round 2).

An `EventHub` is fed by a TEE on the session's event emit (see
`Controller.add_event_tap` and `headless.run_print_mode`'s wrapped turn
stream): the TUI's own drain loop stays the single reader of
`Controller.events`, the hub only ever receives a copy.

What a subscriber sees:

* `text_delta` events are buffered into one `text_chunk` frame per
  `TEXT_FLUSH_S` seconds or `TEXT_FLUSH_BYTES` bytes (whichever comes
  first), flushed early whenever any other kind arrives so ordering holds;
* `thinking_delta` is not forwarded (a raw per-token stream, never useful
  at a phone's pace);
* every other kind in `events.EVENT_KINDS` is forwarded as-is.

Frames are plain dicts: `{"event": kind, "data": {...}, "turn", "agent_id",
"ts"}`. A subscriber owns a bounded queue; when it fills the subscriber is
dropped (closed), the session is never blocked.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Iterable, Optional

TEXT_FLUSH_S = 2.0
TEXT_FLUSH_BYTES = 1800
SUBSCRIBER_QUEUE = 256
NOT_FORWARDED = frozenset({"thinking_delta"})


def event_frame(ev) -> dict:
    return {"event": ev.kind, "data": ev.data, "turn": ev.turn, "agent_id": ev.agent_id, "ts": ev.ts}


class Subscription:
    """One consumer of the feed. `offer` never blocks; a full queue marks the
    subscription `dropped` and closed."""

    def __init__(self, maxsize: int = SUBSCRIBER_QUEUE, kinds: Optional[Iterable[str]] = None):
        self._q: "queue.Queue" = queue.Queue(maxsize)
        self.kinds = frozenset(kinds) if kinds else None
        self.dropped = False
        self.closed = threading.Event()
        self.on_drop: Optional[Callable[[], None]] = None  # e.g. force-close the subscriber's socket

    def offer(self, frame: dict) -> bool:
        if self.closed.is_set():
            return False
        if self.kinds is not None and frame["event"] not in self.kinds:
            return True
        try:
            self._q.put_nowait(frame)
            return True
        except queue.Full:
            self.dropped = True
            self.closed.set()
            cb = self.on_drop
            if cb is not None:
                try:
                    cb()
                except Exception:
                    pass
            return False

    def get(self, timeout: float = 0.25) -> Optional[dict]:
        """Next frame, or None on timeout / once closed."""
        if self.closed.is_set():
            return None
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self) -> None:
        self.closed.set()


class EventHub:
    def __init__(self, *, flush_s: float = TEXT_FLUSH_S, flush_bytes: int = TEXT_FLUSH_BYTES,
                 clock: Callable[[], float] = time.monotonic):
        self.flush_s = flush_s
        self.flush_bytes = flush_bytes
        self._clock = clock
        self._lock = threading.Lock()
        self._subs: "list[Subscription]" = []
        self._observers: "list[Callable]" = []
        self._buf: "list[str]" = []
        self._buf_bytes = 0
        self._buf_t0 = 0.0
        self._buf_meta: "tuple" = (0, None)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ---- lifecycle -------------------------------------------------------

    def start(self) -> "EventHub":
        if self._thread is None:
            self._thread = threading.Thread(target=self._flush_loop, name="halo-remote-feed", daemon=True)
            self._thread.start()
        return self

    def close(self) -> None:
        self._stop.set()
        with self._lock:
            for sub in self._subs:
                sub.close()
            self._subs.clear()

    def _flush_loop(self) -> None:
        while not self._stop.wait(0.25):
            self.flush_if_due()

    # ---- subscribers / observers ----------------------------------------

    def subscribe(self, maxsize: int = SUBSCRIBER_QUEUE, kinds: Optional[Iterable[str]] = None) -> Subscription:
        sub = Subscription(maxsize, kinds)
        with self._lock:
            self._subs.append(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        sub.close()
        with self._lock:
            if sub in self._subs:
                self._subs.remove(sub)

    def add_observer(self, fn: Callable) -> None:
        """`fn(event)` runs on the publishing thread for EVERY event, before
        coalescing; it must be quick and must not raise."""
        self._observers.append(fn)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subs)

    # ---- publishing --------------------------------------------------------

    def publish(self, ev) -> None:
        for obs in tuple(self._observers):
            try:
                obs(ev)
            except Exception:
                pass
        if ev.kind in NOT_FORWARDED:
            return
        with self._lock:
            if not self._subs:
                self._buf.clear()
                self._buf_bytes = 0
                return
            if ev.kind == "text_delta":
                self._add_text(ev)
            else:
                self._flush_locked()
                self._fanout(event_frame(ev))
            self._prune()

    def publish_frame(self, frame: dict) -> None:
        """A synthesized frame (not an `Event`): flushes pending text first."""
        with self._lock:
            self._flush_locked()
            self._fanout(frame)
            self._prune()

    def _add_text(self, ev) -> None:
        text = ev.data.get("text", "") if isinstance(ev.data, dict) else ""
        meta = (ev.turn, ev.agent_id)
        if self._buf and meta != self._buf_meta:
            self._flush_locked()
        if not self._buf:
            self._buf_t0 = self._clock()
            self._buf_meta = meta
        self._buf.append(text)
        self._buf_bytes += len(text.encode("utf-8", "replace"))
        if self._buf_bytes >= self.flush_bytes or (self._clock() - self._buf_t0) >= self.flush_s:
            self._flush_locked()

    def flush_if_due(self) -> None:
        with self._lock:
            if self._buf and (self._clock() - self._buf_t0) >= self.flush_s:
                self._flush_locked()
                self._prune()

    def flush_now(self) -> None:
        with self._lock:
            self._flush_locked()
            self._prune()

    def _flush_locked(self) -> None:
        if not self._buf:
            return
        text = "".join(self._buf)
        turn, agent_id = self._buf_meta
        self._buf.clear()
        self._buf_bytes = 0
        if text:
            self._fanout({"event": "text_chunk", "data": {"text": text}, "turn": turn,
                           "agent_id": agent_id, "ts": time.time()})

    def _fanout(self, frame: dict) -> None:
        for sub in self._subs:
            sub.offer(frame)

    def _prune(self) -> None:
        self._subs[:] = [s for s in self._subs if not s.closed.is_set()]
