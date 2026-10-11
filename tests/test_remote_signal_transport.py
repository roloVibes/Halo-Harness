"""tests.test_remote_signal_transport -- Halo 2.0.9 round 3: the signal-cli
JSON-RPC client (`halo_harness/remote/signal_transport.py`) against the fake
signal-cli child (tests/helpers/fake_signal_cli.py): spawn flags, receive,
send, the typing cadence, reconnect with backoff, the error-code map, and the
attachment rules (inbound text only, downloads deleted; outbound by data URI).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from halo_harness.remote import signal_errors as E
from halo_harness.remote.signal_link import build_argv
from halo_harness.remote.signal_transport import SignalTransport
from tests.helpers.fake_signal_cli import ACCOUNT, FakeSignal, data_message, sync_sent, untrusted_notice
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.signal_rig import ACI_A, wait_for
from tests.helpers.signal_transport_rig import Rig

test, TESTS = new_registry()


@test
def test_spawn_flags_and_subscribe(ctx: Ctx):
    r = Rig()
    try:
        argv = r.fake.argvs()[0]
        ctx.check("account and trust mode flags", argv[:4] == ["-a", ACCOUNT, "--trust-new-identities", "never"])
        ctx.check("scrub-log and the data dir come before the subcommand",
                  "--scrub-log" in argv and argv[argv.index("-d") + 1] == r.cfg["data_dir"]
                  and argv.index("-d") < argv.index("jsonRpc"))
        ctx.check("the jsonRpc subcommand carries the ignore flags",
                  all(f in argv[argv.index("jsonRpc"):] for f in ("--ignore-stories", "--ignore-avatars", "--ignore-stickers")))
        ctx.check("manual receive mode is passed", argv[-2:] == ["--receive-mode", "manual"])
        ctx.check("no read-receipt flag and no verbose flag", "--send-read-receipts" not in argv and "-v" not in argv)
        ctx.check("manual mode subscribes to receive", len(r.fake.requests("subscribeReceive")) == 1)
        ctx.check("a 'connected' notice reaches the sink", r.items("notice", "connected") != [])
        ctx.check("build_argv honours a binary path and extra args",
                  build_argv({"binary": "/opt/signal-cli/bin/signal-cli", "account": "+1", "data_dir": "/d",
                              "extra_args": ["--x"], "receive_mode": "on-start"})
                  == ["/opt/signal-cli/bin/signal-cli", "-a", "+1", "--trust-new-identities", "never", "--scrub-log",
                      "-d", "/d", "--x", "jsonRpc", "--ignore-stories", "--ignore-avatars", "--ignore-stickers",
                      "--receive-mode", "on-start"])
    finally:
        r.close()
    r2 = Rig(receive_mode="on-start")
    try:
        ctx.check("on-start mode does not call subscribeReceive", r2.fake.requests("subscribeReceive") == [])
        r2.fake.emit(data_message(ACI_A, "hi", 1))
        it = r2.next()
        ctx.check("on-start notifications arrive unwrapped",
                  it is not None and it["envelope"]["dataMessage"]["message"] == "hi")
    finally:
        r2.close()


@test
def test_receive_and_send(ctx: Ctx):
    r = Rig()
    try:
        r.fake.emit(data_message(ACI_A, "hello there", 1234, "+15555550101"))
        it = r.next()
        env = it["envelope"] if it else {}
        ctx.check("a subscription-wrapped receive is unwrapped into an envelope item",
                  it is not None and env.get("sourceUuid") == ACI_A and env["dataMessage"]["message"] == "hello there"
                  and it["account"] == ACCOUNT and it["exception"] is None)
        r.fake.emit(untrusted_notice(ACI_A, "+15555550101", 99))
        it = r.next()
        ctx.check("the untrusted-identity notification keeps its exception object",
                  it is not None and it["exception"]["type"] == "UntrustedIdentityException"
                  and "dataMessage" not in it["envelope"])
        res = r.t.send(ACI_A, "reply text")
        ctx.check("send returns signal-cli's result", res["results"][0]["type"] == "SUCCESS")
        p = r.fake.requests("send")[-1]["params"]
        ctx.check("send params: recipient list and message", p == {"message": "reply text", "recipient": [ACI_A]})
        r.t.send(ACI_A, "code", styles=["0:4:MONOSPACE"])
        ctx.check("textStyle ranges are passed", r.fake.requests("send")[-1]["params"]["textStyle"] == ["0:4:MONOSPACE"])
        r.t.send_receipt(ACI_A, 1234)
        ctx.check("sendReceipt: read type, target timestamp list",
                  r.fake.requests("sendReceipt")[-1]["params"] == {"recipient": ACI_A, "targetTimestamp": [1234], "type": "read"})
        r.fake.order(op="identity", uuid=ACI_A, number=None, safetyNumber="123 456", trust="UNTRUSTED")
        time.sleep(0.2)
        ctx.check("safety_number reads listIdentities", r.t.safety_number(ACI_A) == "123 456")
        ctx.check("an unknown recipient has no safety number", r.t.safety_number("nobody") is None)
        r.t.trust(ACI_A, "123456")
        ctx.check("trust sends verifiedSafetyNumber", r.fake.requests("trust")[-1]["params"]
                  == {"recipient": ACI_A, "verifiedSafetyNumber": "123456"})
        try:
            r.t.trust(ACI_A, "999999")
            ctx.check("a wrong safety number is a user error", False)
        except E.UserFailure as e:
            ctx.check("a wrong safety number is a user error (-1)", e.code == -1)
    finally:
        r.close()


@test
def test_linked_mode_note_to_self(ctx: Ctx):
    own = "00000000-0000-4000-8000-0000000000aa"
    r = Rig(identity_model="linked", own_aci=own)
    try:
        r.t.send(own, "to me")
        p = r.fake.requests("send")[-1]["params"]
        ctx.check("a linked account replies through noteToSelf", p == {"message": "to me", "noteToSelf": True})
        r.t.send_typing(own)
        r.t.send_receipt(own, 5)
        ctx.check("no typing or receipt is sent to ourselves", r.fake.requests("sendTyping") == []
                  and r.fake.requests("sendReceipt") == [])
        r.fake.emit(sync_sent(own, "note", 7))
        it = r.next()
        ctx.check("a Note-to-Self sync arrives as an envelope with the sentMessage",
                  it is not None and it["envelope"]["syncMessage"]["sentMessage"]["destinationUuid"] == own)
    finally:
        r.close()


@test
def test_typing_cadence(ctx: Ctx):
    r = Rig(typing_interval=0.05)
    try:
        r.t.typing.start(ACI_A)
        ctx.check("a second start for the same recipient is a no-op", r.t.typing.start(ACI_A) is False)
        ctx.check("typing repeats while the turn runs",
                  wait_for(lambda: len([x for x in r.fake.requests("sendTyping") if not x["params"].get("stop")]) >= 4, 5))
        r.t.typing.stop(ACI_A)
        ctx.check("stop sends one 'stop: true'",
                  wait_for(lambda: any(x["params"].get("stop") for x in r.fake.requests("sendTyping")), 5))
        time.sleep(0.2)
        n = len(r.fake.requests("sendTyping"))
        time.sleep(0.3)
        ctx.check("nothing is sent after stop", len(r.fake.requests("sendTyping")) == n)
        ctx.check("the last typing request is the stop", r.fake.requests("sendTyping")[-1]["params"].get("stop") is True)
        ctx.check("typing params carry the recipient list", r.fake.requests("sendTyping")[0]["params"]["recipient"] == [ACI_A])
        ctx.check("the keeper is idle", r.t.typing.active() == [])
    finally:
        r.close()


@test
def test_reconnect_with_backoff(ctx: Ctx):
    r = Rig(backoff=(0.05, 0.1))
    try:
        ctx.check("one connection so far", r.t.connects == 1)
        r.fake.order(op="exit")
        ctx.check("a child exit is noticed", wait_for(lambda: r.items("notice", "disconnected") != [] or r.t.connects > 1, 5))
        ctx.check("the child is respawned", wait_for(lambda: r.t.connects == 2 and r.t.connected, 15))
        ctx.check("the first backoff is the configured base", r.t.backoffs[0] == 0.05)
        time.sleep(0.2)
        ctx.check("manual mode re-subscribes after the respawn", len(r.fake.requests("subscribeReceive")) == 2)
        r.fake.emit(data_message(ACI_A, "after restart", 5))
        it = r.next()
        ctx.check("messages flow again", it is not None and it["envelope"]["dataMessage"]["message"] == "after restart")
        r.fake.order(op="fail", method="send", code=-3, times=1)
        time.sleep(0.2)
        try:
            r.t.send(ACI_A, "x")
            ctx.check("a -3 reply raises IOFailure", False)
        except E.IOFailure:
            ctx.check("a -3 reply raises IOFailure", True)
        ctx.check("a -3 reply makes the link reconnect", wait_for(lambda: r.t.connects == 3 and r.t.connected, 15))
        ctx.check("sending works after the reconnect", r.t.send(ACI_A, "again")["results"][0]["type"] == "SUCCESS")
    finally:
        r.close()
    cfg = FakeSignal().config(binary=["no-such-signal-cli-binary-xyz"])
    t = SignalTransport(cfg, backoff=(0.01, 0.02, 0.04))
    t.set_sink(lambda item: None)
    t.start()
    try:
        ctx.check("a binary that cannot start is retried with growing delays",
                  wait_for(lambda: len(t.backoffs) >= 6, 10))
        ctx.check("the delays grow then stay at the cap", t.backoffs[:3] == [0.01, 0.02, 0.04]
                  and all(d == 0.04 for d in t.backoffs[3:]))
        try:
            t.send(ACI_A, "x")
            ctx.check("sending while disconnected raises IOFailure", False)
        except E.IOFailure:
            ctx.check("sending while disconnected raises IOFailure", True)
    finally:
        t.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
