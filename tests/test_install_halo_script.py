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


def _uv_lines(out: str) -> list:
    return [ln for ln in out.splitlines() if "uv tool install --reinstall" in ln and ln.startswith("DRY RUN")]


def _stub_bash() -> str:
    """The stub-python tests need a real bash that runs extensionless `#!/bin/sh` files (not WSL's stub)."""
    bash = _require_bash()
    if os.name == "nt" and "git" not in bash.lower():
        raise SkipTest(f"bash here is not Git Bash ({bash})")
    return bash


def _old_python(path: Path) -> None:
    path.write_text("#!/bin/sh\n[ \"$1\" = --version ] && { echo 'Python 3.9.6'; exit 0; }\nexit 1\n", encoding="utf-8")
    path.chmod(0o755)


@test
def test_install_halo_sh_hands_uv_the_python_it_chose(ctx: Ctx):
    """Pass 2: the script chose (and printed) a python, then let `uv tool install` pick an interpreter of its own, so
    HALO_PYTHON only changed what was reported. Both install lines (straight from GitHub and from the clone) now carry
    `--python <the one chosen>`."""
    bash = _require_bash()
    scratch = Path(tempfile.mkdtemp(prefix="install-halo-uvpy-"))
    for args, env in ((["--no-clone", "--dry-run"], _env()),
                      (["--dry-run"], {**_env(), "HALO_CLONE_DIR": str(scratch / "clone"), "HOME": str(scratch)})):
        result = subprocess.run([bash, str(SCRIPT), *args], capture_output=True, text=True, timeout=30, env=env)
        lines = _uv_lines(result.stdout)
        ctx.check(f"{args}: exits 0 with one uv install line, got {result.returncode} {lines!r} {result.stdout[-300:]!r}",
                  result.returncode == 0 and len(lines) == 1)
        ctx.check(f"{args}: the uv line names the python, got {lines!r}", bool(lines) and " --python " in lines[0])
        if os.name != "nt" and lines:
            ctx.check(f"{args}: it is HALO_PYTHON itself, got {lines[0]!r}", lines[0].endswith(f"--python {sys.executable}")
                      or f"--python {sys.executable}" in lines[0])


@test
def test_install_halo_sh_lets_uv_bring_a_python_when_none_here_is_new_enough(ctx: Ctx):
    """Pass 2: a stock Mac (python3 = 3.9, no other) was refused with 'Python 3.10 or newer is required' although uv
    downloads a Python itself. With no HALO_PYTHON named, the script now goes on and asks uv for Python 3.12; and it
    looks at the versioned names bin/halo looks at (python3.14 .. python3.10), so a Homebrew python3.13 with no
    `python3` link is found."""
    bash = _stub_bash()
    scratch = Path(tempfile.mkdtemp(prefix="install-halo-nopy-"))
    stubs = scratch / "bin"
    stubs.mkdir()
    names = ("python3", "python", "python3.14", "python3.13", "python3.12", "python3.11", "python3.10")
    for name in names:
        _old_python(stubs / name)
    env = {**os.environ, "PATH": str(stubs) + os.pathsep + os.environ.get("PATH", ""), "HALO_PYTHON": ""}
    result = subprocess.run([bash, str(SCRIPT), "--no-clone", "--dry-run"], capture_output=True, text=True,
                            timeout=30, env=env)
    out = result.stdout
    lines = _uv_lines(out)
    ctx.check(f"no 3.10+ python: goes on (exit 0), got {result.returncode} {out[-500:]!r}", result.returncode == 0)
    ctx.check(f"says what it looked at and that uv brings 3.12, got {out[:600]!r}",
              "Python 3.9.6" in out and "uv" in out and "3.12" in out)
    ctx.check(f"the uv line asks for Python 3.12, got {lines!r}", bool(lines) and lines[0].endswith("--python 3.12"))
    if os.name == "nt":
        return
    real = stubs / "python3.13"
    real.write_text(f"#!/bin/sh\nexec '{sys.executable}' \"$@\"\n", encoding="utf-8")
    real.chmod(0o755)
    result = subprocess.run([bash, str(SCRIPT), "--no-clone", "--dry-run"], capture_output=True, text=True,
                            timeout=30, env=env)
    lines = _uv_lines(result.stdout)
    ctx.check(f"a python3.13 with no python3 link is chosen and handed to uv, got {result.returncode} {lines!r}",
              result.returncode == 0 and bool(lines) and lines[0].endswith(f"--python {real}"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
