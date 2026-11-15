"""tests.test_install_halo_script -- W3a/W3b: scripts/install-halo.sh (the
teammate install script, README/docs/INSTALL.md's own curl-pipe-bash line)
stays syntactically valid bash, and its `--dry-run` mode genuinely never
installs/uninstalls/clones anything -- it only ever PRINTS the commands it
would run, so a teammate (or this test) can audit it safely before trusting
it with real network/filesystem actions. Runs the real `bash` on PATH
(Git Bash on Windows, the system bash on Linux/macOS) -- skipped outright
where none exists.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
SCRIPT = REPO_DIR / "scripts" / "install-halo.sh"

test, TESTS = new_registry()


def _this_python() -> str:
    """R12: the script is pointed at the running interpreter (a Mac's system python3 is 3.9, too old). On Windows
    the bash found may be WSL's, which cannot run this interpreter: it is left to find its own python there."""
    return "" if os.name == "nt" else sys.executable


def _env() -> dict:
    return {**os.environ, "HALO_PYTHON": _this_python()}


def _require_bash() -> str:
    bash = shutil.which("bash")
    if not bash:
        raise SkipTest("no bash on PATH")
    return bash


@test
def test_install_halo_sh_exists(ctx: Ctx):
    ctx.check(f"scripts/install-halo.sh exists, got {SCRIPT}", SCRIPT.is_file())


@test
def test_install_halo_sh_passes_bash_syntax_check(ctx: Ctx):
    bash = _require_bash()
    result = subprocess.run([bash, "-n", str(SCRIPT)], capture_output=True, text=True, timeout=10)
    ctx.check(f"bash -n exits 0, got {result.returncode} stderr={result.stderr!r}", result.returncode == 0)


@test
def test_install_halo_sh_dry_run_no_clone_prints_commands_and_exits_0(ctx: Ctx):
    """`--no-clone --dry-run` needs no git repo at all -- the simplest
    path that still exercises uv-detection, the install command itself,
    and the verify step, all three as DRY RUN lines, never executed."""
    bash = _require_bash()
    result = subprocess.run([bash, str(SCRIPT), "--no-clone", "--dry-run"],
                             capture_output=True, text=True, timeout=30, env=_env())
    out = result.stdout
    ctx.check(f"exits 0, got {result.returncode} stdout={out!r} stderr={result.stderr!r}", result.returncode == 0)
    ctx.check(f"prints the install command as a dry run, got {out!r}",
              "DRY RUN:" in out and "uv tool install --reinstall git+" in out)
    ctx.check(f"never claims to have actually verified an install, got {out!r}",
              "DRY RUN: would check halo is on PATH" in out)
    ctx.check("never prompts (no confirm() text waits on a real answer)", "[y/N]" not in out or "DRY RUN" in out)


@test
def test_install_halo_sh_dry_run_clone_path_never_touches_the_filesystem(ctx: Ctx):
    """The default (clone) path, pointed at a scoped HALO_CLONE_DIR that
    does not exist yet -- `--dry-run` must print the `git clone`/`uv tool
    install` lines without ever actually creating that directory."""
    bash = _require_bash()
    scratch = Path(tempfile.mkdtemp(prefix="install-halo-dry-run-"))
    clone_dir = scratch / "Halo-Harness-clone-target"
    env = {"HALO_CLONE_DIR": str(clone_dir), "HOME": str(scratch), "PATH": os.environ.get("PATH", ""),
           "HALO_PYTHON": _this_python()}
    result = subprocess.run([bash, str(SCRIPT), "--dry-run"], capture_output=True, text=True, timeout=30, env=env)
    out = result.stdout
    ctx.check(f"exits 0, got {result.returncode} stdout={out!r} stderr={result.stderr!r}", result.returncode == 0)
    ctx.check(f"prints the git clone command as a dry run, got {out!r}",
              "DRY RUN:" in out and "git clone" in out and str(clone_dir) in out)
    ctx.check(f"the clone directory was never actually created, got exists={clone_dir.exists()}",
              not clone_dir.exists())


@test
def test_install_halo_sh_says_which_python_it_looked_at(ctx: Ctx):
    """R12: on a Mac whose system python3 is older than 3.10 the refusal named no python at all. It now lists each
    one it looked at with what it is, and says how to name another (HALO_PYTHON)."""
    bash = _require_bash()
    scratch = Path(tempfile.mkdtemp(prefix="install-halo-py-"))
    missing = (scratch / "no-such-python3").as_posix()
    result = subprocess.run([bash, str(SCRIPT), "--no-clone", "--dry-run"], capture_output=True, text=True,
                            timeout=30, env={**os.environ, "HALO_PYTHON": missing})
    out = result.stdout
    ctx.check(f"exits 1 naming the python it looked at and the way out, got {result.returncode} {out!r}",
              result.returncode == 1 and "Looked at:" in out and f"{missing}: not found" in out
              and "HALO_PYTHON" in out)
    if os.name == "nt":
        return
    old = scratch / "python3"
    old.write_text("#!/bin/sh\n[ \"$1\" = --version ] && { echo 'Python 3.9.6'; exit 0; }\nexit 1\n", encoding="utf-8")
    old.chmod(0o755)
    result = subprocess.run([bash, str(SCRIPT), "--no-clone", "--dry-run"], capture_output=True, text=True,
                            timeout=30, env={**os.environ, "HALO_PYTHON": str(old)})
    ctx.check(f"an old python is named with its version, got {result.stdout!r}",
              result.returncode == 1 and f"{old}: Python 3.9.6" in result.stdout)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
