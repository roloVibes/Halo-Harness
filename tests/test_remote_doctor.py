"""tests.test_remote_doctor -- Halo 2.0.9 round 4: `halo doctor`'s remote
control checks (halo_harness/remote/doctor_check.py): quiet when unused;
control sockets, the Signal bridge, signal-cli presence / the 0.14.9 pin / the
90-day warning, the JRE for the JVM build, ~/.halo/remote/ permissions, the
proxy egress hosts; `--json` records like every other check; doctor writes
nothing."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.cli_rig import Env
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_default_provider_credentials()
test, TESTS = new_registry()
PROXY_VARS = ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy", "JAVA_TOOL_OPTIONS")


class Proxyless:
    def __enter__(self):
        self.saved = {k: os.environ.pop(k, None) for k in PROXY_VARS}
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        return False


def _entries() -> dict:
    from halo_harness.remote.doctor_check import entries
    return dict(entries())


def _remote_files(env: Env) -> set:
    return {str(p.relative_to(env.home)) for p in Path(env.home).rglob("*")}


@test
def test_quiet_when_unused_and_writes_nothing(ctx: Ctx):
    with Env() as env, Proxyless():
        before = _remote_files(env)
        e = _entries()
        ctx.check("one line, OK, names the flag", list(e) == ["remote"] and e["remote"].startswith("[OK] Remote control: off (remote.enabled is false)"))
        ctx.check("doctor created no ~/.halo/remote and no run dir", _remote_files(env) == before)
        from halo_harness.theme import set_config_value
        set_config_value("remote.enabled", True)
        e = _entries()
        ctx.check("with remote.enabled the control line says on and counts the registry",
                  e["remote"].startswith("[OK] Remote control: on (remote.enabled)") and "0 live sessions" in e["remote"])
        ctx.check("remote.enabled without a signal.json says the bridge is not set up and how",
                  e["remote_signal_cli"].startswith("[WARN] Signal bridge: not set up yet") and "-> fix: halo remote signal setup" in e["remote_signal_cli"])


@test
def test_signal_cli_presence_pin_and_age(ctx: Ctx):
    from halo_harness.remote import signal_install as inst
    with Env() as env, Proxyless():
        env.write_signal_json()
        os.environ["FAKE_SIGNAL_VERSION"] = "0.14.9"
        e = _entries()
        ctx.check("the pinned version, fresh: OK with the release date and age",
                  e["remote_signal_cli"].startswith("[OK] signal-cli: 0.14.9 (pinned 0.14.9, released 2026-10-07"))
        ctx.check("the bridge line reads off", e["remote_bridge"].startswith("[OK] Signal bridge: off"))
        saved = inst.age_days
        inst.age_days = lambda now=None: 91.0
        try:
            line = _entries()["remote_signal_cli"]
        finally:
            inst.age_days = saved
        ctx.check("past 90 days from the release: WARN with the reason and a pointer", line.startswith("[WARN]") and "91 days ago" in line
                  and "-> see: docs/REMOTE.md" in line)
        os.environ["FAKE_SIGNAL_VERSION"] = "0.14.8"
        line = _entries()["remote_signal_cli"]
        ctx.check("a different version than the pin: WARN with the setup command",
                  line.startswith("[WARN] signal-cli: 0.14.8 found, Halo is pinned to 0.14.9") and "-> fix: halo remote signal setup" in line)
        env.write_signal_json(binary=[str(Path(env.home) / "no-such-signal-cli")])
        line = _entries()["remote_signal_cli"]
        ctx.check("a missing binary: WARN with the setup command", line.startswith("[WARN] signal-cli: not found") and "halo remote signal setup" in line)


@test
def test_bridge_state_line(ctx: Ctx):
    from halo_harness.remote import bridge_state as BS
    with Env() as env, Proxyless():
        env.write_signal_json()
        BS.BridgeState().write("connected")
        line = _entries()["remote_bridge"]
        ctx.check("a live bridge pulse shows state and pid", "Signal bridge: connected (pid " in line and "remote.signal.enabled false" in line)


@test
def test_jre_only_for_the_jvm_build(ctx: Ctx):
    from halo_harness.remote import signal_install as inst
    with Env() as env, Proxyless():
        env.write_signal_json()
        saved = (inst.native_host, inst.java_major)
        try:
            inst.native_host = lambda *a: False
            for major, want in ((None, "[WARN] Java runtime: none found"), (17, "[WARN] Java runtime: 17 found"), (25, "[OK] Java runtime: 25")):
                inst.java_major = lambda *a, m=major, **k: m
                ctx.check(f"JVM build, java={major}: {want}", _entries()["remote_jre"].startswith(want))
            ctx.check("the WARN names JRE 25 and where to get one", "-> see: https://adoptium.net/" in
                      (setattr(inst, "java_major", lambda *a, **k: None), _entries()["remote_jre"])[1])
            inst.native_host = lambda *a: True
            ctx.check("native build (Linux x86-64, no lib/ beside bin/): no JRE line", "remote_jre" not in _entries())
        finally:
            inst.native_host, inst.java_major = saved


@test
def test_permissions_under_the_remote_directory(ctx: Ctx):
    from halo_harness.remote.signal_config import remote_dir
    with Env() as env, Proxyless():
        env.write_signal_json()
        line = _entries()["remote_dir"]
        if os.name == "nt":
            ctx.check("Windows: reported as following the account, not checked", line.startswith("[OK]") and "not checked" in line)
            return
        d = remote_dir()
        os.chmod(d, 0o700)
        os.chmod(d / "signal.json", 0o600)
        ctx.check("0700 / 0600: OK", _entries()["remote_dir"].startswith("[OK]"))
        os.chmod(d / "signal.json", 0o644)
        line = _entries()["remote_dir"]
        ctx.check("a world-readable file: WARN naming it, with the chmod fix", line.startswith("[WARN]") and "signal.json" in line and "chmod 600" in line)
        os.chmod(d / "signal.json", 0o600)
        os.chmod(d, 0o755)
        ctx.check("a loose directory: WARN", "[WARN]" in _entries()["remote_dir"])


@test
def test_proxy_egress_hosts(ctx: Ctx):
    from halo_harness.remote import signal_install as inst
    with Env() as env, Proxyless():
        env.write_signal_json()
        ctx.check("no proxy: no egress line", "remote_egress" not in _entries())
        saved = inst.native_host
        inst.native_host = lambda *a: False
        try:
            os.environ["HTTPS_PROXY"] = "http://proxy.invalid:3128"
            line = _entries()["remote_egress"]
            hosts = ("chat.signal.org", "cdn.signal.org", "cdn2.signal.org", "cdn3.signal.org", "storage.signal.org",
                     "cdsi.signal.org", "svr2.signal.org")
            ctx.check("with a proxy: all seven hosts, port and WebSockets, and the JVM caveat", line.startswith("[WARN]")
                      and all(h in line for h in hosts) and "443" in line and "WebSockets" in line and "JAVA_TOOL_OPTIONS" in line)
            os.environ["JAVA_TOOL_OPTIONS"] = "-Dhttps.proxyHost=proxy.invalid -Dhttps.proxyPort=3128"
            line = _entries()["remote_egress"]
            ctx.check("with the JVM proxy properties set: OK, hosts still listed", line.startswith("[OK]") and "svr2.signal.org" in line)
        finally:
            inst.native_host = saved


@test
def test_json_records_match_the_other_checks(ctx: Ctx):
    from halo_harness import doctor
    with Env() as env, Proxyless():
        env.write_signal_json(binary=[str(Path(env.home) / "gone")])
        rows = [dict(doctor._parse_check_line(line), id=cid) for cid, line in doctor._check_remote()]
        ctx.check("every record has id, status, message, fix, see",
                  rows and all({"id", "status", "message", "fix", "see"} <= set(r) for r in rows))
        bad = [r for r in rows if r["id"] == "remote_signal_cli"][0]
        ctx.check("a WARN carries its fix command in `fix`", bad["status"] == "warn" and bad["fix"] == "halo remote signal setup")
        checks, _ok = doctor.run_checks_structured()
        ids = [c["id"] for c in checks]
        ctx.check("run_checks_structured / doctor --json include the remote checks, ids unique",
                  "remote" in ids and "remote_signal_cli" in ids and len(ids) == len(set(ids)))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
