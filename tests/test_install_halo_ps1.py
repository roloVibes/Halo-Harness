"""tests.test_install_halo_ps1 -- Halo 2.0.2 round 6: scripts/install-halo.ps1
(the Windows counterpart to install-halo.sh) stays syntactically valid
PowerShell, and its `-DryRun` mode genuinely never installs/uninstalls/clones
anything. Runs real PowerShell (`pwsh` preferred, `powershell` as a
fallback) -- skipped outright where neither exists (any non-Windows CI box
with no PowerShell Core installed).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
SCRIPT = REPO_DIR / "scripts" / "install-halo.ps1"


def _require_powershell() -> str:
    for exe in ("pwsh", "powershell"):
        found = shutil.which(exe)
        if found:
            return exe
    raise SkipTest("no pwsh/powershell on PATH")


test, TESTS = new_registry()


@test
def test_install_halo_ps1_exists(ctx: Ctx):
    ctx.check(f"scripts/install-halo.ps1 exists, got {SCRIPT}", SCRIPT.is_file())


@test
def test_install_halo_ps1_parses_as_a_scriptblock(ctx: Ctx):
    """The brief's own check: `[scriptblock]::Create((Get-Content -Raw
    ...))` -- parses the file without running a single line of it."""
    exe = _require_powershell()
    # A single-quoted PowerShell string literal -- '' escapes a literal '
    # inside one, so a path containing a quote is still one argument.
    ps_literal = "'" + str(SCRIPT).replace("'", "''") + "'"
    command = f"[scriptblock]::Create((Get-Content -Raw -Path {ps_literal})) | Out-Null; Write-Host 'PARSE OK'"
    result = subprocess.run([exe, "-NoProfile", "-Command", command],
                             capture_output=True, text=True, timeout=30)
    ctx.check(f"{exe} parses the script with exit 0, got {result.returncode} "
              f"stdout={result.stdout!r} stderr={result.stderr!r}",
              result.returncode == 0 and "PARSE OK" in result.stdout)


@test
def test_install_halo_ps1_dry_run_no_clone_prints_commands_and_exits_0(ctx: Ctx):
    exe = _require_powershell()
    result = subprocess.run([exe, "-NoProfile", "-File", str(SCRIPT), "-NoClone", "-DryRun"],
                             capture_output=True, text=True, timeout=60)
    out = result.stdout
    ctx.check(f"exits 0, got {result.returncode} stdout={out!r} stderr={result.stderr!r}", result.returncode == 0)
    ctx.check(f"prints the install command as a dry run, got {out!r}",
              "DRY RUN:" in out and "uv tool install --reinstall git+" in out)
    ctx.check(f"never claims to have actually verified an install, got {out!r}",
              "DRY RUN: would check halo is on PATH" in out)


@test
def test_install_halo_ps1_dry_run_clone_path_never_touches_the_filesystem(ctx: Ctx):
    exe = _require_powershell()
    scratch = Path(tempfile.mkdtemp(prefix="install-halo-ps1-dry-run-"))
    clone_dir = scratch / "Halo-Harness-clone-target"
    result = subprocess.run([exe, "-NoProfile", "-File", str(SCRIPT), "-DryRun", "-CloneDir", str(clone_dir)],
                             capture_output=True, text=True, timeout=60)
    out = result.stdout
    ctx.check(f"exits 0, got {result.returncode} stdout={out!r} stderr={result.stderr!r}", result.returncode == 0)
    ctx.check(f"prints the git clone command as a dry run, got {out!r}",
              "DRY RUN:" in out and "git clone" in out and str(clone_dir) in out)
    ctx.check(f"the clone directory was never actually created, got exists={clone_dir.exists()}",
              not clone_dir.exists())


@test
def test_install_halo_ps1_stops_while_halo_runs_from_the_tool_environment(ctx: Ctx):
    """3.6.0.0 fix package update-install: the installer is also the repair line for a 3.5.0.1 Windows install, and
    `uv tool install --reinstall` meets a locked python.exe while any halo (a session, 3.5's detached Studio, the LAN
    host) runs from the tool environment it replaces. The installer names it and stops before it installs; under
    -DryRun it says it would. A process whose command line names `<uv tool dir>\\halo-harness\\` stands in for it
    (UV_TOOL_DIR points `uv tool dir` at a scratch folder, so nothing real is looked at or touched)."""
    if sys.platform != "win32":
        raise SkipTest("the Windows installer's process check")
    exe = _require_powershell()
    if not shutil.which("uv"):
        raise SkipTest("no uv on PATH")
    scratch = Path(tempfile.mkdtemp(prefix="install-halo-ps1-running-"))
    env_dir = scratch / "tools" / "halo-harness" / "Scripts"
    env_dir.mkdir(parents=True)
    import os
    stand_in = subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(90)", str(env_dir / "halo.exe")])
    try:
        env = dict(os.environ, UV_TOOL_DIR=str(scratch / "tools"))
        result = subprocess.run([exe, "-NoProfile", "-File", str(SCRIPT), "-NoClone", "-DryRun"],
                                capture_output=True, text=True, timeout=90, env=env)
    finally:
        stand_in.kill()
        stand_in.wait(timeout=10)
    out = result.stdout
    ctx.check(f"names the running halo by pid, got {out!r}",
              "Halo is running from the environment this install replaces" in out and f"pid {stand_in.pid}" in out)
    ctx.check(f"says what to close first, got {out!r}", "halo studio --stop" in out and "halo host stop" in out)
    ctx.check(f"-DryRun still exits 0, got {result.returncode} stderr={result.stderr!r}", result.returncode == 0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
