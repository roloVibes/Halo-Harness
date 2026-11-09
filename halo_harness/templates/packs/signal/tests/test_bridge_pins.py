"""tests.test_bridge_pins -- the bridge's pins from Halo's review and security passes, ported to the signal pack:
item 26 a stale signed message burns its counter; item 27 a sub-agent's text and turn_done never close the parent's
card; item 30 a refused subscribeReceive reaches the health file and the audit; item 31 a card whose send failed is
kept and sent again after the reconnect; item 33 a question answered at the keyboard does not swallow the next text;
item 101 a rate-limited signed message keeps its counter; item 108 superscript digits are not a session number;
security f2 a signing secret never goes into the chat; f4 a signed phone with no secret is refused; f5 the audit
rotates; f23 a registration PIN travels on stdin, never in argv. Run: python -m tests.test_bridge_pins"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

from halo_signal import errors as E
from halo_signal import signing
from tests.support import ACI_A, data_message, main, now_ms, registry, wait_for
from tests.rig import Phone

test, TESTS = registry()


@test
def test_item26_stale_burns_its_counter(ctx):
    with Phone() as p:
        p.pair()
        secret = p.b.pairing.set_signed(ACI_A, True)
        msg = signing.sign(secret, 1, "/signal")
        p.tr.deliver(data_message(ACI_A, msg, now_ms() - 900_000))
        p.wait("outside the allowed time window")
        p.text(msg)
        ctx.check("the same bytes later are a replay", p.wait("already used"))


@test
def test_item27_a_child_never_closes_the_parents_card(ctx):
    with Phone() as p:
        p.pair()
        p.text("please ask first")
        p.wait("echo hi")
        rt = p.b.rts[ACI_A]
        for ev in ("text_chunk", "turn_done"):
            p.b.inbox.put({"kind": "feed", "aci": ACI_A, "gen": rt.gen,
                           "frame": {"event": ev, "data": {"text": "child says\n"}, "agent_id": "child-1"}})
        time.sleep(0.3)
        ctx.check("the card is still open and nothing of the child was relayed",
                  rt.permission and "child says" not in p.joined())


@test
def test_item30_subscribe_failed_reaches_health_and_audit(ctx):
    from halo_signal.health import Health
    with Phone() as p:
        h = Health(path=Path(p.home) / "h.json", stop=Path(p.home) / "nope")
        p.b.health = h
        p.b.handle({"kind": "notice", "name": "subscribe_failed", "code": -32601, "message": "Method not found"})
        ctx.check("the health line names it", "-32601" in h.line and h.state == "starting")
        ctx.check("an audit line", any(r["outcome"] == "subscribe_failed -32601" for r in p.b.audit.lines()))


@test
def test_item31_a_failed_card_is_kept_and_sent_again(ctx):
    with Phone() as p:
        p.pair()
        p.text("hello")
        p.wait("hello from the fake session")
        p.tr.send_error = E.IOFailure("link down")
        p.text("please ask first")
        rt = p.b.rts[ACI_A]
        ctx.check("the card is kept", wait_for(lambda: rt.undelivered, 3.0))
        p.tr.send_error = None
        p.b.inbox.put({"kind": "notice", "name": "connected"})
        ctx.check("and sent after the reconnect", p.wait("echo hi") and not rt.undelivered)


@test
def test_item33_a_question_answered_elsewhere(ctx):
    with Phone() as p:
        p.pair()
        p.text("a question for me")
        p.wait("which?")
        p.session().pending["question"] = []
        p.text("tell me more")
        ctx.check("the text is a prompt, not an answer", wait_for(
            lambda: len(p.session().submitted) == 2 and not p.session().answers, 3.0))


@test
def test_item101_and_108(ctx):
    with Phone(rate_per_minute=1) as p:
        p.pair()
        secret = p.b.pairing.set_signed(ACI_A, True)
        p.text(signing.sign(secret, 1, "/help"))
        p.wait("Chat commands")
        p.text(signing.sign(secret, 2, "/help"))
        ctx.check("the rate limit drops it", p.wait("Too many messages"))
        ctx.check("its counter stays unused", p.b.pairing.peer(ACI_A)["signing"]["counter"] == 1)
    with Phone() as p:
        p.pair()
        p.text("/attach ²")
        ctx.check("superscript digits are not a session number", p.wait("Usage: /attach <n>"))


@test
def test_f2_f4_signing_secrets(ctx):
    with Phone() as p:
        p.pair()
        secret = p.b.pairing.set_signed(ACI_A, True)
        ctx.check("the secret never went to the phone", secret.hex() not in p.joined()
                  and signing.secret_to_phrase(secret).split()[0] not in p.joined().split())
        from halo_signal import files
        with files.edit_json(p.b.pairing.peers_path, {}) as d:
            d["peers"][ACI_A]["signing"]["secret_hex"] = "short"
        p.text(signing.sign(secret, 1, "/help"))
        ctx.check("a signed phone with no usable secret is refused", p.wait("no usable signing secret"))


@test
def test_f5_the_audit_rotates(ctx):
    from halo_signal import audit
    with Phone() as p:
        a = p.b.audit
        a.path.parent.mkdir(parents=True, exist_ok=True)
        a.path.write_text("x" * (audit.MAX_BYTES + 1), encoding="utf-8")
        a.record(ACI_A, 0, "t", "prompt", "ok")
        ctx.check("the big file became .1 and a fresh one started", a.path.with_name("audit.jsonl.1").exists()
                  and len(a.lines()) == 1)


@test
def test_f23_the_pin_goes_on_stdin(ctx):
    from halo_signal.signalcli import rpc_once
    d = Path(tempfile.mkdtemp(prefix="signal-pin-"))
    fake = d / "fake_cli.py"
    fake.write_text("import json, sys\nopen(__file__ + '.argv', 'w').write(json.dumps(sys.argv))\n"
                    "line = sys.stdin.readline()\nreq = json.loads(line)\nopen(__file__ + '.stdin', 'w').write(line)\n"
                    "print(json.dumps({'jsonrpc': '2.0', 'id': req['id'], 'result': {}}), flush=True)\n", encoding="utf-8")
    cfg = {"binary": [sys.executable, str(fake)], "data_dir": str(d / "data")}
    got = rpc_once(cfg, "verify", {"pin": "246813579", "verificationCode": "1"}, timeout=20)
    ctx.check(f"the call answered ({got.message})", got.ok)
    ctx.check("the PIN is not in the argv", "246813579" not in Path(str(fake) + ".argv").read_text(encoding="utf-8"))
    ctx.check("it went on stdin", "246813579" in Path(str(fake) + ".stdin").read_text(encoding="utf-8"))
    ctx.check("nothing was written beside the pack", not list(Path(os.getcwd()).glob("*.argv")))


if __name__ == "__main__":
    raise SystemExit(main(TESTS))
