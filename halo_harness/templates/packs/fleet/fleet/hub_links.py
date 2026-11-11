"""halo_harness.fleet.hub_links -- one member of a hub and its links (Halo
3.0.5.0 "Fleet" round R2).

A member is a paired harness (members.json). Every halo process of that
harness that has sessions runs a relay, and each relay is one `Link`: the
sessions it announced (rows with their agent trees, already scrubbed by the
member for its share level), when it was last heard from, and the queue of
signed docs its SSE stream sends down. A member is online while one of its
links streams or spoke within LINK_TTL_S.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Optional

LINK_TTL_S = 30.0
STREAM_GRACE_S = 10.0  # a link whose stream closed keeps its sessions this long (a reconnect)
QUEUE_MAX = 256


class Link:
    def __init__(self, link_id: str, hid: str) -> None:
        self.id, self.hid = link_id, hid
        self.sessions: dict = {}
        self.last_seen = time.time()
        self.queue: "queue.Queue" = queue.Queue(QUEUE_MAX)
        self.streams = 0
        self.gen = 0  # the newest stream's number: an older stream handler for this link stops
        self.closed = threading.Event()
        self._seq = 0
        self._lock = threading.Lock()

    def next_seq(self) -> int:
        with self._lock:
            self._seq += 1
            return self._seq

    def push(self, doc: dict) -> bool:
        try:
            self.queue.put_nowait(doc)
            return True
        except queue.Full:
            return False

    def alive(self, now: float) -> bool:
        return not self.closed.is_set() and (self.streams > 0 or now - self.last_seen < LINK_TTL_S)

    def close(self) -> None:
        self.closed.set()


class Member:
    def __init__(self, record: dict, key: Optional[bytes]) -> None:
        self.record = dict(record)
        self.key = key
        self.links: "dict[str, Link]" = {}
        self.harness: dict = {k: record.get(k) for k in ("id", "name", "host", "user", "version", "os")}
        self.share = record.get("share") or "events"
        self.allow_control = record.get("allow_control") or "ask"
        self.allow_answers = False
        self.online = False
        self.last_seen: Optional[float] = None
        self._costs: dict = {}  # (day, session id) -> cost so far today
        self.caps: dict = {}  # 3.0.6.0 R6: {hash, summary} from its last announce

    @property
    def id(self) -> str:
        return str(self.record.get("id"))

    @property
    def name(self) -> str:
        return str(self.harness.get("name") or self.record.get("name") or self.id[:8])

    def link(self, link_id: str) -> Link:
        lk = self.links.get(link_id)
        if lk is None or lk.closed.is_set():
            lk = self.links[link_id] = Link(link_id, self.id)
        return lk

    def link_for(self, sid: str) -> Optional[Link]:
        now = time.time()
        hits = [lk for lk in self.links.values() if sid in lk.sessions and lk.alive(now)]
        return max(hits, key=lambda lk: lk.last_seen) if hits else None

    def sessions(self) -> list:
        seen, rows = set(), []
        now = time.time()
        for lk in sorted(self.links.values(), key=lambda lk: -lk.last_seen):
            if not lk.alive(now):
                continue
            for sid, row in lk.sessions.items():
                if sid not in seen:
                    seen.add(sid)
                    rows.append(row)
        return sorted(rows, key=lambda r: (r.get("started") or 0, r.get("session_id") or ""))

    def note_costs(self, rows: list) -> None:
        day = time.strftime("%Y-%m-%d")
        for r in rows:
            cost = r.get("cost_usd")
            started = r.get("started")
            if isinstance(cost, (int, float)) and isinstance(started, (int, float)) \
                    and time.strftime("%Y-%m-%d", time.localtime(started)) == day:
                self._costs[(day, r.get("session_id"))] = float(cost)
        self._costs = {k: v for k, v in self._costs.items() if k[0] == day}

    def cost_today(self) -> float:
        day = time.strftime("%Y-%m-%d")
        return round(sum(v for (d, _sid), v in self._costs.items() if d == day), 6)

    def close(self) -> None:
        for lk in self.links.values():
            lk.close()

    def view(self, hub_version: str) -> dict:
        h = self.harness
        return {"id": self.id, "name": self.name, "host": h.get("host"), "user": h.get("user"),
                "version": h.get("version"), "os": h.get("os"), "share": self.share,
                "allow_control": self.allow_control, "allow_answers": self.allow_answers, "online": self.online,
                "last_seen": self.last_seen, "cost_today": self.cost_today(), "local": False,
                "version_mismatch": bool(h.get("version")) and h.get("version") != hub_version,
                "paired_at": self.record.get("paired_at"), "capabilities_hash": self.caps.get("hash"),
                "capabilities_summary": self.caps.get("summary"), "sessions": self.sessions()}
