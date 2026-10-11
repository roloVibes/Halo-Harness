"""tests.helpers.signal_transport_rig -- a SignalTransport over the fake
signal-cli child (`Rig`) and an `expect` raise-checker, shared by the two
transport test modules."""
from __future__ import annotations

import queue
import time

from halo_harness.remote.signal_transport import SignalTransport
from tests.helpers.fake_signal_cli import FakeSignal


def expect(ctx, name, exc, fn):
    """Run `fn`; check it raised `exc`; return the exception (or None)."""
    try:
        fn()
    except exc as e:
        ctx.check(name, True)
        return e
    except Exception as e:
        ctx.check(f"{name} (got {type(e).__name__})", False)
        return None
    ctx.check(name, False)
    return None


class Rig:
    def __init__(self, **over):
        self.fake = FakeSignal()
        self.cfg = self.fake.config(**{k: v for k, v in over.items() if k not in ("backoff", "typing_interval")})
        self.q: "queue.Queue" = queue.Queue()
        self.t = SignalTransport(self.cfg, backoff=over.get("backoff", (0.02, 0.04)),
                                 typing_interval=over.get("typing_interval", 0.05), request_timeout=5.0)
        self.t.set_sink(self.q.put)
        self.t.start()
        assert self.t.wait_connected(15), "fake signal-cli did not start"
        time.sleep(0.15)  # let the subscribeReceive request land

    def items(self, kind=None, name=None) -> list:
        out = []
        while True:
            try:
                it = self.q.get_nowait()
            except queue.Empty:
                return [i for i in out if kind in (None, i["kind"]) and name in (None, i.get("name"))]
            out.append(it)

    def next(self, kind="envelope", timeout=5.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                it = self.q.get(timeout=0.1)
            except queue.Empty:
                continue
            if it["kind"] == kind:
                return it
        return None

    def close(self):
        self.t.stop()
