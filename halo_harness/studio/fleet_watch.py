"""halo_harness.studio.fleet_watch -- the hub's eyes between two requests (Halo
3.0.5.0 "Fleet" round R4). One `Watcher` per Studio server (`watcher_for`),
started lazily by the first Fleet panels route or when the hub starts in
Studio, stopped by `server_close`. Every TICK_S it reads the fleet view
(`fleet_hub_api.view_for`) and:

* keeps the ask frames (permission_request, question, plan_review,
  approval_request) per (harness, session, request id), so an attention row
  and its phone card say what is asked;
* keeps who edits which file (`conflicts.Touches`, from the agents' `current`
  in the view and in `agent_state` frames) and finds the conflicts;
* journals sessions that start and end, member cost snapshots, files and
  errors (fleet/journal.py, read by the digest);
* applies the caps (fleet/caps.py): a cap reached pauses the sessions in its
  scope (`pause` with reason "cap") and raises an attention row;
* builds the attention queue (fleet/attention.py), publishes its count as a
  `fleet` frame (`action: attention`) and spools the NEW rows to the phone
  when the Signal bridge is enabled, running and paired (fleet/push.py).

It taps `EventBridge.publish` (studio/events.py `taps`): the tap only queues
the frame. Nothing here calls a model, and a request never waits on a tick
it did not ask for (`snapshot`).
"""

from __future__ import annotations

import collections
import threading
import time
from pathlib import Path

from halo_harness.fleet import attention, caps, conflicts, journal
from halo_harness.studio import fleet_watch_sources as sources
from halo_harness.studio import fleet_feed as feed
from halo_harness.studio import fleet_send as send

TICK_S = 3.0
ASK_KINDS = {"permission_request": "permission", "question": "question", "plan_review": "plan",
             "approval_request": "approval"}
_make_lock = threading.Lock()


class Watcher:
    def __init__(self, server, home) -> None:
        self.server, self.home = server, Path(home)
        self.local_id = sources.local_id(server)
        self.touches = conflicts.Touches()
        self.asks: dict = {}           # (harness, session, request id) -> {kind, data, agent_id, ts}
        self.seen: dict = {}           # attention row id -> first seen
        self.acks: set = set()         # rows set aside from Studio (journal kind ack)
        self.answered: dict = {}       # row id -> when answered (hidden until the session's status catches up)
        self.lifted: dict = {}         # cap id -> the day it was lifted
        self.cap_paused: set = set()   # (harness, session, day)
        self.cap_logged: set = set()   # (cap id, day)
        self.sessions: dict = {}       # (harness, session) -> {title, harness_name}
        self.costs: dict = {}          # (harness, session) -> (when journaled, usd)
        self.pushed: set = set()
        self.view: dict = {"harnesses": []}
        self.rows: list = []
        self.conflicts: list = []
        self.reached: list = []
        self.lock = threading.RLock()
        self._frames: "collections.deque" = collections.deque(maxlen=4000)
        self._stop = threading.Event()
        self._thread = None
        self._last = -1e9
        self._count = None
        self._first = True
        for r in journal.read(self.home, time.time() - 2 * 86400, kinds=("ack", "cap_ack")):
            if r.get("kind") == "ack" and r.get("row"):
                self.acks.add(str(r["row"]))
            elif r.get("kind") == "cap_ack" and r.get("day") == journal.day():
                self.lifted[f"{r.get('scope')}:{r.get('key')}"] = r["day"]

    # ---- life ---------------------------------------------------------------------
    def start(self) -> "Watcher":
        feed.attach_tap(self.server, self.tap)
        with self.lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="halo-fleet-watch", daemon=True)
                self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        feed.detach_tap(self.server, self.tap)

    def _run(self) -> None:
        while not self._stop.wait(TICK_S):  # the first tick waits too: a route asks for one when it needs it
            try:
                self.tick()
            except Exception:  # one bad tick never ends the watcher
                pass

    def tap(self, frame: dict) -> None:
        if isinstance(frame, dict):
            self._frames.append(frame)

    def snapshot(self, max_age: float = 1.0) -> list:
        """The attention rows, from a tick at most `max_age` seconds old."""
        if time.monotonic() - self._last > max_age:
            self.tick()
        return list(self.rows)

    def done(self, rid: str) -> None:
        """A row answered or set aside: out of the queue now, and until its session's status catches up."""
        with self.lock:
            self.answered[rid] = time.time()
            self.rows = [r for r in self.rows if r["id"] != rid]

    # ---- one tick ----------------------------------------------------------------------
    def tick(self) -> list:
        with self.lock:
            now = time.time()
            view = sources.view(self.server, self.home)
            self.view = view
            self._drain(view, now)
            self._track_sessions(view, now)
            for hid, sid, aid, f in conflicts.note_view(self.touches, view):
                self._file(hid, sid, aid, f)
            self.conflicts = conflicts.find(view, self.touches, sources.claims(view, self.local_id), now)
            self.reached = self._caps(view, now)
            self.answered = {k: t for k, t in self.answered.items() if now - t < 12.0}
            capped = {(h, s) for h, s, _d in self.cap_paused}
            rows = attention.build(view, asks=self.asks, flows=sources.flows(self.home), orchestra=sources.orchestra(self.server),
                                   commands=sources.commands(self.server), reached=self.reached, conflicts=self.conflicts,
                                   seen=self.seen, acks=self.acks | set(self.answered), now=now, home=self.home,
                                   teams=sources.teams(self.server))  # 3.0.8.0 R2: team gates
            rows = [r for r in rows if not (r["kind"] == "paused" and (r["harness"], r["session_id"]) in capped)]
            ids = {r["id"] for r in rows}
            self.seen = {k: v for k, v in self.seen.items() if k in ids}
            self.rows = rows
            self._push(rows)
            if len(rows) != self._count:
                self._count = len(rows)
                feed.publish(self.server, {"event": "fleet", "harness": self.local_id,
                                         "data": {"action": "attention", "count": len(rows)}})
            self._first = False
            self._last = time.monotonic()
            return list(rows)

    def _drain(self, view: dict, now: float) -> None:
        rows = {(str(h.get("id")), str(s.get("session_id"))): s for h in view.get("harnesses") or []
                for s in h.get("sessions") or []}
        names = {str(h.get("id")): h.get("name") for h in view.get("harnesses") or []}
        while self._frames:
            f = self._frames.popleft()
            kind, data = f.get("event"), f.get("data") if isinstance(f.get("data"), dict) else {}
            hid, sid = str(f.get("harness") or self.local_id), str(f.get("session_id") or "")
            if kind in ASK_KINDS and data.get("id"):
                self.asks[(hid, sid, str(data["id"]))] = {"kind": ASK_KINDS[kind], "data": data,
                                                         "agent_id": f.get("agent_id") or "main", "ts": now}
            elif kind == "agent_state" and (hid, sid) in rows:
                path = conflicts.edited(data.get("current"))
                row = rows[(hid, sid)]
                if path and self.touches.note(hid, sid, str(data.get("agent_id") or "main"), conflicts.rel(path, row),
                                              caps.project_key(row)):
                    self._file(hid, sid, data.get("agent_id"), conflicts.rel(path, row))
                if data.get("state") == "failed":
                    self._journal("error", hid, sid, names, text=f"{data.get('name') or data.get('agent_id')} failed",
                                  agent_id=data.get("agent_id"))
            elif kind == "error" and sid:
                self._journal("error", hid, sid, names, text=str(data.get("message") or data.get("text") or "")[:300])
        pending = {(str(h.get("id")), str(s.get("session_id")), str(rid)) for h in view.get("harnesses") or []
                   for s in h.get("sessions") or [] for ids in ((s.get("pending") or {}).values()
                                                                if isinstance(s.get("pending"), dict) else [])
                   for rid in ids or []}
        self.asks = {k: v for k, v in self.asks.items() if k in pending or now - v["ts"] < 30}

    def _journal(self, kind: str, hid, sid, names: dict, **fields) -> None:
        journal.append(self.home, kind, harness=hid, harness_name=names.get(str(hid)), session_id=sid, **fields)

    def _file(self, hid, sid, aid, f) -> None:
        names = {str(h.get("id")): h.get("name") for h in self.view.get("harnesses") or []}
        self._journal("file", hid, sid, names, file=f, agent_id=aid)

    def _track_sessions(self, view: dict, now: float) -> None:
        cur = {}
        names = {}
        for h in view.get("harnesses") or []:
            names[str(h.get("id"))] = h.get("name")
            for s in h.get("sessions") or []:
                key = (str(h.get("id")), str(s.get("session_id")))
                cur[key] = {"title": attention.title_of(s), "local": bool(h.get("local")), "row": s}
        for key, info in cur.items():
            if key not in self.sessions:
                self._journal("session_start", key[0], key[1], names, title=info["title"], started=info["row"].get("started"))
            usd = info["row"].get("cost_usd")
            last = self.costs.get(key)
            if not info["local"] and isinstance(usd, (int, float)) and (last is None or (usd != last[1] and now - last[0] >= 60)):
                self.costs[key] = (now, float(usd))
                self._journal("cost", key[0], key[1], names, usd=round(float(usd), 6))
        for key in [k for k in self.sessions if k not in cur]:
            self._journal("session_end", key[0], key[1], names, title=self.sessions[key]["title"])
            self.costs.pop(key, None)
        self.sessions = {k: {"title": v["title"]} for k, v in cur.items()}

    # ---- caps -----------------------------------------------------------------------------
    def _caps(self, view: dict, now: float) -> list:
        day = journal.day()
        active = [r for r in caps.reached(view, caps.config(self.home), now)
                  if self.lifted.get(caps.cap_id(r["scope"], r["key"])) != day]
        for r in active:
            cid = caps.cap_id(r["scope"], r["key"])
            if (cid, day) not in self.cap_logged:
                self.cap_logged.add((cid, day))
                journal.append(self.home, "cap_pause", harness=self.local_id, scope=r["scope"], key=r["key"],
                               spent=r["spent"], cap=r["cap"])
            for hid, sid in r["sessions"]:
                if (hid, sid, day) not in self.cap_paused:
                    self.cap_paused.add((hid, sid, day))
                    send.session_cmd(self.server, self.home, hid, sid, "pause", {"reason": "cap"}, wait_s=0.0)
        return active

    def lift(self, scope: str, key: str, by: str) -> list:
        """The cap row's `a`: resume what that cap paused and hold it off for the rest of the day."""
        with self.lock:
            day = journal.day()
            cid = caps.cap_id(scope, key)
            self.lifted[cid] = day
            hit = next((r for r in self.reached if caps.cap_id(r["scope"], r["key"]) == cid), None)
            targets = [tuple(x) for x in (hit or {}).get("sessions") or []]
            resumed = []
            for hid, sid in targets:
                if (hid, sid, day) in self.cap_paused:
                    self.cap_paused.discard((hid, sid, day))
                    send.session_cmd(self.server, self.home, hid, sid, "resume", {}, wait_s=0.0)
                    resumed.append([hid, sid])
            journal.append(self.home, "cap_ack", harness=self.local_id, scope=scope, key=key, day=day, by=by)
            return resumed

    # ---- the phone ---------------------------------------------------------------------------
    def _push(self, rows: list) -> None:
        new = [r for r in rows if r["id"] not in self.pushed]
        self.pushed = {r["id"] for r in rows}
        if not new or self._first or not sources.push_ready(self.home):
            return
        from halo_harness.fleet import push
        push.spool(self.home, new, self.asks)


def watcher_for(server, home=None, start: bool = True) -> Watcher:
    """The server's one watcher (made, and started, on first use)."""
    with _make_lock:
        w = getattr(server, "fleet_watch", None)
        if w is None:
            w = Watcher(server, home if home is not None else server.state_dir)
            server.fleet_watch = w
    return w.start() if start else w
