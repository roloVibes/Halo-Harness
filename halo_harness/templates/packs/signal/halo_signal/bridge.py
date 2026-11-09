"""halo_signal.bridge -- the conversation loop (Halo 2.0.9 round 3; 3.3.13.0 R3: the signal pack's service).

    Bridge(config, transport, *, sessions=None, clock=None, pairing=None, audit=None, phones=None, health=None,
           transcribe=None, capture=None, fleet_lines=None, notes=None)
      .run(stop, tick=0.25)    blocks until `stop` is set or the service's stop file appears
      .step(timeout)           one item from the inbox, then the tick (pairing trust steps, status lines, notes)

Everything is injected for the tests: `transport` (transport.SignalTransport, or anything with its
`set_sink/start/stop/send/send_receipt/safety_number/trust/take_attachments` and a `typing` keeper), `sessions`
(session.Sessions: the core's sessions through ext.remote), `clock` (`time()` / `monotonic()`). `config`:
identity_model, own_aci, rate_per_minute, stale_window_s, pair_ttl_s, verbosity, model. One thread runs the loop;
signal-cli's reader, the feed threads and a session start only enqueue. Inbound envelopes are inbound.py's.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Optional

from halo_signal import feed, inbound, media, notes as notes_mod, outbox, render, routing
from halo_signal.audit import Audit
from halo_signal.errors import SignalError, UntrustedKey
from halo_signal.pairing import Pairing
from halo_signal.phones import Phones
from halo_signal.ratelimit import RateLimiter
from halo_signal.session import PeerRT, Sessions, detach

BAD_PER_MINUTE = 10
SWITCH_S = 5.0  # 3.3.13.1 (REMOTE-2): how often a running bridge reads its two off switches again
SWEEP_S = 3600.0  # 3.3.14.0 R2 (REVIEW #20, REMOTE-3): how often a running bridge clears inbox/ files past a day
GOODBYE = ("No one is listening on this computer now (Halo's supervisor stopped); your texts wait on Signal's server "
           "until it runs again.")


class Bridge:
    def __init__(self, config: dict, transport, *, sessions=None, clock=None, pairing: Optional[Pairing] = None,
                 audit: Optional[Audit] = None, phones: Optional[Phones] = None, health=None, transcribe=None,
                 capture=None, fleet_lines=None, notes=None, inbox_dir=None) -> None:
        from halo_signal import files
        self.cfg, self.transport = config, transport
        self.sessions = sessions or Sessions()
        self.clock = clock or time
        self.linked = config.get("identity_model") == "linked"
        self.own_aci = str(config.get("own_aci") or "")
        self.pairing = pairing or Pairing(transport=transport, clock=self.clock.time,
                                          ttl=int(config.get("pair_ttl_s") or 600), trust_needed=not self.linked)
        self.audit = audit or Audit(clock=self.clock.time)
        self.phones = phones or Phones()
        per_min = int(config.get("rate_per_minute") or 30)
        self.limiter = RateLimiter(per_min, self.clock.monotonic)
        self.bad_limiter = RateLimiter(min(BAD_PER_MINUTE, per_min), self.clock.monotonic)
        self.window = int(config.get("stale_window_s") or 300)
        self.inbox: "queue.Queue" = queue.Queue()
        self.inbox_dir = inbox_dir or files.path("inbox")
        self.rts: dict = {}
        self.groups_seen: set = set()
        self.health = health
        self.transcribe = transcribe or media.default_transcribe
        self.capture = capture or media.default_capture
        self.fleet_lines = fleet_lines or notes_mod.default_fleet_lines
        self.notes = notes_mod.Notes(self) if notes is None else (notes or None)  # False: none (tests)
        self.ended, self._switch_at = "", 0.0  # 3.3.13.1 (REMOTE-2): the line when a switch turned off mid-run
        self._sweep_at = self.clock.monotonic() + SWEEP_S  # service.py swept inbox/ at start
        self.last_ts = None  # 3.3.13.1 (REMOTE-1): the sent timestamp of the last message out (_send)

    # ---- loop ------------------------------------------------------------------------------
    def run(self, stop: threading.Event, tick: float = 0.25) -> "Bridge":
        self.transport.set_sink(self.inbox.put)
        if self.health is not None:
            self.health.write("starting", "starting signal-cli")
        self.transport.start()
        try:
            while not stop.is_set() and not self.ended:
                self.step(tick)
                if self.health is not None and self.health.stop_asked():
                    break
        finally:
            self.shutdown()
            if self.ended and self.health is not None:
                self.health.write("off", self.ended)
        return self

    def switches(self) -> None:
        """3.3.13.1 (plans/REVIEW-2026-11.md #19, REMOTE-2): `remote.enabled` and the pack's `on` are read again every
        SWITCH_S (they were read once, at start); either off ends the run: `ended` holds the one line, service.main
        prints it and exits 0, so the supervisor leaves the service stopped."""
        now = self.clock.monotonic()
        if now < self._switch_at:
            return
        self._switch_at = now + SWITCH_S
        from halo_harness.ext import remote as R
        from halo_signal import settings
        if not settings.get("on"):
            self.ended = "the bridge is off (/signal on turns it back on)"
        elif not R.enabled():
            self.ended = "remote.enabled is false, every transport's switch (halo config set remote.enabled true)"

    def step(self, timeout: float = 0.25) -> None:
        try:
            item = self.inbox.get(timeout=timeout)
        except queue.Empty:
            item = None
        try:
            if item is not None:
                self.handle(item)
            self.pairing.service(self.transport)
            feed.tick(self, list(self.rts.values()))
            if self.notes is not None:
                self.notes.tick()
            if self.health is not None:
                self.health.beat(len(self.pairing.peers()))
            self.switches()
            if self.clock.monotonic() >= self._sweep_at:  # a long-running bridge keeps "deleted after a day" true
                self._sweep_at = self.clock.monotonic() + SWEEP_S
                media.sweep(self.inbox_dir)
        except Exception as e:  # one bad item never ends the service; it leaves an audit line
            try:
                self.audit.record("-", 0, type(e).__name__, "error", "handler_exception")
            except Exception:
                pass

    def shutdown(self) -> None:
        for rt in list(self.rts.values()):
            if rt.entry is not None or rt.starting:
                self._send(rt.aci, GOODBYE)
            detach(self, rt)
        self.transport.stop()
        if self.health is not None:
            self.health.write("stopped", "stopped")

    def handle(self, item: dict) -> None:
        kind = item.get("kind")
        rt = self.rts.get(item.get("aci")) if item.get("aci") else None
        if kind == "envelope":
            inbound.on_envelope(self, item)
        elif kind == "feed" and rt is not None and item["gen"] == rt.gen:
            feed.on_feed(self, rt, item["frame"])
        elif kind == "feed_closed" and rt is not None and item["gen"] == rt.gen:
            detach(self, rt)
            self.phones.set(rt.aci, session_id=None)
            self.say(rt.aci, "The session ended. Your next text starts a new one; /sessions lists the live ones.")
        elif kind == "started" and rt is not None:
            routing.started(self, rt, item.get("row"), str(item.get("line") or ""))
        elif kind == "notice":
            self.on_notice(item)

    def on_notice(self, item: dict) -> None:
        name = item.get("name")
        if name == "rate_limited":
            wait = float(item.get("retry_after") or 0)
            tok = f" Captcha token: {item['token']}" if item.get("token") else ""
            self.pairing.add_notice("rate_limited", "", f"Signal rate limit: sending paused for {int(wait)} s.{tok}")
            if self.health is not None:
                self.health.write("rate-limited", f"Signal paused sending for {int(wait)} s")
        elif name == "subscribe_failed":
            code, why = item.get("code"), " ".join(str(item.get("message") or "").split())[:200]
            self.audit.record("-", 0, "subscribeReceive", "signal", f"subscribe_failed {code}")
            if self.health is not None:
                self.health.write("starting", f"signal-cli refused subscribeReceive (code {code}{': ' + why if why else ''})")
        elif name in ("connected", "disconnected"):
            if self.health is not None:
                self.health.write("connected" if name == "connected" else "starting",
                                  "connected to Signal" if name == "connected" else "signal-cli's link dropped")
            if name == "connected":
                outbox.flush_all(self)

    def on_group(self, info) -> None:
        gid = str(info.get("groupId") or "") if isinstance(info, dict) else ""
        if gid not in self.groups_seen:
            self.groups_seen.add(gid)
            self.pairing.add_notice("group_message", "", "Halo's number is in a Signal group; group messages are "
                                    "ignored (only direct messages from a paired phone are read).")

    # ---- sending ----------------------------------------------------------------------------
    def rt(self, aci: str) -> PeerRT:
        if aci not in self.rts:
            self.rts[aci] = PeerRT(aci, self.phones.get(aci)["verbosity"])
        return self.rts[aci]

    def say(self, aci: str, text: str, *, markdown: bool = False, state: Optional[dict] = None, card: bool = False,
            attachment_text: Optional[str] = None, attachment_path: Optional[str] = None) -> None:
        """Send `text` (a `card` that fails to send is kept and sent again: outbox.py); `attachment_text` goes as
        reply.txt, `attachment_path` as the file it names."""
        if not text or not text.strip():
            return
        out = render.render_markdown(text, state) if markdown else render.render_plain(text)
        extra = render.data_uri(attachment_text) if attachment_text else attachment_path
        parts = [(m.text, (out.attachment or extra) if i == 0 else None, m.styles) for i, m in enumerate(out.messages)
                 if m.text.strip()]
        if card:
            outbox.send_card(self, aci, parts)
            return
        if aci in self.rts and self.rts[aci].undelivered:
            outbox.flush(self, self.rts[aci])
        for part in parts:
            self._send(aci, *part)

    def _send(self, aci: str, text: str, attachment=None, styles=None) -> bool:
        self.last_ts = None  # 3.3.13.1 (REMOTE-1): signal-cli's `send` answers {timestamp, ...}; outbox keeps a card's
        try:
            got = self.transport.send(aci, text, attachment=attachment, styles=styles)
        except UntrustedKey:
            self.pairing.block(aci, self.safe_safety_number(aci))
        except SignalError:
            return False
        self.last_ts = got.get("timestamp") if isinstance(got, dict) else None
        return True

    def safe_safety_number(self, aci: str) -> Optional[str]:
        try:
            return self.transport.safety_number(aci)
        except SignalError:
            return None


def run_bridge(config: dict, transport, *, stop: Optional[threading.Event] = None, **kw) -> Bridge:
    return Bridge(config, transport, **kw).run(stop or threading.Event())
