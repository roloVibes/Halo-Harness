"""halo_harness.remote.bridge_session -- the bridge's side of "the session a
phone is attached to" (Halo 2.0.9 round 3): picking and attaching a live
session, calling its control socket, and turning its event feed into phone
messages. State lives on the bridge's `PeerRT`; see bridge.py."""

from __future__ import annotations

import threading
from typing import Optional

from halo_harness.remote import bridge_cards as cards
from halo_harness.remote.client import default_token_for


FEED_KINDS = ["text_chunk", "permission_request", "question", "plan_review", "approval_request", "error",
              "turn_done", "message_start"]


class PeerRT:
    """Per-peer runtime state (in memory only)."""

    def __init__(self, aci: str, verbosity: str) -> None:
        self.aci, self.verbosity = aci, verbosity
        self.entry: Optional[dict] = None
        self.client = None
        self.feed = None
        self.gen = 0
        self.sessions: list = []
        self.permission: list = []
        self.question: Optional[dict] = None
        self.plan: Optional[dict] = None
        self.approval: Optional[dict] = None
        self.md_state: dict = {}


class _Feed(threading.Thread):
    def __init__(self, bridge, rt: PeerRT, entry: dict, gen: int) -> None:
        super().__init__(name="halo-signal-feed", daemon=True)
        self.bridge, self.rt, self.entry, self.gen = bridge, rt, entry, gen
        self.stop_ev = threading.Event()
        self.ready = threading.Event()  # set once subscribed (or given up)

    def run(self) -> None:
        c = None
        try:
            c = self.bridge.client_factory(self.entry["endpoint"], default_token_for(self.entry))
            c.call("subscribe", kinds=FEED_KINDS)
            self.ready.set()
            while not self.stop_ev.is_set():
                ev = c.next_event(0.4)
                if ev is not None:
                    self.bridge.inbox.put({"kind": "feed", "aci": self.rt.aci, "gen": self.gen, "frame": ev})
        except (OSError, ValueError, TimeoutError):
            pass
        finally:
            self.ready.set()
            if c is not None:
                c.close()
            if not self.stop_ev.is_set():
                self.bridge.inbox.put({"kind": "feed_closed", "aci": self.rt.aci, "gen": self.gen})


def cwd_tail(cwd) -> str:
    parts = [p for p in str(cwd or "").replace("\\", "/").split("/") if p]
    return "/".join(parts[-2:]) or "?"


def label(entry: dict) -> str:
    title = (entry.get("title") or "").strip() or "untitled"
    return f"{cards.one_line(title, 48)} ({cwd_tail(entry.get('cwd'))})"


def live_sessions(b) -> list:
    """Live sessions, most recently started first."""
    try:
        rows = list(b.registry.list_live())
    except Exception:
        rows = []
    return sorted(rows, key=lambda r: r.get("started") or 0, reverse=True)


def tell_session(rt, attached: bool) -> None:
    """Tell the attached session a phone came or went (control-socket `note`;
    drives the TUI's `remote` chip). Best effort: an old session ignores it."""
    if rt.client is None:
        return
    try:
        rt.client.call("note", name="remote.attached", peer=rt.aci[:8], attached=attached)
    except Exception:
        pass


def detach(b, rt) -> None:
    tell_session(rt, False)
    rt.gen += 1
    if rt.feed is not None:
        rt.feed.stop_ev.set()
        rt.feed = None
    if rt.client is not None:
        rt.client.close()
        rt.client = None
    rt.entry = None
    rt.permission, rt.question, rt.plan, rt.approval = [], None, None, None
    b.transport.typing.stop(rt.aci)


def attach(b, rt, entry: dict) -> Optional[str]:
    """Attach `rt` to `entry`; an error sentence, or None on success."""
    detach(b, rt)
    try:
        client = b.client_factory(entry["endpoint"], default_token_for(entry))
        client.call("ping")
    except (OSError, ValueError, TimeoutError, KeyError) as e:
        return f"Could not reach that session ({type(e).__name__})."
    rt.entry, rt.client = entry, client
    rt.feed = _Feed(b, rt, entry, rt.gen)
    rt.feed.start()
    rt.feed.ready.wait(3.0)  # events after this point are not missed
    tell_session(rt, True)
    return None


def ensure_attached(b, rt) -> bool:
    """True when `rt` has a session; otherwise attach the newest live one."""
    if rt.client is not None:
        return True
    rows = live_sessions(b)
    if not rows:
        b.say(rt.aci, "No live halo session. Start halo with `remote.enabled` set to true, then /sessions.")
        return False
    err = attach(b, rt, rows[0])
    if err:
        b.say(rt.aci, err)
        return False
    b.say(rt.aci, "Attached to " + label(rows[0]) + ".")
    return True


def call(b, rt, cmd: str, **fields) -> dict:
    """One control-socket request; `{"ok": False, "error": ...}` when there is
    no session or the link failed (the attachment is then dropped)."""
    if not ensure_attached(b, rt):
        return {"ok": False, "error": "no session"}
    try:
        return rt.client.call(cmd, **fields)
    except (OSError, ValueError, TimeoutError):
        detach(b, rt)
        return {"ok": False, "error": "The session is no longer reachable. /sessions lists the live ones."}


def on_feed(b, rt, frame: dict) -> None:
    ev, data = frame.get("event"), frame.get("data") or {}
    aci = rt.aci
    if ev == "text_chunk":
        if rt.verbosity == "loud":
            b.say(aci, str(data.get("text") or ""), markdown=True, state=rt.md_state)
    elif ev == "message_start":
        b.transport.typing.start(aci)
    elif ev == "permission_request":
        rt.permission.append({"id": data.get("id")})
        for part in cards.permission_messages(data):
            b.say(aci, part)
    elif ev == "question":
        qs = cards.normalize_questions(data)
        if qs:
            rt.question = {"id": data.get("id"), "questions": qs, "idx": 0, "answers": {}}
            b.say(aci, cards.question_card(qs[0], 0, len(qs)))
    elif ev == "plan_review":
        rt.plan = {"id": data.get("id")}
        b.say(aci, cards.plan_card(data), markdown=True)
    elif ev == "approval_request":
        rt.approval = {"id": data.get("id")}
        b.say(aci, cards.approval_card(data))
    elif ev == "error":
        b.say(aci, "Error: " + cards.one_line(data.get("message"), 600))
    elif ev == "turn_done":
        b.transport.typing.stop(aci)
        rt.md_state.clear()
        rt.permission, rt.question, rt.plan, rt.approval = [], None, None, None
        st = call(b, rt, "status")
        b.say(aci, cards.cost_line(st.get("result") or {}) if st.get("ok") else "Done.")
