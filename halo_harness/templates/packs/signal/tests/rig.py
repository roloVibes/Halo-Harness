"""tests.rig -- a running bridge over the stub transport and the fake sessions, with a phone to text from.

    with Phone() as p:
        p.pair()                       # /signal pair's phrase, texted once (the untrusted first message, then it)
        p.text("hello")                # as the paired phone
        p.wait("hello from the fake")  # a reply containing it
"""

from __future__ import annotations

import threading

from tests.support import ACI_A, NUM_A, SAFETY, StubTransport, data_message, now_ms, untrusted, wait_for
from tests.fake_session import FakeSessions


class Phone:
    def __init__(self, *, transcribe=None, capture=None, clock=None, sessions=None, notes=False, home=None,
                 **cfg) -> None:
        import os
        import tempfile
        from halo_signal.bridge import Bridge
        self.home = home or tempfile.mkdtemp(prefix="signal-phone-home-")  # each phone's own data folder
        os.environ["BRIDGE_TEST_HOME"] = self.home
        self.tr = StubTransport()
        self.sessions = sessions or FakeSessions()
        self.heard: list = []

        def hear(path):
            self.heard.append(path)
            return ("make it blue", "") if transcribe is None else transcribe(path)
        kw = {"notes": False} if notes is False else ({"notes": notes} if notes not in (True, None) else {})
        self.b = Bridge({"rate_per_minute": 100, "pair_ttl_s": 600, **cfg}, self.tr, sessions=self.sessions,
                        clock=clock, transcribe=hear, capture=capture or (lambda sid: (None, "Studio is not open")),
                        live_lines=lambda: ["you@studio: 1 live session(s)", "Waiting on you: 0 (nothing)"], **kw)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.b.run, args=(self.stop, 0.02), daemon=True)
        self.thread.start()

    def pair(self, aci: str = ACI_A, number: str = NUM_A) -> str:
        phrase = self.b.pairing.invite()["phrase"]
        self.tr.identities[aci] = SAFETY
        self.tr.deliver(untrusted(aci, number, now_ms()))
        wait_for(lambda: self.tr.trusts, 3.0)
        self.text(phrase, aci, number)
        assert self.wait("Paired.", aci=aci), self.joined(aci)
        return phrase

    def text(self, text, aci: str = ACI_A, number: str = NUM_A, attachments=None) -> None:
        self.tr.deliver(data_message(aci, text, now_ms(), number, attachments=attachments))

    def texts(self, aci: str = ACI_A) -> list:
        return self.tr.texts(aci)

    def joined(self, aci: str = ACI_A) -> str:
        return "\n".join(self.texts(aci))

    def wait(self, needle: str, timeout: float = 6.0, aci: str = ACI_A) -> bool:
        return wait_for(lambda: needle in self.joined(aci), timeout)

    def session(self):
        rt = self.b.rts.get(ACI_A)
        sid = (rt.entry or {}).get("session_id") if rt else None
        return self.sessions.rows.get(sid)

    def close(self) -> None:
        self.stop.set()
        self.thread.join(5)

    def __enter__(self) -> "Phone":
        return self

    def __exit__(self, *exc) -> bool:
        self.close()
        return False
