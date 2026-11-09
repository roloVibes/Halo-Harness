"""halo_signal.session -- the bridge's side of "the session a phone talks to": the live sessions, attaching one,
starting one when a text arrives and none is attached, its control socket, and its event feed.

    Sessions()                       the core's sessions through `halo_harness.ext.remote` (tests pass their own):
                                     .live() -> [row], .connect(session_id) -> client | None,
                                     .start(cwd, model, by) -> (row | None, line)
    PeerRT                           one phone's runtime state (in memory; phones.json keeps what outlives a restart)
    attach(b, rt, row) -> error | None, detach(b, rt), call(b, rt, cmd, **fields) -> dict
    ensure(b, rt) -> "ready" | "starting" | "error"   the attached session, the one the phone had before a restart
                                     when it is still live, else a new one in the phone's home folder: said in one line
                                     first ("Starting a session in ~/work on <model>."), started off the bridge's loop,
                                     and the texts that arrive meanwhile wait for it (rt.waiting)
"""

from __future__ import annotations

import threading
from typing import Optional

from halo_harness.ext import remote as R

from halo_signal.phones import short

FEED_KINDS = ["text_chunk", "permission_request", "question", "plan_review", "approval_request", "error",
              "turn_done", "message_start", "user_message", "tool_use_ready"]


class Sessions:
    def live(self) -> list:
        return R.sessions()

    def connect(self, session_id: str):
        return R.connect(session_id)

    def start(self, cwd: str, model: str, by: str):
        return R.start_session(cwd, model, by)


class PeerRT:
    """One phone's runtime state."""

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
        self.undelivered: list = []      # card messages whose send failed (outbox.py)
        self.starting = False            # a session is being started for this phone
        self.waiting: list = []          # prompts that wait for it: [{"text", "image"?}]
        self.held: Optional[str] = None  # a text that may or may not answer an open card (answers.py)
        self.relay = None                # the turn's answer as it is written (relay.Relay)
        self.mine = False                # the running turn is one the phone started


class _Feed(threading.Thread):
    def __init__(self, bridge, rt: PeerRT, client, gen: int) -> None:
        super().__init__(name="halo-signal-feed", daemon=True)
        self.bridge, self.rt, self.client, self.gen = bridge, rt, client, gen
        self.stop_ev = threading.Event()
        self.ready = threading.Event()

    def run(self) -> None:
        try:
            self.client.call("subscribe", kinds=FEED_KINDS)
            self.ready.set()
            while not self.stop_ev.is_set():
                ev = self.client.next_event(0.4)
                if ev is not None:
                    self.bridge.inbox.put({"kind": "feed", "aci": self.rt.aci, "gen": self.gen, "frame": ev})
        except (OSError, ValueError, TimeoutError):
            pass
        finally:
            self.ready.set()
            try:
                self.client.close()
            except Exception:
                pass
            if not self.stop_ev.is_set():
                self.bridge.inbox.put({"kind": "feed_closed", "aci": self.rt.aci, "gen": self.gen})


def one_line(text, limit: int = 160) -> str:
    return R.cards.one_line(text, limit)


def label(row: dict) -> str:
    title = (row.get("title") or "").strip() or "untitled"
    return f"{one_line(title, 48)} ({short(str(row.get('cwd') or '?'))})"


def live_sessions(b) -> list:
    try:
        return list(b.sessions.live())
    except Exception:
        return []


def tell_session(rt, attached: bool) -> None:
    """The attached session's `remote N` chip (control-socket `note`); best effort."""
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
        try:
            rt.client.close()
        except Exception:
            pass
        rt.client = None
    rt.entry, rt.relay, rt.mine = None, None, False
    rt.permission, rt.question, rt.plan, rt.approval, rt.held = [], None, None, None, None
    from halo_signal import outbox
    outbox.forget(b, rt, "dropped_detached")
    b.transport.typing.stop(rt.aci)


def attach(b, rt, row: dict) -> Optional[str]:
    detach(b, rt)
    try:
        client, feed_client = b.sessions.connect(row["session_id"]), b.sessions.connect(row["session_id"])
        if client is None or feed_client is None:
            return "That session is no longer live. /sessions lists the live ones."
        client.call("ping")
    except (OSError, ValueError, TimeoutError, KeyError) as e:
        return f"Could not reach that session ({type(e).__name__})."
    rt.entry, rt.client = row, client
    rt.feed = _Feed(b, rt, feed_client, rt.gen)
    rt.feed.start()
    rt.feed.ready.wait(3.0)
    tell_session(rt, True)
    b.phones.set(rt.aci, session_id=row.get("session_id"))
    return None


def ensure(b, rt) -> str:
    if rt.client is not None:
        return "ready"
    if rt.starting:
        return "starting"
    want = b.phones.get(rt.aci)
    known = want.get("session_id")
    row = next((r for r in live_sessions(b) if known and r.get("session_id") == known), None)
    if row is not None and attach(b, rt, row) is None:
        b.say(rt.aci, "Back in " + label(row) + ".")
        return "ready"
    start_new(b, rt, want["home"])
    return "starting"


def start_new(b, rt, home: str) -> None:
    """Start a session in `home` off the bridge's loop; its answer comes back as a `started` item."""
    detach(b, rt)
    model = str(b.cfg.get("model") or "") or R.default_model()
    rt.starting = True
    b.say(rt.aci, f"Starting a session in {short(home)} on {model or 'your default model'}.")

    def work() -> None:
        try:
            row, line = b.sessions.start(home, model, f"signal:{rt.aci[:8]}")
        except Exception as e:  # the start's own trouble, in one line
            row, line = None, f"{type(e).__name__}: {e}"
        b.inbox.put({"kind": "started", "aci": rt.aci, "row": row, "line": line})
    threading.Thread(target=work, name="halo-signal-start", daemon=True).start()


def call(b, rt, cmd: str, **fields) -> dict:
    """One control-socket request to the attached session; `{"ok": False, "error": ...}` when there is none or the
    link failed (the attachment is then dropped)."""
    if rt.client is None:
        return {"ok": False, "error": "no session is attached (send a text to start one, or /sessions)"}
    try:
        return rt.client.call(cmd, **fields)
    except (OSError, ValueError, TimeoutError):
        detach(b, rt)
        b.phones.set(rt.aci, session_id=None)
        return {"ok": False, "error": "The session is no longer reachable. /sessions lists the live ones."}
