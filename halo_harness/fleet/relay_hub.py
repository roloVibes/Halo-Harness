"""halo_harness.fleet.relay_hub -- one joined hub's relay thread (Halo
3.0.5.0 "Fleet" round R2; started by relay_runtime.py).

`HubRelay(entry, actives)` announces the sessions `actives()` returns (rows
with their agent trees, scrubbed for the share level; 3.0.6.0 R6: plus the
capability catalog's summary and hash, fleet/capabilities.py), forwards each one's
feed through protocol.scrub_frame, reads the hub's signed command stream
(protocol.verify_down: a doc that is not the hub's, out of order or stale is
ignored; a command id is run once) and runs each command on its own worker
thread through control.py, replying `asked` when the owner's card opens and
the outcome when it is decided. A kick (the hub's signed `kicked`, or a 403)
marks the hub `kicked` in fleet.json and ends the thread; any other failure
retries with backoff.
"""

from __future__ import annotations

import random
import secrets
import threading
import time
from typing import Callable, Optional

from halo_harness.fleet import capabilities, control, identity, ollama_share, protocol, store
from halo_harness.fleet.relay import HubError, HubLink

ANNOUNCE_S = 10.0
FRAME_BATCH = 200
BATCH_BYTES = 2_000_000  # the hub takes a body up to 4 MB
FRAME_BYTES = 256_000
SUB_QUEUE = 1024
STREAM_DEAD_S = 3 * protocol.PING_S
BACKOFF_MAX_S = 60.0


class Kicked(Exception):
    pass


class HubRelay(threading.Thread):
    def __init__(self, entry: dict, actives: Callable[[], list]) -> None:
        super().__init__(daemon=True, name=f"halo-fleet-relay-{str(entry.get('name') or 'hub')[:12]}")
        self.entry = dict(entry)
        self.actives = actives
        self.link_id = secrets.token_hex(8)
        self.stop_ev, self.poke_ev = threading.Event(), threading.Event()
        self.state, self.error, self.member_name = "starting", "", None
        self.link: Optional[HubLink] = None
        self._subs: dict = {}
        self._done: dict = {}
        self._policy: dict = {}
        self._mtime = store.mtime()
        self._ollama = ollama_share.Forwarder(self.entry)  # 3.3.4.0 R2: the ledger's lines

    def poke(self) -> None:
        self.poke_ev.set()

    def stop(self) -> None:
        self.stop_ev.set()
        self.poke_ev.set()

    # ---- the loop -----------------------------------------------------------------
    def run(self) -> None:
        backoff = 1.0
        while not self.stop_ev.is_set() and self._current():
            if identity.offline() or not self.actives():
                self.state = "offline" if identity.offline() else "idle"
                self.poke_ev.wait(5.0)
                self.poke_ev.clear()
                continue
            try:
                self._pump()
                backoff = 1.0
            except Kicked:
                store.mark(self.entry.get("hub_id"), state="kicked", kicked_at=time.time())
                self.state = "kicked"
                break
            except HubError as e:
                self.error = str(e)
                if e.status == -1:
                    self.state = "error"
                    break
                if e.kicked or e.status == 403:
                    store.mark(self.entry.get("hub_id"), state="kicked", kicked_at=time.time())
                    self.state = "kicked"
                    break
            except Exception as e:  # never let a relay bug reach a session
                self.error = f"{type(e).__name__}: {e}"
            finally:
                self._unsubscribe_all()
                if self.link is not None:
                    self.link.close()
            if self.stop_ev.is_set():
                break
            self.state = "retrying"
            self.stop_ev.wait(backoff * (0.75 + random.random() / 2))
            backoff = min(BACKOFF_MAX_S, backoff * 2)
        self._unsubscribe_all()
        if self.state not in ("kicked", "error"):
            self.state = "stopped"

    def _current(self) -> bool:
        """False once this hub left fleet.json or was kicked; picks up share / control changes."""
        mt = store.mtime()
        if mt == self._mtime:
            return True
        self._mtime = mt
        hit = next((h for h in store.hubs() if h.get("hub_id") == self.entry.get("hub_id")), None)
        if hit is None or hit.get("state", "joined") != "joined":
            return False
        self.entry = dict(hit)
        self.poke()
        return True

    def _pump(self) -> None:
        key, member = store.key_for(self.entry), identity.harness()["id"]
        if key is None:
            raise HubError("the pair key for this hub is missing; `halo fleet join` it again", status=-1)
        self.link = link = HubLink(self.entry, key, member)
        self._announce()
        stream = link.open_stream(self.link_id)
        self.state, self.error, last_seq = "connected", "", 0
        next_announce = time.monotonic() + ANNOUNCE_S
        try:
            while not self.stop_ev.is_set() and self._current() and not identity.offline():
                for doc in stream.read(0.25):
                    if protocol.verify_down(key, member, self.link_id, doc, last_seq):
                        continue  # not the hub's, out of order or stale: ignored
                    last_seq = doc["seq"]
                    if doc.get("type") == "kicked":
                        raise Kicked()
                    if doc.get("type") == "command":
                        self._command(doc)
                self._sync_subs()
                batch = self._drain()
                if batch:
                    link.request("POST", protocol.PREFIX + "/frames", protocol.doc(link=self.link_id, frames=batch))
                self._ollama.tick(link, self.link_id, force=not self.actives())
                if control.policy(self.entry) != self._policy:  # `halo config set fleet.share ...` while running
                    self.poke()
                if self.poke_ev.is_set() or time.monotonic() >= next_announce:
                    self.poke_ev.clear()
                    self._announce()
                    next_announce = time.monotonic() + ANNOUNCE_S
                if time.monotonic() - stream.last_data > STREAM_DEAD_S:
                    raise HubError("the hub went quiet")
                if not self.actives():  # the last session closed: tell the hub, then idle
                    self._announce()
                    return
        finally:
            stream.close()

    def _announce(self) -> None:
        pol = control.policy(self.entry)
        rows = [self._row(a, pol["share"]) for a in self.actives()]
        reply = self.link.request("POST", protocol.PREFIX + "/announce", protocol.doc(
            link=self.link_id, harness=identity.harness(), share=pol["share"], allow_control=pol["allow_control"],
            allow_answers=pol["allow_answers"], sessions=rows, **capabilities.announce_fields(on_change=self.poke)))
        self.member_name = reply.get("member_name") or self.member_name
        self._policy = pol

    @staticmethod
    def _row(act, share: str) -> dict:
        from halo_harness.fleet.local_view import session_row
        try:
            status = act.handle.status()
        except Exception:
            status = None
        try:
            from halo_harness.agent.agent_registry import tree_for
            agents = tree_for(act.handle.session).public_rows()
        except Exception:
            agents = []
        row = protocol.scrub_session(session_row(act.entry, status, [protocol.scrub_agent(a, share) for a in agents]))
        if row.get("kind") == "orchestra-worker":  # 3.0.5.0 R4: its run's claims, for the hub's conflict warnings
            from halo_harness.fleet.conflicts import own_claims
            row["claims"] = own_claims()
        return row

    # ---- feeds ----------------------------------------------------------------------
    def _sync_subs(self) -> None:
        acts = self.actives()
        ids = {id(a) for a in acts}
        for k in [k for k in self._subs if k not in ids]:
            act, sub = self._subs.pop(k)
            act.handle.hub.unsubscribe(sub)
        for a in acts:
            cur = self._subs.get(id(a))
            if cur is not None and cur[1].closed.is_set():  # it overflowed: frames were lost, so announce afresh
                a.handle.hub.unsubscribe(cur[1])
                cur = None
                self.poke()
            if cur is None:
                self._subs[id(a)] = (a, a.handle.hub.subscribe(SUB_QUEUE))

    def _unsubscribe_all(self) -> None:
        for act, sub in list(self._subs.values()):
            try:
                act.handle.hub.unsubscribe(sub)
            except Exception:
                pass
        self._subs.clear()

    def _drain(self) -> list:
        """Frames to send now, as this hub's share level allows: at most FRAME_BATCH of them and about
        BATCH_BYTES; a frame over FRAME_BYTES goes with its data replaced by its size."""
        share = control.policy(self.entry)["share"]
        out, size = [], 0
        for _act, sub in list(self._subs.values()):
            while len(out) < FRAME_BATCH and size < BATCH_BYTES:
                raw = sub.get(timeout=0)
                if raw is None:
                    break
                f = protocol.scrub_frame(raw, share)
                if f is None:
                    continue
                n = len(protocol.encode(f))
                if n > FRAME_BYTES:
                    f, n = {**f, "data": {"omitted": "too large for the fleet feed", "bytes": n}}, 200
                out.append(f)
                size += n
        return out

    # ---- commands -------------------------------------------------------------------
    def _command(self, doc: dict) -> None:
        cid, now = str(doc.get("cid") or ""), time.time()
        self._done = {k: t for k, t in self._done.items() if now - t < 2 * protocol.WINDOW_S}
        if not cid or cid in self._done:
            return
        self._done[cid] = now
        act = next((a for a in self.actives() if a.session_id == doc.get("session_id")), None)
        if act is None:
            self._reply(doc, {"state": "refused", "error": f"no session {doc.get('session_id')!r} here any more"})
            return
        threading.Thread(target=self._run_command, args=(act, doc), daemon=True, name="halo-fleet-cmd").start()

    def _run_command(self, act, doc: dict) -> None:
        out = control.run(act.handle, doc, {**control.policy(self.entry), "hub_entry": self.entry},  # R7: run_task
                          interim=lambda: self._reply(doc, {"state": "asked"}))
        self._reply(doc, out)

    def _reply(self, doc: dict, out: dict) -> None:
        link = self.link
        if link is None:
            return
        try:
            link.request("POST", protocol.PREFIX + "/reply", protocol.doc(link=self.link_id, cid=doc.get("cid"), **out))
        except Exception:
            pass
