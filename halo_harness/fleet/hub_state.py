"""halo_harness.fleet.hub_state -- the hub's merged view of the fleet (Halo
3.0.5.0 "Fleet" round R2).

Every member (members.json) with its sessions and agent trees, kept live
from the relays' announces and frames, plus this hub's own harness (its
local registry, the direct path) as a member of its own hub. `view()` is
Studio's `GET /api/fleet`:

    {harnesses: [{id, name, host, user, version, os, share, allow_control, online, last_seen,
                  cost_today, version_mismatch, local, sessions: [{...row, agents: [...]}]}],
     hub: {serving, name, port, bind, tls, fingerprint, url, members, online, pair_code_active}}

Member frames go to every sink (Studio's EventBridge) with `harness: <id>`
and their `session_id` unchanged; `fleet` frames say join, leave, online,
offline, sessions (a member's session list changed) and command (an outcome).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.fleet import protocol
from halo_harness.fleet.hub_capabilities import HubCaps
from halo_harness.fleet.hub_commands import Commands
from halo_harness.fleet.hub_links import LINK_TTL_S, STREAM_GRACE_S, Link, Member
from halo_harness.fleet.identity import CONTROL_LEVELS, SHARE_LEVELS
from halo_harness.fleet.pairing import HubPairing, public


def _key(rec: dict) -> Optional[bytes]:
    try:
        key = bytes.fromhex(str(rec.get("key_hex") or ""))
    except ValueError:
        return None
    return key if len(key) == 32 else None


def _default_local_view():
    from halo_harness.fleet.local_view import snapshot
    return snapshot()


class HubState:
    def __init__(self, home, *, name: str, identity: dict, local_view: Optional[Callable] = None,
                 pairing: Optional[HubPairing] = None) -> None:
        self.home = Path(home)
        self.name, self.identity = name, dict(identity)
        self.version = str(identity.get("version") or "")
        self.local_view = local_view or _default_local_view
        self.pairing = pairing or HubPairing(home)
        self.members: "dict[str, Member]" = {}
        self.sinks: list = []
        self.lock = threading.RLock()
        self.commands = Commands(self)
        self.caps = HubCaps(self)  # 3.0.6.0 R6: every harness's capability catalog
        self.serving: dict = {}
        self._mtime: Optional[float] = None
        self.reload(force=True, quiet=True)

    # ---- frames out ------------------------------------------------------------
    def publish(self, frame: dict) -> None:
        for sink in list(self.sinks):
            try:
                sink(frame)
            except Exception:
                pass

    def _member_frame(self, m: Member, action: str, **extra) -> None:
        info = {k: v for k, v in m.view(self.version).items() if k != "sessions"}
        self.publish({"session_id": None, "harness": m.id, "event": "fleet", "turn": None, "agent_id": None,
                      "ts": time.time(), "data": {"action": action, "harness": info, **extra}})

    # ---- members ----------------------------------------------------------------
    def reload(self, force: bool = False, quiet: bool = False) -> None:
        joined, gone = [], []
        with self.lock:
            mt = self.pairing.mtime()
            if not force and mt == self._mtime:
                return
            self._mtime = mt
            records = self.pairing.members()
            for hid, rec in records.items():
                m = self.members.get(hid)
                if m is None:
                    m = self.members[hid] = Member(public(rec), _key(rec))
                    joined.append(m)
                else:
                    m.record, m.key = public(rec), _key(rec)
            for hid in [h for h in self.members if h not in records]:
                gone.append(self.members.pop(hid))
        for m in gone:
            for lk in list(m.links.values()):
                if m.key is not None and lk.streams:
                    lk.push({"type": "kicked", "hub": self.name})  # its stream signs it with the key it holds
                lk.close()
        if not quiet:
            for m in joined:
                self._member_frame(m, "join")
            for m in gone:
                self._member_frame(m, "leave")

    def key_for(self, hid: str) -> Optional[bytes]:
        self.reload()
        m = self.members.get(hid)
        return m.key if m is not None else None

    def touch(self, hid: str, link_id: str) -> Optional[Link]:
        m = self.members.get(hid)
        if m is None or not link_id:
            return None
        now = time.time()
        with self.lock:
            lk = m.link(str(link_id)[:64])
            lk.last_seen = m.last_seen = now
            went_online, m.online = not m.online, True
        if went_online:
            self._member_frame(m, "online")
        return lk

    def announce(self, hid: str, body: dict) -> Optional[dict]:
        lk = self.touch(hid, str(body.get("link") or ""))
        m = self.members.get(hid)
        if lk is None or m is None:
            return None
        h = body.get("harness") if isinstance(body.get("harness"), dict) else {}
        share = body.get("share") if body.get("share") in SHARE_LEVELS else m.share
        rows = []
        for r in body.get("sessions") or []:
            if isinstance(r, dict) and isinstance(r.get("session_id"), str):
                agents = [protocol.scrub_agent(a, share) for a in (r.get("agents") or []) if isinstance(a, dict)]
                rows.append({**protocol.scrub_session(r), "agents": agents})
        with self.lock:
            before = (set(lk.sessions), m.harness.get("version"), m.share, m.allow_control)
            m.harness.update({k: h.get(k) for k in ("name", "host", "user", "version", "os") if h.get(k)})
            m.share = share
            m.allow_control = body.get("allow_control") if body.get("allow_control") in CONTROL_LEVELS else m.allow_control
            m.allow_answers = bool(body.get("allow_answers"))
            lk.sessions = {r["session_id"]: r for r in rows}
            m.note_costs(rows)
            after = (set(lk.sessions), m.harness.get("version"), m.share, m.allow_control)
        if before != after:
            self._member_frame(m, "sessions", sessions=m.sessions())
        if (m.record.get("name"), m.record.get("version")) != (m.harness.get("name"), m.harness.get("version")):
            self.pairing.update_member(hid, name=m.harness.get("name"), version=m.harness.get("version"))
        self.caps.seen(m, body)
        return {"ok": True, "member_name": m.name, "hub": self.hub_public()}

    def frames(self, hid: str, body: dict) -> Optional[int]:
        lk = self.touch(hid, str(body.get("link") or ""))
        m = self.members.get(hid)
        if lk is None or m is None:
            return None
        n = 0
        for f in (body.get("frames") or [])[:500]:
            f = protocol.scrub_frame(f, m.share) if isinstance(f, dict) else None
            sid = f.get("session_id") if f else None
            if not isinstance(sid, str):
                continue
            with self.lock:
                self._track(lk, f, m.share)
            self.publish({"session_id": sid, "harness": hid, "event": f.get("event"), "data": f.get("data"),
                          "turn": f.get("turn"), "agent_id": f.get("agent_id"), "ts": f.get("ts") or time.time()})
            n += 1
        return n

    @staticmethod
    def _track(lk: Link, f: dict, share: str) -> None:
        kind, sid, data = f.get("event"), f["session_id"], f.get("data")
        if not isinstance(data, dict):
            return
        if kind == "agent_state" and sid in lk.sessions and data.get("agent_id"):
            agents = [a for a in lk.sessions[sid].get("agents") or [] if a.get("agent_id") != data["agent_id"]]
            lk.sessions[sid]["agents"] = agents + [protocol.scrub_agent(data, share)]
        elif kind == "fleet" and data.get("action") == "unregister":
            lk.sessions.pop(sid, None)
        elif kind == "fleet" and data.get("action") in ("register", "update", "hello"):
            row = lk.sessions.setdefault(sid, {"agents": []})
            row.update({k: v for k, v in data.items() if k != "action"})

    # ---- streams, liveness -----------------------------------------------------
    def stream_open(self, hid: str, link_id: str) -> "tuple[Optional[Link], int]":
        lk = self.touch(hid, link_id)
        if lk is None:
            return None, 0
        with self.lock:
            lk.streams += 1
            lk.gen += 1
            return lk, lk.gen

    def stream_closed(self, lk: Link) -> None:
        with self.lock:
            lk.streams = max(0, lk.streams - 1)
            lk.last_seen = min(time.time(), time.time() - LINK_TTL_S + STREAM_GRACE_S)

    def tick(self) -> None:
        now = time.time()
        self.reload(force=now - getattr(self, "_forced", 0.0) > 5.0)  # also every 5 s: a coarse file clock
        if now - getattr(self, "_forced", 0.0) > 5.0:
            self._forced = now
        offline = []
        with self.lock:
            for m in self.members.values():
                for lid in [lid for lid, lk in m.links.items()
                            if not lk.streams and (lk.closed.is_set() or now - lk.last_seen > 2 * LINK_TTL_S)]:
                    del m.links[lid]
                if m.online and not any(lk.alive(now) for lk in m.links.values()):
                    m.online = False
                    offline.append(m)
        for m in offline:
            self._member_frame(m, "offline")

    def leave(self, hid: str) -> None:
        self.pairing.remove(hid, kicked=False)
        self.reload()

    # ---- the view -----------------------------------------------------------------
    def hub_public(self) -> dict:
        return {"id": self.identity.get("id"), "name": self.name, "version": self.version,
                "tls": bool(self.serving.get("tls")), "fingerprint": self.serving.get("fingerprint")}

    def you(self, hid: str) -> dict:
        m = self.members.get(hid)
        if m is None:
            return {"member": False}
        return {"member": True, "name": m.name, "online": m.online, "sessions": len(m.sessions()),
                "version_mismatch": m.view(self.version)["version_mismatch"]}

    def view(self) -> dict:
        rows = []
        try:
            local = self.local_view()
        except Exception:
            local = None
        if local:
            rows.append(local)
        with self.lock:
            members = sorted(self.members.values(), key=lambda m: m.name.lower())
            rows += [m.view(self.version) for m in members]
            online = sum(1 for m in members if m.online)
        serving = {k: self.serving.get(k) for k in ("port", "bind", "tls", "fingerprint", "url")}
        return {"harnesses": rows, "hub": {"serving": bool(self.serving.get("port")), "name": self.name, **serving,
                                           "members": len(members), "online": online,
                                           "pair_code_active": self.pairing.active_codes() > 0}}
