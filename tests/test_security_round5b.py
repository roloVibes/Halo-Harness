"""tests.test_security_round5b -- 2.0.10 round 5, security fix pass 3
(subprocesses), findings 21-23 of docs/harness/SECURITY-REVIEW-2.0.10.md.

21  the signal-cli archive is checked against a pinned SHA-256 before it is
    unpacked; gpg counts only when made by the pinned key; the tar
    extraction rejects device, FIFO, link, absolute and `..` members
22  the cc: route reads the child's `system.init` tool list and ends the turn
    when a built-in tool is advertised
23  the registration-lock PIN reaches signal-cli through JSON-RPC stdin, not
    argv (verify --pin falls back to argv only when signal-cli has no such
    method, and says so)

Siblings: test_security_round5 (1-5), test_security_round5c (26-27).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.cli_rig import Env, make_archive, run
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()
JVM, NATIVE = "signal-cli-0.14.9.tar.gz", "signal-cli-0.14.9-Linux-native.tar.gz"


def _tar(members: list) -> Path:
    path = Path(tempfile.mkdtemp(prefix="sec5b-tar-")) / "a.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        for name, kind in members:
            info = tarfile.TarInfo(name)
            info.type = kind
            data = b"x" if kind == tarfile.REGTYPE else b""
            info.size = len(data)
            if kind == tarfile.SYMTYPE:
                info.linkname = "/etc/passwd"
            tar.addfile(info, io.BytesIO(data))
    return path


def _extract_ok(inst, members) -> bool:
    try:
        inst.extract(_tar(members), Path(tempfile.mkdtemp(prefix="sec5b-dest-")))
        return True
    except inst.InstallError:
        return False


@test
def test_f21_digest_is_pinned_and_checked_before_unpacking(ctx: Ctx):
    from halo_harness.remote import signal_install as inst
    ctx.check("f21 the two pinned archives carry the published GitHub digests",
              inst.SHA256[JVM] == "c32b87f587198cbd277c9d71228716ee6047ee2b63e8e88728e8280d9407d65a"
              and inst.SHA256[NATIVE] == "a8fab78b5e8053abf3db5725272957ad11d1745b9a16848ddb2ace4743dfa5d5")
    with Env():
        d = Path(tempfile.mkdtemp(prefix="sec5b-dl-"))
        good = d / JVM
        make_archive(good)  # pins the stand-in as the digest of both assets
        ctx.check("f21 a matching archive passes", inst.verify_digest(good, JVM) == hashlib.sha256(good.read_bytes()).hexdigest())
        inst.SHA256[JVM] = "0" * 64
        try:
            inst.verify_digest(good, JVM)
            mismatch = False
        except inst.InstallError as e:
            mismatch = "mismatch" in str(e)
        ctx.check("f21 a different archive is an install error", mismatch)
        for pin in ("", "PLACEHOLDER", None):
            inst.SHA256[JVM] = pin
            try:
                inst.verify_digest(good, JVM)
                refused = False
            except inst.InstallError as e:
                refused = "no pinned SHA-256" in str(e)
            ctx.check(f"f21 an unpinned asset ({pin!r}) refuses to install", refused)


@test
def test_f21_install_stops_on_a_wrong_digest_before_extracting(ctx: Ctx):
    from halo_harness.remote import signal_install as inst
    with Env():
        saved = (inst.download, inst.native_host, inst.extract)
        calls = []
        inst.native_host = lambda *a: False

        def fake_download(url, dest, progress=None):
            if url.endswith(".asc"):
                Path(dest).write_text("sig", encoding="utf-8")
            else:
                make_archive(Path(dest))
                inst.SHA256[JVM] = "f" * 64  # the pin differs from what the "server" sent

        inst.download = fake_download
        inst.extract = lambda *a, **k: calls.append(a)
        try:
            rc, out, err = run(["setup", "--model", "dedicated", "--yes"])
        finally:
            inst.download, inst.native_host, inst.extract = saved
        ctx.check("f21 setup fails with a SHA-256 mismatch message", rc == 1 and "mismatch" in err)
        ctx.check("f21 nothing was unpacked and no install directory exists", calls == [] and not inst.install_dir().exists())
        ctx.check("f21 the downloaded archive was deleted", not list((inst.install_dir().parent.parent / "dl").glob("*.tar.gz")))


@test
def test_f21_gpg_counts_only_for_the_pinned_key(ctx: Ctx):
    from halo_harness.remote import signal_install as inst
    pinned, other = "A" * 40, "B" * 40
    sig = Path(tempfile.mkdtemp(prefix="sec5b-sig-")) / "a.asc"
    sig.write_text("x", encoding="utf-8")

    def runner(fpr):
        def run_(argv, **kw):
            line = f"[GNUPG:] VALIDSIG {fpr} 2026-10-07 1 0 4 0 1 10 00 {fpr}\n"
            return types.SimpleNamespace(returncode=0, stdout=line, stderr="")
        return run_

    saved = (inst.RELEASE_KEY_FINGERPRINT, inst.shutil.which)
    inst.shutil.which = lambda name: "/usr/bin/gpg"
    try:
        ctx.check("f21 no pinned fingerprint: gpg is not consulted", inst.verify_signature(Path("a"), sig, runner(other))[0] == "digest-only")
        inst.RELEASE_KEY_FINGERPRINT = pinned
        ctx.check("f21 a good signature by some OTHER key is bad, not verified", inst.verify_signature(Path("a"), sig, runner(other))[0] == "bad")
        ctx.check("f21 a good signature by the pinned key is verified", inst.verify_signature(Path("a"), sig, runner(pinned))[0] == "verified")
    finally:
        inst.RELEASE_KEY_FINGERPRINT, inst.shutil.which = saved


@test
def test_f21_extract_rejects_unsafe_members(ctx: Ctx):
    from halo_harness.remote import signal_install as inst
    ctx.check("f21 a normal archive extracts", _extract_ok(inst, [("signal-cli/bin/signal-cli", tarfile.REGTYPE)]))
    for label, member in (("device", ("dev/null", tarfile.CHRTYPE)), ("block device", ("dev/sda", tarfile.BLKTYPE)),
                          ("FIFO", ("pipe", tarfile.FIFOTYPE)), ("symlink", ("link", tarfile.SYMTYPE)),
                          ("absolute path", ("/tmp/halo-evil", tarfile.REGTYPE)), ("dot-dot", ("a/../../evil", tarfile.REGTYPE)),
                          ("backslash dot-dot", ("a" + chr(92) + ".." + chr(92) + "evil", tarfile.REGTYPE)),
                          ("drive path", ("C:/evil", tarfile.REGTYPE))):
        ctx.check(f"f21 a {label} member is rejected", not _extract_ok(inst, [("ok/file", tarfile.REGTYPE), member]))


@test
def test_f22_builtin_tools_in_system_init_end_the_turn(ctx: Ctx):
    from halo_harness.agent import cc_runtime
    ctx.check("f22 only mcp__ names are accepted",
              cc_runtime.builtin_tools_in_init({"tools": ["mcp__rolo__Read", "mcp__x__y"]}) == []
              and cc_runtime.builtin_tools_in_init({"tools": ["mcp__rolo__Read", "Bash", {"name": "Write"}]}) == ["Bash", "Write"]
              and cc_runtime.builtin_tools_in_init({}) == [])
    from tests.test_cc_session import _fake_claude_env, _new_cc_session
    with _fake_claude_env():
        from halo_harness.subscription_consent import record_acceptance
        record_acceptance()  # the cc: route is gated per home (2.0.7 round 7b)
        os.environ["FAKE_CC_LEAK_BUILTIN"] = "1"
        try:
            session, _ = _new_cc_session()
            evs = list(session.turn("reply with the single word pong"))
            state = session._cc_state
            errs = [e for e in evs if e.kind == "error" and e.data.get("err_type") == "cc_builtin_tools"]
            ctx.check("f22 a plain error names the leaked tools", len(errs) == 1 and "Bash" in errs[0].data["message"])
            ctx.check("f22 the turn ends as an error and no model text came through",
                      evs[-1].kind == "turn_done" and evs[-1].data["reason"] == "error"
                      and not [e for e in evs if e.kind == "text_delta"])
            ctx.check("f22 the child was stopped", state is not None and not state.process.alive and state.leaked_tools == ["Bash", "Write"])
            session.close_cc()
        finally:
            os.environ.pop("FAKE_CC_LEAK_BUILTIN", None)


@test
def test_f23_pin_goes_through_stdin_not_argv(ctx: Ctx):
    with Env("ok") as env:
        env.write_signal_json(identity_model="dedicated")
        rc, out, err = run(["register", "+15555550123", "--code", "123456"])
        from halo_harness.remote.signal_config import remote_dir
        pin = (remote_dir() / "registration-pin").read_text(encoding="utf-8").strip()
        calls = env.calls()
        argvs = [c for c in calls if isinstance(c, list)]
        rpcs = [c for c in calls if isinstance(c, dict)]
        ctx.check("f23 setPin went over JSON-RPC with the PIN as a param", any(c["rpc"] == "setPin" and c["params"] == {"pin": pin} for c in rpcs))
        ctx.check("f23 no process argument anywhere contains the PIN or setPin", not any(pin in json.dumps(a) or "setPin" in a for a in argvs))
        ctx.check("f23 the PIN is not printed", rc == 0 and pin not in out + err)
    with Env("locked") as env:
        env.write_signal_json(identity_model="dedicated")
        rc, out, err = run(["register", "+15555550123", "--code", "123456", "--pin", "999999"])
        calls = env.calls()
        ctx.check("f23 verify --pin is offered to JSON-RPC first (PIN as a param)",
                  any(isinstance(c, dict) and c["rpc"] == "verify" and c["params"].get("pin") == "999999" for c in calls))
        ctx.check("f23 signal-cli 0.14.9 has no such method, so the argv fallback runs and says so",
                  rc == 0 and "visible" in err and any(isinstance(c, list) and "999999" in c for c in calls))
        rc, out, err = run(["register", "+15555550123", "--code", "123456"])
        ctx.check("f23 without --pin the PIN is never involved (no RPC verify, no note)", "visible" not in err)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
