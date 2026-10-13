"""tests.test_review3_d1b -- pins for the 3.0.2.0 review fix pass, round D1
(remote control core), part two:

  * review item 30  a refused subscribeReceive is retried, then surfaces as a
                    notice, an audit line and a `starting` pulse
  * review item 97  every pairing-code guess leaves an audit line; the first
                    wrong one leaves a notice
  * review item 98  the .ctl sweep keeps a sibling's young or owned socket
  * review item 99  `remote.pair_code_ttl_s` sets the issued code's lifetime
  * review item 100 the launchd agent restarts on failure only
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import plistlib
import socket
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from halo_harness.remote import signal_errors as E
from halo_harness.remote.bridge import Bridge
from tests.helpers.fake_signal_cli import data_message
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.signal_rig import ACI_A, ACI_B, SAFETY_A, SAFETY_B, Home, NoRegistry, StubTransport, now_ms

test, TESTS = new_registry()


def _audit_rows() -> list:
    from halo_harness.remote.signal_config import remote_dir
    p = remote_dir() / "audit.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


# ---- item 30 -------------------------------------------------------------------

def _transport(responses: list, transport: str = "stdio"):
    from halo_harness.remote.signal_transport import SignalTransport
    t = SignalTransport({"account": "+15555550100", "transport": transport,
                         "data_dir": tempfile.mkdtemp(prefix="d1-sig-")}, backoff=(0.01,))
    notices, sent, interrupts = [], [], []
    t.set_sink(notices.append)
    t._link = SimpleNamespace(interrupt=lambda: interrupts.append(1))
    t._connected.set()

    def request(method, params=None, timeout=None):
        sent.append((method, params))
        r = responses.pop(0) if responses else None
        if callable(r):
            r = r(t)
        if isinstance(r, Exception):
            raise r
        return r
    t.request = request
    return t, notices, sent, interrupts


@test
def test_item30_transport_retries_then_reports_subscribe_failed(ctx: Ctx):
    from halo_harness.remote.signal_transport import SUBSCRIBE_TRIES
    t, notices, sent, _ = _transport([E.UserFailure("busy", -1), 0])
    t._subscribe()
    ctx.check("a transient refusal is retried and nothing is reported", len(sent) == 2 and notices == [])
    ctx.check("stdio sends no account (the child is already bound to it)", sent[0] == ("subscribeReceive", {}))
    t, notices, sent, _ = _transport([E.SignalError("Method not found", -32601)])
    t._subscribe()
    ctx.check("a permanent rejection is not retried", len(sent) == 1)
    ctx.check("and is reported once with signal-cli's code and message",
              notices == [{"kind": "notice", "name": "subscribe_failed", "code": -32601, "message": "Method not found"}])
    t, notices, sent, _ = _transport([E.UserFailure("no", -1)] * 10)
    t._subscribe()
    ctx.check("retries are bounded, then reported once", len(sent) == SUBSCRIBE_TRIES and len(notices) == 1)
    t, notices, sent, interrupts = _transport([E.IOFailure("no reply to subscribeReceive")])
    t._subscribe()
    ctx.check("no reply at all is reported and drops the link so the supervisor reconnects",
              len(notices) == 1 and interrupts == [1])

    def closed(tr):
        tr._link = None
        return E.IOFailure("signal-cli link closed")
    t, notices, sent, interrupts = _transport([closed])
    t._subscribe()
    ctx.check("a link that closed under the call reports nothing (the next link subscribes)", notices == [])
    t, notices, sent, _ = _transport([0], transport="tcp")
    t._subscribe()
    ctx.check("a daemon client names the account", sent == [("subscribeReceive", {"account": "+15555550100"})])


@test
def test_item30_bridge_surfaces_subscribe_failed(ctx: Ctx):
    from halo_harness.remote import bridge_state as BS
    with Home():
        path = Path(tempfile.mkdtemp(prefix="d1-pulse-")) / "bridge.json"
        pulse = BS.BridgeState(path=path)
        b = Bridge({}, StubTransport(), NoRegistry(), pulse=pulse)
        b._stop_path = None
        b.on_notice({"kind": "notice", "name": "connected"})
        ctx.check("connected first", BS.read(path)["state"] == "connected")
        item = {"kind": "notice", "name": "subscribe_failed", "code": -32601, "message": "Method not found"}
        b.handle(item)
        ctx.check("the pulse no longer says connected", BS.read(path)["state"] == "starting")
        notes = [n for n in b.pairing.notices() if n["kind"] == "subscribe_failed"]
        ctx.check("a notice names the error", len(notes) == 1 and "-32601" in notes[0]["text"]
                  and "Method not found" in notes[0]["text"] and "not being received" in notes[0]["text"])
        ctx.check("and an audit line is written", any(r["outcome"] == "subscribe_failed -32601" for r in _audit_rows()))
        b.handle(item)
        ctx.check("a repeat does not flood the notices",
                  len([n for n in b.pairing.notices() if n["kind"] == "subscribe_failed"]) == 1)


# ---- item 97 -------------------------------------------------------------------

@test
def test_item97_pairing_code_guesses_are_audited(ctx: Ctx):
    from halo_harness.remote.pairing_files import MAX_ATTEMPTS
    with Home():
        b = Bridge({}, StubTransport(), NoRegistry())

        def guess(aci, code):
            env = data_message(aci, code, now_ms())["envelope"]
            b.handle({"kind": "envelope", "envelope": env, "exception": None, "account": None})
        b.pairing.note_contact(ACI_A, "+15555550101", SAFETY_A)
        real = b.pairing.approve(ACI_A).code
        wrong = f"{(int(real) + 1) % 1000000:06d}"
        guess(ACI_A, wrong)
        ctx.check("a wrong code leaves an audit line", [r["outcome"] for r in _audit_rows()] == ["wrong"])
        ctx.check("and a notice", [n["kind"] for n in b.pairing.notices()].count("code_wrong") == 1)
        for _ in range(MAX_ATTEMPTS - 1):
            guess(ACI_A, wrong)
        outcomes = [r["outcome"] for r in _audit_rows()]
        ctx.check("every guess is audited; the last one drops the request",
                  outcomes == ["wrong"] * (MAX_ATTEMPTS - 1) + ["dropped"])
        ctx.check("the wrong-code notice is not repeated", [n["kind"] for n in b.pairing.notices()].count("code_wrong") == 1)
        ctx.check("no line holds the code", all(wrong not in json.dumps(r) for r in _audit_rows()))
        b.pairing.note_contact(ACI_B, "+15555550102", SAFETY_B)
        b.pairing.approve(ACI_B)
        b.pairing.clock = lambda: time.time() + 10_000
        guess(ACI_B, "123456")
        ctx.check("a code sent after expiry is audited", _audit_rows()[-1]["outcome"] == "expired")


# ---- item 98 -------------------------------------------------------------------

@test
def test_item98_sweep_keeps_young_and_owned_sockets(ctx: Ctx):
    from halo_harness.remote import registry
    d = Path(tempfile.mkdtemp(prefix="d1-run-"))
    young, owned, dead = d / "young.ctl", d / "owned.ctl", d / "dead.ctl"
    for f in (young, owned, dead):
        f.write_text("", encoding="utf-8")
    old = time.time() - 3600
    for f in (owned, dead):
        os.utime(f, (old, old))
    (d / registry.FILENAME).write_text(json.dumps({"version": 1, "sessions": [
        {"session_id": "owned", "pid": os.getpid(), "endpoint": "unix:x"}]}), encoding="utf-8")
    registry.sweep_stale_ctl(d)
    ctx.check("a just-created socket file is kept", young.exists())
    ctx.check("one whose session has a live pid is kept", owned.exists())
    ctx.check("an old unowned one with no listener is removed", not dead.exists())
    if os.name == "nt" or not hasattr(socket, "AF_UNIX"):
        return
    path = d / "binding.ctl"
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.bind(str(path))  # bound, not yet listening: a connect probe is refused
        registry.sweep_stale_ctl(d)
        ctx.check("a sibling's bound-but-not-listening socket survives the sweep", path.exists())
    finally:
        s.close()


# ---- item 99 -------------------------------------------------------------------

@test
def test_item99_pair_code_ttl_is_the_setting(ctx: Ctx):
    from halo_harness.remote import cli_pair, dialog_model
    from halo_harness.remote.pairing import Pairing
    from halo_harness.theme import set_config_value
    with Home():
        set_config_value("remote.pair_code_ttl_s", 60)
        Pairing().note_contact(ACI_A, "+15555550101", SAFETY_A)
        res = dialog_model.approve(ACI_A)
        ctx.check("the /remote dialog's code lives 60 s", res["ok"] and abs(res["expires"] - time.time() - 60) < 5)
        Pairing().note_contact(ACI_B, "+15555550102", SAFETY_B)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cli_pair.cmd_pair(["--approve", ACI_B, "--wait", "0", "--json"])
        row = json.loads(out.getvalue())
        ctx.check("`halo remote signal pair --approve` honours it too",
                  rc == 0 and abs(row["expires"] - time.time() - 60) < 5)


# ---- item 100 ------------------------------------------------------------------

@test
def test_item100_launchd_restarts_on_failure_only(ctx: Ctx):
    from halo_harness.remote.daemon_units import render_launchd
    plist = plistlib.loads(render_launchd(["/usr/local/bin/halo", "remote", "signal", "run"]).encode("utf-8"))
    ctx.check("KeepAlive restarts only after a non-zero exit", plist.get("KeepAlive") == {"SuccessfulExit": False})
    ctx.check("RunAtLoad still starts it at login", plist.get("RunAtLoad") is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
