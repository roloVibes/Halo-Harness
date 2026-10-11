"""tests.helpers.bridge_rig -- a running Signal bridge over one or more real
control sockets (round 2's `Rig`: real Controller + FakeSession + ControlServer)
with a stub transport, plus a paired fake phone.

    with Harness(sessions=2) as h:
        h.send("/sessions")            # as the paired phone (signed if h.signed)
        h.wait_text("1. ")             # wait for a reply containing text
"""
from __future__ import annotations

import os
import threading
import time

from halo_harness.remote import signing
from halo_harness.remote.bridge import Bridge
from tests.helpers.fake_signal_cli import data_message, sync_sent
from tests.helpers.remote_rig import Rig
from tests.helpers.signal_rig import ACI_A, SAFETY_A, StubTransport, now_ms, pair_peer, wait_for


class StubRegistry:
    def __init__(self) -> None:
        self.entries: list = []

    def list_live(self) -> list:
        return list(self.entries)


class Harness:
    def __init__(self, sessions: int = 1, signed: bool = False, clock=None, peer: str = ACI_A, **cfg) -> None:
        self.peer = peer
        self.linked = cfg.get("identity_model") == "linked"
        self.rigs = [Rig(session_id=f"fakesession{i + 1:020d}") for i in range(sessions)]
        self.registry = StubRegistry()
        for i, rig in enumerate(self.rigs):
            self.registry.entries.append({
                "session_id": rig.session.log.session_id, "cwd": str(rig.cwd), "pid": os.getpid(),
                "endpoint": rig.server.endpoint, "token": rig.server.token, "title": f"Session {i + 1}",
                "started": 1000.0 + i, "kind": "tui"})
        self.tr = StubTransport()
        self.bridge = Bridge({"rate_per_minute": 100, **cfg}, self.tr, self.registry, clock)
        self.secret = pair_peer(self.bridge.pairing, peer, "+15555550101", SAFETY_A, signed=signed)
        self.signed, self.counter = signed, 0
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.bridge.run, args=(self.stop, 0.05), daemon=True)
        self.thread.start()

    @property
    def rig(self) -> Rig:
        return self.rigs[-1]

    def send(self, text: str, aci=None, ts=None) -> str:
        aci = aci or self.peer
        ts = ts if ts is not None else now_ms()
        if self.signed and aci == self.peer:
            self.counter += 1
            text = signing.sign(self.secret, self.counter, text)
        self.tr.deliver(sync_sent(aci, text, ts) if self.linked and aci == self.peer else data_message(aci, text, ts))
        return text

    def texts(self) -> list:
        return self.tr.texts(self.peer)

    def joined(self) -> str:
        return "\n".join(self.texts())

    def wait_text(self, needle: str, timeout: float = 8.0) -> bool:
        return wait_for(lambda: needle in self.joined(), timeout)

    def wait_idle(self, rig=None, turns: int = 1, timeout: float = 8.0) -> bool:
        r = rig or self.rig
        return wait_for(lambda: r.session.turn_count >= turns and not r.session.busy, timeout)

    def close(self) -> None:
        self.stop.set()
        self.thread.join(5)
        for rig in reversed(self.rigs):
            rig.close()

    def __enter__(self) -> "Harness":
        return self

    def __exit__(self, *exc) -> bool:
        self.close()
        return False


def settle(seconds: float = 0.3) -> None:
    time.sleep(seconds)
