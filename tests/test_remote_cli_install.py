"""tests.test_remote_cli_install -- Halo 2.0.9 round 4: the pieces under `halo remote signal setup`
and `run --daemon`: which signal-cli build each OS gets, the archive and offline guards, the QR
fallback on a narrow terminal, and the service-manager files per OS (written, never enabled)."""
from __future__ import annotations

import io
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.cli_rig import Env, run
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_default_provider_credentials()
test, TESTS = new_registry()


def _cfg() -> dict:
    from halo_harness.remote.signal_config import signal_json_path
    return json.loads(signal_json_path().read_text(encoding="utf-8"))


@test
def test_asset_choice_per_platform(ctx: Ctx):
    from halo_harness.remote import signal_install as inst
    ctx.check("Linux x86-64 gets the native tarball", inst.asset_name("linux", "x86_64").endswith("Linux-native.tar.gz"))
    for plat, arch in (("linux", "aarch64"), ("win32", "AMD64"), ("darwin", "arm64"), ("darwin", "x86_64")):
        ctx.check(f"{plat}/{arch} gets the JVM tarball", inst.asset_name(plat, arch) == "signal-cli-0.14.9.tar.gz")
    ctx.check("--jvm forces the JVM build even on Linux x86-64",
              inst.asset_name("linux", "x86_64", jvm=True) == "signal-cli-0.14.9.tar.gz")
    ctx.check("urls pin the tag", inst.asset_url("x.tar.gz") == "https://github.com/AsamK/signal-cli/releases/download/v0.14.9/x.tar.gz")
    ctx.check("release age counts from 2026-10-07", 0 <= inst.age_days(inst.RELEASED_TS + 86400 * 5) - 5 < 1e-6)


@test
def test_install_helpers_never_leave_the_directory_and_honour_offline(ctx: Ctx):
    from halo_harness.remote import signal_install as inst
    with Env():
        bad = Path(tempfile.mkdtemp(prefix="tar-")) / "evil.tar.gz"
        with tarfile.open(bad, "w:gz") as tar:
            data = b"x"
            info = tarfile.TarInfo("../../escape.txt")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        dest = Path(tempfile.mkdtemp(prefix="dest-"))
        try:
            inst.extract(bad, dest)
            ok = False
        except inst.InstallError:
            ok = True
        ctx.check("a path that escapes the target is an install error", ok and not (dest.parent / "escape.txt").exists())
        os.environ["HALO_OFFLINE"] = "1"
        try:
            inst.download("https://github.com/x", Path(tempfile.mkdtemp()) / "f")
            err = ""
        except inst.InstallError as e:
            err = str(e)
        ctx.check("network.offline blocks the download before any socket", "offline" in err.lower())
        st, _ = inst.verify_signature(Path("a"), None)
        ctx.check("no pinned release key -> gpg is not consulted (digest-only)", st == "digest-only")
        inst.RELEASE_KEY_FINGERPRINT = "A" * 40
        try:
            st, _ = inst.verify_signature(Path("a"), None)
        finally:
            inst.RELEASE_KEY_FINGERPRINT = ""
        ctx.check("a pinned key and no .asc -> no-signature", st == "no-signature")


@test
def test_qr_falls_back_to_ascii_on_a_narrow_terminal(ctx: Ctx):
    import contextlib
    from halo_harness.remote import cli_common as C
    raw = io.BytesIO()
    cp = io.TextIOWrapper(raw, encoding="ascii", errors="strict")
    with contextlib.redirect_stdout(cp):
        C.print_qr("HELLO WORLD")
        cp.flush()
    text = raw.getvalue().decode("ascii")
    ctx.check("an ASCII-only terminal gets the # form", "##" in text and len(text.splitlines()) == 25)


@test
def test_daemon_units_per_os_are_written_and_never_enabled(ctx: Ctx):
    from halo_harness.remote import daemon_units as du
    with Env():
        argv = ["/usr/bin/halo", "remote", "signal", "run"]
        env = {"JAVA_TOOL_OPTIONS": "-Dhttps.proxyHost=proxy.invalid -Dhttps.proxyPort=3128"}
        path, cmd = du.write_unit("linux", argv, env)
        text = path.read_text(encoding="utf-8")
        ctx.check("systemd: unit under ~/.halo/remote with ExecStart and the proxy env",
                  path.name == "halo-remote.service" and path.parent.name == "remote"
                  and "ExecStart=/usr/bin/halo remote signal run" in text and 'JAVA_TOOL_OPTIONS=-Dhttps.proxyHost' in text
                  and "WantedBy=default.target" in text)
        ctx.check("systemd: the printed command links and enables", cmd.startswith("systemctl --user link ") and "enable --now" in cmd)
        path, cmd = du.write_unit("macos", argv, {})
        text = path.read_text(encoding="utf-8")
        ctx.check("launchd: a plist with ProgramArguments and KeepAlive",
                  path.name == "dev.halo.remote.plist" and "<key>ProgramArguments</key>" in text and "<string>signal</string>" in text
                  and "KeepAlive" in text and cmd.startswith("launchctl bootstrap gui/"))
        path, cmd = du.write_unit("windows", ["C:\\Program Files\\halo\\halo.exe", "remote", "signal", "run"], {})
        text = path.read_bytes().decode("utf-16")
        ctx.check("Task Scheduler: XML with a logon trigger and the command",
                  path.name == "halo-remote-task.xml" and "LogonTrigger" in text and "halo.exe" in text
                  and "remote signal run" in text and cmd.startswith("schtasks /Create /TN"))
        rc, out, _ = run(["run", "--daemon", "--os", "linux", "--json"])
        res = json.loads(out)
        ctx.check("`run --daemon --json` reports the file and the one enable command, nothing more",
                  rc == 0 and Path(res["unit"]).exists() and res["enable"].startswith("systemctl --user"))
        ctx.check("run_argv falls back to the interpreter when halo is not on PATH",
                  du.run_argv()[-3:] == ["remote", "signal", "run"])


@test
def test_setup_jvm_flag_downloads_the_jvm_build_into_its_own_directory(ctx: Ctx):
    import json
    from pathlib import Path
    from halo_harness.remote import signal_install as inst
    from tests.helpers.cli_rig import make_archive
    with Env():
        urls, saved = [], (inst.download, inst.verify_signature, inst.native_host, inst.java_major)
        inst.native_host = lambda *a: True  # a Linux x86-64 host
        inst.java_major = lambda *a, **k: 25
        inst.verify_signature = lambda a, s, r=None: ("verified", "ok")
        inst.download = lambda url, dest, progress=None: (urls.append(url), make_archive(Path(dest)) if not url.endswith(".asc")
                                                           else Path(dest).write_text("s"))
        try:
            rc, out, err = run(["setup", "--model", "dedicated", "--yes", "--jvm", "--json"])
            res = json.loads(out)
            ctx.check("the JVM tarball, not the native one", rc == 0 and urls[0].endswith("/signal-cli-0.14.9.tar.gz"))
            ctx.check("unpacked beside, not over, the default build", "0.14.9-jvm" in Path(res["binary"]).parts)
            ctx.check("a JRE 25 satisfies the check", res["jre_ok"] is True)
        finally:
            inst.download, inst.verify_signature, inst.native_host, inst.java_major = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
