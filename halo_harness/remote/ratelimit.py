"""halo_harness.remote.ratelimit -- commands per minute per peer (config
`remote.rate_per_minute`, default 30). Over the limit the bridge drops the
command and tells the phone once per overrun (the next `allow` after the
window clears starts a fresh episode)."""

from __future__ import annotations

import time
from collections import deque
from typing import Callable

WINDOW_S = 60.0
OK, DROP, DROP_NOTIFY = "ok", "drop", "drop_notify"


class RateLimiter:
    def __init__(self, per_minute: int = 30, clock: Callable[[], float] = time.monotonic) -> None:
        self.per_minute = max(1, int(per_minute))
        self._clock = clock
        self._hits: dict = {}
        self._notified: set = set()

    def allow(self, key: str) -> str:
        now = self._clock()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= WINDOW_S:
            hits.popleft()
        if len(hits) < self.per_minute:
            hits.append(now)
            self._notified.discard(key)
            return OK
        if key in self._notified:
            return DROP
        self._notified.add(key)
        return DROP_NOTIFY
