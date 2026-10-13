"""tests.test_review3_d2b -- the 3.0.2.0 review fix pass, round D2 (Signal
bridge), part 2: the transport's rate-limit pause and the installer. No signal-cli,
java or gpg is ever spawned here: every child is a stub.

  * review item 102  typing and receipts stay quiet during a -5 pause; one notice per pause
  * review item 103  a download cut mid-stream is an install error and leaves no partial file
  * review item 104  `signal link`, `version_of`, `java_major` run without provider keys
(items 105-107 are in tests/test_review3_d2c.py)
"""
from __future__ import annotations

import contextlib
import http.client
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from halo_harness.remote import signal_errors as E
from halo_harness.remote import signal_install as inst
from halo_harness.remote.signal_link import Link
from halo_harness.remote.signal_transport import SignalTransport
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.signal_rig import ACI_A, Home

test, TESTS = new_registry()
PLANTED = "planted-provider-key-d2"
KEYS = ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "DATABRICKS_TOKEN")


@contextlib.contextmanager
def planted_keys():
    saved = {k: os.environ.get(k) for k in KEYS}
    for k in KEYS:
        os.environ[k] = PLANTED
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _transport(sink: list, **cfg) -> SignalTransport:
    t = SignalTransport({"data_dir": tempfile.mkdtemp(prefix="d2-sig-"), "receive_mode": "on-start", **cfg},
                        backoff=(0.01,), request_timeout=1.0)
    t.set_sink(sink.append)
    return t


class _ReplyLink(Link):
    """A link whose `write` answers at once through `reply(request) -> response`."""

    def __init__(self, t: SignalTransport, reply) -> None:
        super().__init__(io.BytesIO(b""), io.BytesIO(), lambda: None)
        self.t, self.reply, self.methods, self.interrupts = t, reply, [], 0

    def write(self, obj: dict) -> None:
        self.methods.append(obj["method"])
        self.t._dispatch({"id": obj["id"], **self.reply(obj)})

    def interrupt(self) -> None:
        self.interrupts += 1


def _connect(t: SignalTransport, reply) -> _ReplyLink:
    link = _ReplyLink(t, reply)
    t._link = link
    t._connected.set()
    return link


@test
def test_item102_typing_and_receipts_wait_out_the_pause(ctx: Ctx):
    sink: list = []
    t = _transport(sink)
    link = _connect(t, lambda req: {"error": {"code": -5, "message": "rate limited",
                                              "data": {"results": [{"retryAfterSeconds": 300, "token": "tok-1"}]}}})
    for _ in range(3):
        try:
            t.request("send", {"message": "x"})
        except E.RateLimited:
            pass
    notes = [n for n in sink if n.get("name") == "rate_limited"]
    ctx.check(f"one rate_limited notice for one pause, got {len(notes)}", len(notes) == 1)
    n = len(link.methods)
    ctx.check("sendTyping during the pause is skipped", t.send_typing(ACI_A) is None and t.send_typing(ACI_A, True) is None)
    ctx.check("sendReceipt during the pause is skipped", t.send_receipt(ACI_A, 123) is None)
    ctx.check("neither reached signal-cli", len(link.methods) == n)
    link.reply = lambda req: {"error": {"code": -5, "data": {"results": [{"retryAfterSeconds": 300, "token": "tok-2"}]}}}
    try:
        t.request("send", {"message": "x"})
    except E.RateLimited:
        pass
    ctx.check("a new captcha token is surfaced", len([s for s in sink if s.get("name") == "rate_limited"]) == 2
              and t.captcha_token == "tok-2")
    t.paused_until = 0.0
    link.reply = lambda req: {"result": {}}
    t.send_typing(ACI_A)
    ctx.check("typing resumes once the pause is over", link.methods[-1] == "sendTyping")


class _CutResponse:
    def __init__(self) -> None:
        self.calls = 0

    def read(self, n: int) -> bytes:
        self.calls += 1
        if self.calls == 1:
            return b"x" * 1024
        raise http.client.IncompleteRead(b"", 4096)

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False


@test
def test_item103_cut_download_is_an_install_error(ctx: Ctx):
    from halo_harness.providers import http as phttp
    saved = phttp.urlopen_tls
    dest = Path(tempfile.mkdtemp(prefix="d2-dl-")) / "signal-cli.tar.gz"
    phttp.urlopen_tls = lambda url, timeout=60: _CutResponse()
    try:
        inst.download("https://example.invalid/signal-cli.tar.gz", dest)
        err = ""
    except inst.InstallError as e:
        err = str(e)
    finally:
        phttp.urlopen_tls = saved
    ctx.check(f"IncompleteRead becomes 'download failed', got {err!r}", err.startswith("download failed") and "IncompleteRead" in err)
    ctx.check("the partial archive is removed", not dest.exists())


@test
def test_item103_setup_reports_an_unexpected_install_failure(ctx: Ctx):
    from halo_harness.remote import cli_setup
    saved = (inst.install, inst.find_installed, inst.java_major, inst.native_host)

    def boom(*a, **k):
        raise RuntimeError("tar exploded")
    inst.install, inst.find_installed = boom, (lambda *a, **k: None)
    inst.java_major, inst.native_host = (lambda *a, **k: 25), (lambda *a, **k: False)
    out = io.StringIO()
    try:
        with Home(), contextlib.redirect_stdout(out):
            rc = cli_setup.cmd_setup(["--json", "--yes", "--model", "dedicated", "--jvm"])
    finally:
        inst.install, inst.find_installed, inst.java_major, inst.native_host = saved
    res = json.loads(out.getvalue())
    ctx.check(f"rc 1 with install_failed, got {rc} {res}", rc == 1 and res["error"] == "install_failed"
              and "tar exploded" in res["message"])


@test
def test_item104_third_party_children_get_no_provider_keys(ctx: Ctx):
    seen: list = []

    def runner(argv, **kw):
        seen.append(kw.get("env"))
        return type("R", (), {"stdout": "signal-cli 0.14.9", "stderr": 'openjdk version "25.0.1"', "returncode": 0})()
    import shutil
    saved_which = shutil.which
    with planted_keys():
        shutil.which = lambda name, *a, **k: "/usr/bin/" + name
        try:
            v, j = inst.version_of("signal-cli", runner), inst.java_major(runner)
        finally:
            shutil.which = saved_which
        ctx.check("the runners still parse", v == "0.14.9" and j == 25)
        ctx.check("an env is passed to both children", len(seen) == 2 and all(isinstance(e, dict) for e in seen))
        ctx.check("no planted key reaches signal-cli --version or java -version",
                  all(PLANTED not in e.values() for e in seen))
        _check_link_env(ctx)


def _check_link_env(ctx: Ctx) -> None:
    import subprocess
    from halo_harness.remote import cli_common as C
    from halo_harness.remote import cli_link
    got: dict = {}

    class FakeProc:
        def __init__(self, argv, **kw):
            got.update(kw)
            self.stdout = iter(["no link today\n"])

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            pass
    saved = (subprocess.Popen, C.configured)
    subprocess.Popen = FakeProc
    C.configured = lambda as_json=False: ({"binary": "signal-cli", "data_dir": tempfile.mkdtemp(prefix="d2-l-")}, 0)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            rc = cli_link.cmd_link(["--json", "--timeout", "1"])
    finally:
        subprocess.Popen, C.configured = saved
    env = got.get("env")
    ctx.check(f"signal link gets a scrubbed env (rc {rc})", isinstance(env, dict) and PLANTED not in env.values()
              and "PATH" in {k.upper() for k in env})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
