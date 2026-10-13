"""tests.test_remote_bridge_auth -- Halo 2.0.9 round 3: the bridge's
authentication paths. Signed commands (good, unsigned, tampered, replayed,
stale (which burns its counter), `signed: false`), the read receipt only after every check passes, the
hashed audit line, Note to Self filtering, that no message content lands in
any file under the scratch homes, and one end-to-end run through the REAL
transport against the fake signal-cli child (contact request -> approve ->
code -> signed command -> reply).
"""
from __future__ import annotations

import base64
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from halo_harness.remote import signing
from halo_harness.remote.audit import command_hash
from halo_harness.remote.bridge import Bridge
from halo_harness.remote.signal_transport import SignalTransport
from tests.helpers.bridge_rig import Harness, StubRegistry, settle
from tests.helpers.fake_signal_cli import FakeSignal, data_message, attachment, sync_sent, untrusted_notice
from tests.helpers.remote_rig import Rig
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.signal_rig import ACI_A, ACI_B, SAFETY_A, SENTINEL, now_ms, wait_for

test, TESTS = new_registry()
OWN = "00000000-0000-4000-8000-0000000000aa"


@test
def test_signed_commands(ctx: Ctx):
    with Harness(signed=True) as h:
        h.send("/remote status")
        ctx.check("a good signed command is answered", h.wait_text("Paired as 00000000") and "signing on" in h.joined())
        ctx.check("the counter is stored", h.bridge.pairing.peer(ACI_A)["signing"]["counter"] == 1)
        n = len(h.texts())
        h.tr.deliver(data_message(ACI_A, "/remote status", now_ms()))
        ctx.check("an unsigned command is refused with the format", wait_for(lambda: len(h.texts()) == n + 1)
                  and "#<counter>:<mac>" in h.texts()[-1])
        good = signing.sign(h.secret, 2, "/remote status")
        h.tr.deliver(data_message(ACI_A, good.replace("/remote status", "/remote unpair"), now_ms()))
        ctx.check("a tampered command is refused and does nothing", wait_for(lambda: "did not match" in h.joined())
                  and h.bridge.pairing.is_paired(ACI_A))
        h.tr.deliver(data_message(ACI_A, good, now_ms()))
        ctx.check("counter 2 is accepted", wait_for(lambda: h.joined().count("Paired as") == 2))
        h.tr.deliver(data_message(ACI_A, good, now_ms()))
        ctx.check("the same message again is a replay and is refused with a notice",
                  wait_for(lambda: "already used" in h.joined()) and h.joined().count("Paired as") == 2)
        h.tr.deliver(data_message(ACI_A, signing.sign(h.secret, 1, "/remote help"), now_ms()))
        ctx.check("a lower counter is refused too", wait_for(lambda: h.joined().count("already used") == 2))
        old = signing.sign(h.secret, 50, "/remote status")
        h.tr.deliver(data_message(ACI_A, old, now_ms() - 10 * 60 * 1000))
        ctx.check("a command older than 5 minutes is refused", wait_for(lambda: "outside the allowed time window" in h.joined()))
        ctx.check("a stale command with a genuine signature burns its counter",
                  wait_for(lambda: h.bridge.pairing.peer(ACI_A)["signing"]["counter"] == 50))
        h.tr.deliver(data_message(ACI_A, old, now_ms()))
        ctx.check("the same bytes re-sent with a fresh timestamp are a replay, not a command",
                  wait_for(lambda: h.joined().count("already used") == 3) and h.joined().count("Paired as") == 2)
        h.tr.deliver(data_message(ACI_A, signing.sign(h.secret, 51, "/remote status"), now_ms()))
        ctx.check("re-signed with a higher counter it passes", wait_for(lambda: h.joined().count("Paired as") == 3))
        ctx.check("a read receipt went out only for the three accepted commands", len(h.tr.receipts) == 3)
        h.bridge.pairing.set_signed(ACI_A, False)
        h.tr.deliver(data_message(ACI_A, "/remote status", now_ms()))
        ctx.check("signed: false skips the check (layers 1-2 remain)", wait_for(lambda: h.joined().count("Paired as") == 4)
                  and "signing off" in h.texts()[-1])
        h.tr.deliver(data_message(ACI_B, "/remote status", now_ms()))
        settle()
        ctx.check("a different sender is still never answered", h.tr.texts(ACI_B) == [])


@test
def test_audit_line_is_a_hash(ctx: Ctx):
    with Harness(signed=True) as h:
        h.send("/remote status")
        h.send(f"hello {SENTINEL}")
        h.wait_idle()
        h.tr.deliver(data_message(ACI_A, "no signature here", now_ms()))
        wait_for(lambda: len(h.bridge.audit.lines()) >= 3)
        rows = h.bridge.audit.lines()
        ctx.check("one line per command, refusals included", [(r["kind"], r["outcome"]) for r in rows]
                  == [("cmd:remote", "ok"), ("prompt", "ok"), ("refused", "unsigned")])
        ctx.check("a line has exactly ts, peer, h, kind, outcome", all(set(r) == {"ts", "peer", "h", "kind", "outcome"} for r in rows))
        ctx.check("h is sha256(aci|counter|text)[:16] of the verified text",
                  rows[0]["h"] == command_hash(ACI_A, 1, "/remote status") and rows[1]["h"] == command_hash(ACI_A, 2, f"hello {SENTINEL}")
                  and len(rows[0]["h"]) == 16)
        ctx.check("peer is the ACI prefix", rows[0]["peer"] == ACI_A[:8])
        raw = h.bridge.audit.path.read_text(encoding="utf-8")
        ctx.check("no text of any command is in the audit file", SENTINEL not in raw and "remote status" not in raw)
        if os.name != "nt":
            ctx.check("audit.jsonl is 0600", h.bridge.audit.path.stat().st_mode & 0o777 == 0o600)


@test
def test_no_message_content_at_rest(ctx: Ctx):
    with Harness(signed=True) as h:
        h.send(f"first prompt {SENTINEL}")
        h.wait_idle()
        h.counter += 1
        h.tr.attachment_text["ATT1"] = signing.sign(h.secret, h.counter, f"{SENTINEL} typed as a long attachment")
        h.tr.deliver(data_message(ACI_A, "(cut at 2000 bytes)", now_ms(), attachments=[attachment("ATT1", "text/x-signal-plain")]))
        h.wait_idle(turns=2)
        h.send("/tail 5")
        h.wait_text("ASSISTANT")
        h.send("/status")
        h.tr.deliver(data_message(ACI_B, f"stranger says {SENTINEL}", now_ms()))
        h.tr.deliver(untrusted_notice(ACI_B, "+15555550102", now_ms()))
        settle(0.5)
        ctx.check("the sentinel did flow through the bridge (the test is live)",
                  SENTINEL in h.joined() and h.rig.session.turn_count == 2)
        ctx.check("the downloaded attachment was discarded after reading", "ATT1" in h.tr.discarded)
        ctx.check("the stranger was not answered", h.tr.texts(ACI_B) == [])
        home = Path(os.environ["BRIDGE_TEST_HOME"])
        needles = [SENTINEL.encode(), base64.b64encode(SENTINEL.encode())[:12], SENTINEL.upper().encode()]
        hits, scanned = [], 0
        for root in (home, h.rig.cwd):
            for f in root.rglob("*"):
                if f.is_file():
                    scanned += 1
                    data = f.read_bytes()
                    if any(n in data for n in needles):
                        hits.append(str(f))
        ctx.check("files exist under the scratch home to scan (peers, pending, audit)", scanned >= 3)
        ctx.check("no file under the scratch home or the session cwd holds a message", hits == [])
        ctx.check("peers.json and pending.json hold no text",
                  "stranger says" not in (home / ".halo" / "remote" / "pending.json").read_text(encoding="utf-8"))


@test
def test_receipts_only_after_the_checks(ctx: Ctx):
    with Harness(signed=True) as h:
        h.tr.deliver(data_message(ACI_B, "hello", now_ms()))
        h.tr.deliver(data_message(ACI_A, "unsigned", now_ms()))
        h.tr.deliver(data_message(ACI_A, "/x #1:00000000", now_ms()))
        settle(0.4)
        ctx.check("a stranger, an unsigned and a forged command get no receipt", h.tr.receipts == [])
        h.send("/remote status")
        ctx.check("a command that passes gets the read receipt",
                  wait_for(lambda: len(h.tr.receipts) == 1) and h.tr.receipts[0][2] == "read")


@test
def test_note_to_self_filter(ctx: Ctx):
    with Harness(identity_model="linked", own_aci=OWN, peer=OWN) as h:
        h.send("/remote status")
        ctx.check("a Note-to-Self message from the account itself is a command", h.wait_text("Paired as 00000000"))
        ctx.check("the reply goes to the own ACI", h.tr.sent and h.tr.sent[0]["to"] == OWN)
        n = len(h.tr.sent)
        h.tr.deliver(data_message(ACI_B, "/remote status", now_ms()))
        h.tr.deliver(sync_sent(OWN, "/remote status", now_ms(), dest_uuid=ACI_B))
        h.tr.deliver({"envelope": {"sourceUuid": OWN, "timestamp": 1, "syncMessage": {"type": "CONTACTS_SYNC"}}})
        settle(0.4)
        ctx.check("another sender, a sync to someone else and other sync kinds are dropped", len(h.tr.sent) == n)
        ctx.check("and leave no contact request behind", h.bridge.pairing.pending() == [])


@test
def test_end_to_end_with_fake_signal_cli(ctx: Ctx):
    fake = FakeSignal()
    rig = Rig(session_id="fakesession" + "7" * 21)
    reg = StubRegistry()
    reg.entries.append({"session_id": rig.session.log.session_id, "cwd": str(rig.cwd), "pid": os.getpid(),
                        "endpoint": rig.server.endpoint, "token": rig.server.token, "title": "E2E", "started": 1.0})
    t = SignalTransport(fake.config(), backoff=(0.05,), typing_interval=0.2, request_timeout=5.0)
    bridge = Bridge({"rate_per_minute": 100}, t, reg)
    stop = threading.Event()
    th = threading.Thread(target=bridge.run, args=(stop, 0.05), daemon=True)
    th.start()
    try:
        ctx.check("the transport is up", t.wait_connected(15))
        time.sleep(0.3)
        fake.order(op="identity", uuid=ACI_A, number="+15555550101", safetyNumber=SAFETY_A, trust="UNTRUSTED")
        time.sleep(0.2)
        fake.order(op="untrusted", uuid=ACI_A, number="+15555550101", held_text="hi there")
        ctx.check("the stranger becomes a contact request with the safety number from listIdentities",
                  wait_for(lambda: [r["safety_number"] for r in bridge.pairing.pending()] == [SAFETY_A], 8))
        ctx.check("signal-cli was never asked to send to the stranger", fake.requests("send") == [])
        ap = bridge.pairing.approve(ACI_A)
        tr = fake.requests("trust")
        ctx.check("approve called trust with the safety number as plain digits",
                  tr and tr[-1]["params"] == {"recipient": ACI_A, "verifiedSafetyNumber": "".join(SAFETY_A.split())})
        time.sleep(0.5)
        ctx.check("the message redelivered after trust is not a guess and gets no reply", fake.requests("send") == []
                  and [r["attempts"] for r in bridge.pairing.pending()] == [0])
        fake.emit(data_message(ACI_A, ap.code, now_ms(), "+15555550101"))
        ctx.check("the pairing code gets the one 'Paired.' reply",
                  wait_for(lambda: any(r["params"]["message"].startswith("Paired.") for r in fake.requests("send")), 8))
        peer = bridge.pairing.peer(ACI_A)
        secret = bytes.fromhex(peer["signing"]["secret_hex"])
        fake.emit(data_message(ACI_A, signing.sign(secret, 1, "/status"), now_ms()))
        ctx.check("a signed /status attaches the session and answers with its status",
                  wait_for(lambda: any("Model: mock/fake" in r["params"]["message"] for r in fake.requests("send")), 10))
        sends = fake.requests("send")
        ctx.check("every reply went to the paired ACI only", all(r["params"]["recipient"] == [ACI_A] for r in sends))
        rc = fake.requests("sendReceipt")
        ctx.check("the read receipt was sent after the checks", rc and rc[-1]["params"]["type"] == "read")
        ctx.check("no message was written under the bridge's scratch home", not any(
            b"hi there" in f.read_bytes() or b"/status" in f.read_bytes()
            for f in Path(os.environ["BRIDGE_TEST_HOME"]).rglob("*") if f.is_file()))
    finally:
        stop.set()
        th.join(10)
        rig.close()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
