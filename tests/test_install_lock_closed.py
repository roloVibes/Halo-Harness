"""tests.test_install_lock_closed -- the installer installs nothing when it cannot fetch the dependency lock (Halo
3.4.1.2, the 2026-11-12 review's PACKS-10; scripts/install-halo.sh, scripts/install-halo.ps1, update_install.py):

1. `install-halo.sh --no-clone` fetches requirements.lock itself first; when that fails it says so in one line, names
   the unpinned command to run on purpose, exits 1 and never runs `uv tool install` (stubs for curl, git and uv on
   PATH, a scratch HOME: nothing real runs, nothing leaves the machine);
2. the PowerShell installer carries the same check (read from its text: running it needs Windows' own tools).
3. `halo update` with the lock unreachable exits 1 and runs no install (update_install.pin_locally fails closed).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
STUB = "#!/usr/bin/env bash\necho \"$(basename \"$0\") $*\" >> \"$STUB_LOG\"\n"


@test
def test_packs_10_the_installer_fails_closed_without_the_lock(ctx: Ctx):
    bash = shutil.which("bash")
    if not bash:
        raise SkipTest("no bash on PATH")
    with tempfile.TemporaryDirectory(prefix="halo-install-") as tmp:
        stubs, home, log = Path(tmp) / "bin", Path(tmp) / "home", Path(tmp) / "calls.log"
        stubs.mkdir()
        home.mkdir()
        for name, tail in (("curl", "exit 22\n"), ("git", "exit 0\n"), ("uv", "[ \"$1\" = --version ] && echo 'uv 0.0.0'\nexit 0\n")):
            (stubs / name).write_text(STUB + tail, encoding="utf-8", newline="\n")
            (stubs / name).chmod(0o755)
        env = {**os.environ, "PATH": str(stubs) + os.pathsep + os.environ.get("PATH", ""), "HOME": str(home),
               "STUB_LOG": str(log), "HALO_NO_MODIFY_PATH": "1", "HALO_CLONE_DIR": str(home / "clone")}
        sha = "0123456789abcdef0123456789abcdef01234567"
        r = subprocess.run([bash, str(REPO / "scripts" / "install-halo.sh"), "--no-clone", "--yes", "--ref", sha],
                           capture_output=True, text=True, timeout=60, env=env, stdin=subprocess.DEVNULL)
        calls = log.read_text(encoding="utf-8") if log.exists() else ""
        ctx.check(f"exit 1, the one line names the lock and the deliberate way, got {r.returncode} {r.stdout[-400:]!r}",
                  r.returncode == 1 and "nothing was installed" in r.stdout and "without the pin on purpose" in r.stdout)
        ctx.check(f"curl was asked for the lock, uv never installed, got {calls!r}",
                  "requirements.lock" in calls and "uv tool install" not in calls)


@test
def test_packs_10_the_powershell_installer_carries_the_same_check(ctx: Ctx):
    text = (REPO / "scripts" / "install-halo.ps1").read_text(encoding="utf-8")
    ctx.check("the lock is fetched first and checked for its hashes", "Invoke-WebRequest" in text
              and "--hash=sha256:" in text and "so nothing was installed" in text and "without the pin on purpose" in text)


@test
def test_packs_10_halo_update_installs_nothing_without_the_lock(ctx: Ctx):
    from halo_harness import update_cli
    from halo_harness import update_install as UI
    from tests.test_update_cli import _Proc, _capture, _patch_all, _restore_all, upd
    cmd = ("uv tool install --reinstall --constraints https://raw.githubusercontent.com/roloVibes/Halo-Harness/master/"
           "requirements.lock git+https://github.com/roloVibes/Halo-Harness")
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb")
    ran, was = [], UI.fetch_lock

    def boom(_url):
        raise OSError("certificate verify failed")

    def fake_run(c, **kwargs):
        ran.append(c)
        return _Proc(stdout="halo 2.0.2 (aaaaaaa, master)")
    upd.run, UI.fetch_lock = fake_run, boom
    try:
        code, _out, err = _capture(lambda: update_cli.apply_update(cmd=cmd, force=True))
        ctx.check(f"exit 1, no install run, the line on stderr, got {code} {ran} {err!r}", code == 1 and "nothing was installed" in err
                  and not any(isinstance(c, str) and "uv tool install" in c for c in ran))
    finally:
        UI.fetch_lock = was
        _restore_all(orig)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
