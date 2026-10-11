"""halo_harness.remote.bridge -- the Signal bridge daemon loop (Halo 2.0.9
round 3): phone messages in, session commands out, session events back.

    run_bridge(config, transport, registry, clock) -> Bridge   (blocks until `stop`)

Everything is injected: `transport` (SignalTransport, or any object with its
`set_sink/start/stop/send/send_receipt/safety_number/trust/take_attachments`
and a `typing` keeper), `registry` (anything with `list_live()`; default the
sessions registry), `clock` (anything with `time()` and `monotonic()`;
default the `time` module). `config` is a dict: `identity_model`, `own_aci`,
`rate_per_minute`, `verbosity`, `stale_window_s`, `pair_code_ttl_s`
(`signal_config.bridge_settings()` plus `load_signal_config()`).

One thread runs the loop; signal-cli's reader and the per-session feed
threads only enqueue. An envelope goes through: sender identity (an unknown
sender is never answered), blocked-peer check, rate limit, long-text
attachment, signature, read receipt, then routing (bridge_commands.py).
Nothing of a message is logged or stored; the audit line is a hash.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Optional

from halo_harness.remote import bridge_commands as commands
from halo_harness.remote import bridge_session as sess
from halo_harness.remote.bridge_session import PeerRT
from halo_harness.remote import bridge_state, render, signing
from halo_harness.remote.audit import Audit
from halo_harness.remote.client import ControlClient
from halo_harness.remote.pairing import Pairing
from halo_harness.remote.ratelimit import DROP_NOTIFY, OK, RateLimiter
from halo_harness.remote.signal_errors import RateLimited, SignalError, UntrustedKey

SIGNED_HINT = "Commands must end with ' #<counter>:<mac>' (see docs/REMOTE.md, Signing)."
SIGN_REFUSALS = {"unsigned": SIGNED_HINT, "bad_mac": "That signature did not match. " + SIGNED_HINT,
                 "stale": "That command is outside the allowed time window; send it again.",
                 "replay": "That counter was already used; use a higher one."}


class Bridge:
    def __init__(self, config: dict, transport, registry=None, clock=None, *, pairing: Optional[Pairing] = None,
                 audit: Optional[Audit] = None, client_factory=ControlClient, limiter=None,
                 pulse: "Optional[bridge_state.BridgeState]" = None) -> None:
        if registry is None:
            from halo_harness.remote import registry as registry_mod
            registry = registry_mod
        self.cfg, self.transport, self.registry = config, transport, registry
        self.clock = clock or time
        self.linked = config.get("identity_model") == "linked"
        self.own_aci = str(config.get("own_aci") or "")
        self.pairing = pairing or Pairing(transport=transport, clock=self.clock.time,
                                          ttl=int(config.get("pair_code_ttl_s") or 600), trust_needed=not self.linked)
        self.audit = audit or Audit(clock=self.clock.time)
        self.client_factory = client_factory
        self.limiter = limiter or RateLimiter(int(config.get("rate_per_minute") or 30), self.clock.monotonic)
        self.window = int(config.get("stale_window_s") or signing.WINDOW_S)
        self.inbox: "queue.Queue" = queue.Queue()
        self.rts: dict = {}
        self.pulse = pulse  # the CLI's bridge.json writer; tests leave it None
        self._stop_path = bridge_state.stop_path() if pulse is not None else None

    # ---- loop ---------------------------------------------------------------
    def run(self, stop: threading.Event, tick: float = 0.25) -> "Bridge":
        self.transport.set_sink(self.inbox.put)
        if self.pulse is not None:
            self.pulse.write("starting")
        self.transport.start()
        try:
            while not stop.is_set():
                self.step(tick)
                if self._stop_path is not None and self._stop_path.exists():
                    break  # `halo remote signal off` (or /remote Off) asked for it
        finally:
            self.shutdown()
            if self.pulse is not None:
                self.pulse.write("stopped")
        return self

    def step(self, timeout: float = 0.25) -> None:
        try:
            item = self.inbox.get(timeout=timeout)
        except queue.Empty:
            item = None
        try:
            if item is not None:
                self.handle(item)
            self.pairing.service(self.transport)
        except Exception:
            pass  # one bad item must never end the daemon

    def shutdown(self) -> None:
        for rt in self.rts.values():
            sess.detach(self, rt)
        self.transport.stop()

    def handle(self, item: dict) -> None:
        kind = item.get("kind")
        if kind == "envelope":
            self.on_envelope(item)
        elif kind == "feed":
            rt = self.rts.get(item["aci"])
            if rt is not None and item["gen"] == rt.gen:
                sess.on_feed(self, rt, item["frame"])
        elif kind == "feed_closed":
            rt = self.rts.get(item["aci"])
            if rt is not None and item["gen"] == rt.gen:
                sess.detach(self, rt)
                self.say(rt.aci, "The attached session ended. /sessions lists the live ones.")
        elif kind == "notice":
            self.on_notice(item)

    def on_notice(self, item: dict) -> None:
        name = item.get("name")
        if name == "rate_limited":
            wait = float(item.get("retry_after") or 0)
            tok = f" Captcha token: {item['token']}" if item.get("token") else ""
            self.pairing.add_notice("rate_limited", "", f"Signal rate limit: sending paused for {int(wait)} s.{tok}")
            if self.pulse is not None:
                self.pulse.write("rate-limited", self.clock.time() + wait)
        elif self.pulse is not None and name in ("connected", "disconnected"):
            self.pulse.write("connected" if name == "connected" else "starting")

    # ---- sending --------------------------------------------------------------
    def rt(self, aci: str) -> PeerRT:
        if aci not in self.rts:
            self.rts[aci] = PeerRT(aci, str(self.cfg.get("verbosity") or "loud"))
        return self.rts[aci]

    def say(self, aci: str, text: str, *, markdown: bool = False, state: Optional[dict] = None) -> None:
        if not text or not text.strip():
            return
        out = render.render_markdown(text, state) if markdown else render.render_plain(text)
        for i, m in enumerate(out.messages):
            if m.text.strip():
                self._send(aci, m.text, out.attachment if i == 0 else None, m.styles)

    def _send(self, aci: str, text: str, attachment=None, styles=None) -> None:
        try:
            self.transport.send(aci, text, attachment=attachment, styles=styles)
        except UntrustedKey:
            self.pairing.block(aci, self.safe_safety_number(aci))
        except RateLimited:
            pass  # the transport's notice already told the owner
        except SignalError:
            pass

    def safe_safety_number(self, aci: str) -> Optional[str]:
        try:
            return self.transport.safety_number(aci)
        except SignalError:
            return None

    # ---- inbound -----------------------------------------------------------------------
    def on_envelope(self, item: dict) -> None:
        env = item.get("envelope") or {}
        aci, number, ts = env.get("sourceUuid"), env.get("sourceNumber"), env.get("timestamp")
        msg, atts = None, []
        if self.linked:  # Note to Self: only the account's own sync to itself counts
            sent = (env.get("syncMessage") or {}).get("sentMessage")
            if not isinstance(sent, dict) or sent.get("destinationUuid") != self.own_aci:
                return
            aci, msg, atts = self.own_aci, sent.get("message"), sent.get("attachments") or []
        elif env.get("dataMessage") is not None:
            dm = env["dataMessage"]
            msg, atts = dm.get("message"), dm.get("attachments") or []
        if not aci:
            return
        if item.get("exception"):  # the untrusted-identity notification: never answered
            self.on_untrusted(aci, number)
            return
        if msg is None and not atts:
            return  # typing, receipts, sync of other kinds: dropped without a trace
        peer = self.pairing.peer(aci)
        if peer is None:
            self.on_stranger(aci, number, msg or "", atts)
        else:
            self.on_peer(peer, number, ts, msg or "", atts)

    def on_untrusted(self, aci: str, number) -> None:
        if self.pairing.is_paired(aci):
            self.pairing.block(aci, self.safe_safety_number(aci))
        else:
            self.contact(aci, number)

    def contact(self, aci: str, number) -> None:
        if not any(r["aci"] == aci for r in self.pairing.pending()):
            self.pairing.note_contact(aci, number, self.safe_safety_number(aci))

    def on_stranger(self, aci: str, number, text: str, atts: list) -> None:
        self.transport.take_attachments(atts, False)
        res = self.pairing.redeem(aci, text, number)
        if res.status == "paired":
            phrase = signing.secret_to_phrase(res.secret)
            self.say(aci, "Paired. Signing secret (shown once):\n" + phrase + "\n\n"
                     + signing.pair_uri(res.secret, aci) + "\n\nEnd each command with ' #<counter>:<mac>'.")
            self.audit.record(aci, 0, "pairing-code", "pair", "paired")
        elif res.status == "ignored":
            self.contact(aci, number)

    def on_peer(self, peer: dict, number, ts, msg: str, atts: list) -> None:
        aci = peer["aci"]
        text = self.transport.take_attachments(atts, not peer.get("blocked_until_reverified")) or msg
        if peer.get("blocked_until_reverified"):
            self.audit.record(aci, 0, text, "refused", "blocked")
            return
        verdict = self.limiter.allow(aci)
        if verdict != OK:
            self.audit.record(aci, 0, text, "refused", "rate_limited")
            if verdict == DROP_NOTIFY:
                self.say(aci, "Too many commands; slow down. Further commands this minute are dropped.")
            return
        counter, shown = 0, text
        if peer.get("signed", True):
            sg = peer.get("signing") or {}
            v = signing.verify(bytes.fromhex(sg.get("secret_hex") or ""), sg.get("counter", 0), text, ts,
                               self.clock.time(), self.window)
            if not v.ok:
                self.audit.record(aci, v.counter, text, "refused", v.reason)
                self.say(aci, SIGN_REFUSALS.get(v.reason, SIGNED_HINT))
                return
            counter, shown = v.counter, v.text
            self.pairing.advance_counter(aci, counter)
        try:
            if ts:
                self.transport.send_receipt(aci, ts)
        except SignalError:
            pass
        kind, outcome = commands.route(self, self.rt(aci), shown)
        self.audit.record(aci, counter, shown, kind, outcome)


def run_bridge(config: dict, transport, registry=None, clock=None, *, stop: Optional[threading.Event] = None,
               **kw) -> Bridge:
    """Run the bridge until `stop` is set (forever when None)."""
    bridge = Bridge(config, transport, registry, clock, **kw)
    return bridge.run(stop or threading.Event())
