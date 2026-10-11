"""tests.test_remote_signal_io -- Halo 2.0.9 round 3: the rest of the signal-cli
client (`halo_harness/remote/signal_transport.py`, `signal_calls.py`) against the
fake signal-cli: the error-code map, the attachment rules (inbound text only,
downloads deleted; outbound by data URI, nothing on disk) and the tcp daemon client.
"""
from __future__ import annotations

import base64
import queue
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from halo_harness.remote import render
from halo_harness.remote import signal_errors as E
from halo_harness.remote.signal_transport import SignalTransport
from tests.helpers.fake_signal_cli import FakeSignal, attachment, data_message
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.signal_rig import ACI_A, Home, wait_for
from tests.helpers.signal_transport_rig import Rig, expect

test, TESTS = new_registry()


@test
def test_error_code_map(ctx: Ctx):
    r = Rig()
    try:
        def inject(code, data=None, method="send"):
            r.fake.order(op="fail", method=method, code=code, times=1, data=data)
            time.sleep(0.15)

        inject(-4)
        try:
            r.t.send(ACI_A, "x")
            ctx.check("-4 is UntrustedKey", False)
        except E.UntrustedKey as e:
            ctx.check("-4 is UntrustedKey", e.code == -4)
        inject(-1)
        e = expect(ctx, "-1 is UserFailure", E.UserFailure, lambda: r.t.send(ACI_A, "x"))
        ctx.check("-1 carries its code", e is not None and e.code == -1)
        inject(-6)
        e = expect(ctx, "-6 is CaptchaRejected", E.CaptchaRejected, lambda: r.t.send(ACI_A, "x"))
        ctx.check("-6 carries its code", e is not None and e.code == -6)
        inject(-32601)
        e = expect(ctx, "an unmapped code is a SignalError", E.SignalError, lambda: r.t.send(ACI_A, "x"))
        ctx.check("an unmapped code keeps its number", e is not None and type(e) is E.SignalError and e.code == -32601)
        r.items()
        inject(-5, {"results": [{"type": "RATE_LIMIT_FAILURE", "token": "tok-123", "retryAfterSeconds": 30}]})
        try:
            r.t.send(ACI_A, "x")
            ctx.check("-5 is RateLimited", False)
        except E.RateLimited as e:
            ctx.check("-5 is RateLimited with retry_after and the captcha token",
                      e.code == -5 and e.retry_after == 30 and e.token == "tok-123")
        notes = r.items("notice", "rate_limited")
        ctx.check("a rate_limited notice carries the token", notes and notes[0]["token"] == "tok-123" and notes[0]["retry_after"] == 30)
        before = len(r.fake.requests("send"))
        try:
            r.t.send(ACI_A, "again")
            ctx.check("sending is paused while rate limited", False)
        except E.RateLimited:
            ctx.check("sending is paused while rate limited", len(r.fake.requests("send")) == before)
        ctx.check("rate_limited() reports the seconds left", 0 < r.t.rate_limited() <= 30)
        r.t.submit_captcha("tok-123", "signalcaptcha://x")
        ctx.check("a submitted captcha reopens sending", r.t.rate_limited() == 0
                  and r.t.send(ACI_A, "ok")["results"][0]["type"] == "SUCCESS")
        ctx.check("errors do not depend on the message text", E.error_from({"code": -4, "message": "whatever"}).code == -4
                  and isinstance(E.error_from({"code": -4, "message": "rate limit"}), E.UntrustedKey))
        ctx.check("a -5 with no data defaults to a 60 s pause", E.error_from({"code": -5, "message": "x"}).retry_after == 60.0)
    finally:
        r.close()


@test
def test_attachments_in_and_out(ctx: Ctx):
    with Home():
        r = Rig()
        try:
            att_dir = Path(r.cfg["data_dir"]) / "attachments"
            att_dir.mkdir(parents=True, exist_ok=True)
            (att_dir / "AAA111").write_text("a long prompt typed on the phone", encoding="utf-8")
            (att_dir / "BBB222").write_bytes(b"\x89PNG not text")
            (att_dir / "CCC333").write_text("second text file", encoding="utf-8")
            outside = Path(tempfile.mkdtemp(prefix="att-outside-")) / "keep.txt"
            outside.write_text("must survive", encoding="utf-8")
            atts = [attachment("BBB222", "image/png"), attachment("AAA111", "text/x-signal-plain"),
                    attachment("CCC333", "text/x-signal-plain"), attachment("../../" + outside.name, "text/x-signal-plain"),
                    attachment("MISSING9", "text/x-signal-plain"), {"contentType": "text/x-signal-plain"}]
            text = r.t.take_attachments(atts, True)
            ctx.check("the first text/x-signal-plain attachment is the prompt text", text == "a long prompt typed on the phone")
            ctx.check("every downloaded attachment is deleted after reading",
                      list(att_dir.iterdir()) == [])
            ctx.check("an id with path separators is ignored, never followed", outside.exists())
            (att_dir / "DDD444").write_text("ignored text", encoding="utf-8")
            ctx.check("with want_text False nothing is read but the file is still deleted",
                      r.t.take_attachments([attachment("DDD444", "text/x-signal-plain")], False) is None
                      and not (att_dir / "DDD444").exists())
            (att_dir / "EEE555").write_text("not read", encoding="utf-8")
            ctx.check("a non-text attachment is never read",
                      r.t.take_attachments([attachment("EEE555", "application/pdf")], True) is None
                      and not (att_dir / "EEE555").exists())
            ctx.check("no attachments at all is fine", r.t.take_attachments([], True) is None
                      and r.t.take_attachments(None, True) is None)
            before = sorted(p.name for p in Path(r.cfg["data_dir"]).rglob("*"))
            long_text = "word " * 2000
            out = render.render_plain(long_text)
            r.t.send(ACI_A, out.messages[0].text, attachment=out.attachment)
            p = r.fake.requests("send")[-1]["params"]
            uri = p["attachment"][0]
            head = "data:text/plain;filename=reply.txt;base64,"
            ctx.check("a long reply goes out as a data: URI attachment", uri.startswith(head))
            ctx.check("the attachment decodes to the whole reply",
                      base64.b64decode(uri[len(head):]).decode("utf-8").strip() == long_text.strip())
            ctx.check("nothing was written to disk for the outbound attachment",
                      sorted(p.name for p in Path(r.cfg["data_dir"]).rglob("*")) == before)
        finally:
            r.close()


@test
def test_tcp_daemon_client(ctx: Ctx):
    fake = FakeSignal()
    portfile = fake.root / "port"
    proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve().parent / "helpers" / "fake_signal_cli.py"),
                             "--receive-mode", "manual", "--fake-ctl", str(fake.ctl), "--fake-log", str(fake.log),
                             "--fake-listen", "0", "--fake-portfile", str(portfile)],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t = None
    try:
        ctx.check("the fake daemon is listening", wait_for(lambda: portfile.exists() and portfile.read_text().strip(), 15))
        cfg = fake.config(transport="tcp", tcp=f"127.0.0.1:{portfile.read_text().strip()}")
        q: "queue.Queue" = queue.Queue()
        t = SignalTransport(cfg, backoff=(0.05,), request_timeout=5.0)
        t.set_sink(q.put)
        t.start()
        ctx.check("the tcp client connects without spawning anything", t.wait_connected(10))
        time.sleep(0.2)
        ctx.check("it subscribes (manual mode) and sends over the socket",
                  len(fake.requests("subscribeReceive")) == 1 and t.send(ACI_A, "over tcp")["results"][0]["type"] == "SUCCESS")
        ctx.check("the daemon was not given a spawn command", fake.argvs()[0].count("jsonRpc") == 0)
        fake.emit(data_message(ACI_A, "from the daemon", 9))
        got = None
        end = time.monotonic() + 5
        while time.monotonic() < end and got is None:
            try:
                it = q.get(timeout=0.2)
            except queue.Empty:
                continue
            got = it if it["kind"] == "envelope" else None
        ctx.check("receive works over tcp", got is not None and got["envelope"]["dataMessage"]["message"] == "from the daemon")
    finally:
        if t is not None:
            t.stop()
        proc.kill()
        proc.wait(5)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
