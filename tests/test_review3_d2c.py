"""tests.test_review3_d2c -- the 3.0.2.0 review fix pass, round D2 (Signal
bridge), part 3: pairing's trust queue, the transport's reader and
subscribe, and the changed-safety-number notice. No signal-cli is spawned.

  * review item 105  a trust step that fails for a non-network reason is finished, not retried forever
  * review item 106  a reader-loop exception drops and respawns the link; a failed subscribe respawns too
  * review item 107  one identity_changed notice per change, not per undecryptable message
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from halo_harness.remote import signal_errors as E
from halo_harness.remote.pairing import TRUST_TRIES, Pairing
from halo_harness.remote.signal_link import Link
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.signal_rig import ACI_A, SAFETY_A, SAFETY_B, FakeClock, Home, pair_peer, wait_for
from tests.test_review3_d2b import _connect, _transport

test, TESTS = new_registry()

class _CountingTrust:
    def __init__(self, error) -> None:
        self.error, self.calls = error, 0

    def trust(self, recipient, safety_number):
        self.calls += 1
        if self.error is not None:
            raise self.error


def _queued(clock) -> Pairing:
    p = Pairing(directory=tempfile.mkdtemp(prefix="d2-pair-"), clock=clock.time)
    p.note_contact(ACI_A, "+15555550101", SAFETY_A)
    p.approve(ACI_A)  # no transport: the trust step is queued
    return p


@test
def test_item105_trust_refused_for_other_reasons_is_finished(ctx: Ctx):
    clock = FakeClock()
    p = _queued(clock)
    tr = _CountingTrust(E.SignalError("internal error", -32603))
    for _ in range(5):
        p.service(tr)
    ctx.check(f"one attempt, then finished (got {tr.calls})", tr.calls == 1)
    ctx.check("the op is gone and the owner is told", not json.loads(p.pending_path.read_text())["ops"]
              and any(n["kind"] == "trust_failed" for n in p.notices()))


@test
def test_item105_network_failures_back_off_then_give_up(ctx: Ctx):
    clock = FakeClock()
    p = _queued(clock)
    tr = _CountingTrust(E.IOFailure("link closed"))
    for _ in range(10):
        p.service(tr)
    ctx.check(f"an -3 is retried with backoff, not every tick (got {tr.calls})", tr.calls == 1)
    for _ in range(TRUST_TRIES * 2):
        clock.now += 61
        p.service(tr)
    ctx.check(f"after {TRUST_TRIES} attempts the step is given up (got {tr.calls})", tr.calls == TRUST_TRIES)
    ctx.check("with a notice", any(n["kind"] == "trust_failed" for n in p.notices()))
    p2 = _queued(clock)
    tr2 = _CountingTrust(E.IOFailure("down"))
    p2.service(tr2)
    tr2.error = None
    clock.now += 61
    p2.service(tr2)
    ctx.check("a step that recovers completes", tr2.calls == 2 and not json.loads(p2.pending_path.read_text())["ops"])


@test
def test_item106_reader_exception_respawns_the_link(ctx: Ctx):
    sink: list = []
    t = _transport(sink)
    opened: list = []

    def fake_open():
        link = Link(io.BytesIO(b'{"jsonrpc":"2.0","id":[1],"result":1}\n{"jsonrpc":"2.0","id":{"a":1},"result":1}\n'),
                    io.BytesIO(), lambda: None)
        opened.append(link)
        return link
    real_read = t._read_loop

    def flaky_read(link):
        if len(opened) == 1:
            raise RuntimeError("reader blew up")
        real_read(link)
    t._open, t._read_loop = fake_open, flaky_read
    t.start()
    try:
        ok = wait_for(lambda: len(opened) >= 3, 5.0)
    finally:
        t.stop()
    names = [n.get("name") for n in sink]
    ctx.check(f"the link was respawned after the exception (opens {len(opened)})", ok)
    ctx.check("a disconnected notice followed the failure", "disconnected" in names)
    try:
        t._dispatch({"jsonrpc": "2.0", "id": [1, 2], "result": 1})
        ctx.check("an unhashable reply id is ignored", True)
    except TypeError:
        ctx.check("an unhashable reply id is ignored", False)


@test
def test_item106_failed_subscribe_respawns(ctx: Ctx):
    sink: list = []
    t = _transport(sink, receive_mode="manual")
    link = _connect(t, lambda req: {"error": {"code": -32601, "message": "Method not implemented"}})
    t._subscribe(link)
    ctx.check("subscribe_failed is surfaced", any(n.get("name") == "subscribe_failed" for n in sink))
    ctx.check("and the link is interrupted so the supervisor respawns it", link.interrupts == 1)


@test
def test_item107_one_identity_notice_per_change(ctx: Ctx):
    with Home():
        from tests.helpers.signal_rig import StubTransport
        p = Pairing(transport=StubTransport())
        pair_peer(p, ACI_A, "+15555550101", SAFETY_A)
        for _ in range(5):
            p.block(ACI_A, SAFETY_B)
        kinds = [n["kind"] for n in p.notices()]
        ctx.check(f"five undecryptable messages, one notice (got {kinds.count('identity_changed')})",
                  kinds.count("identity_changed") == 1)
        p.block(ACI_A, SAFETY_A.replace("1", "3"))
        ctx.check("a different new safety number is news again",
                  [n["kind"] for n in p.notices()].count("identity_changed") == 2)
        ctx.check("the pending safety number follows the newest", p.peer(ACI_A)["pending_safety_number"] == SAFETY_A.replace("1", "3"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
