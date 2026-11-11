"""tests.test_prepush_tree -- what scripts/prepush.py settles before its tiers (Halo 3.4.0.0 D, item 8): a folder
under halo_harness/ or tests/ that holds nothing but __pycache__ is removed (a removed package left importable failed
test_core_focus three times), and on Windows a `bash` that is WSL's is passed over for Git's, in one line.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import prepush_tree as PT  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _touch(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"")


@test
def test_prune_removes_only_folders_that_hold_nothing_but_pycache(ctx: Ctx):
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _touch(repo / "halo_harness" / "gone" / "__pycache__" / "a.cpython-312.pyc")
        _touch(repo / "halo_harness" / "gone" / "deeper" / "__pycache__" / "b.cpython-312.pyc")
        _touch(repo / "halo_harness" / "kept" / "__init__.py")
        _touch(repo / "halo_harness" / "kept" / "__pycache__" / "c.cpython-312.pyc")
        _touch(repo / "tests" / "old_helpers" / "__pycache__" / "d.cpython-312.pyc")
        _touch(repo / "halo_harness" / "studio" / "ui" / "node_modules" / "x" / "__pycache__" / "e.pyc")
        _touch(repo / "halo_harness" / "studio" / "ui" / "package.json")
        got = PT.prune(repo)
        ctx.check(f"the stale folders, deepest first, got {got}",
                  got == ["halo_harness/gone/deeper", "halo_harness/gone", "tests/old_helpers"])
        ctx.check("they are gone", not (repo / "halo_harness" / "gone").exists() and not (repo / "tests" / "old_helpers").exists())
        ctx.check("a package with a source file stays, its cache too", (repo / "halo_harness" / "kept" / "__pycache__").is_dir())
        ctx.check("node_modules is never walked", (repo / "halo_harness" / "studio" / "ui" / "node_modules" / "x").is_dir())
        ctx.check("a second run removes nothing", PT.prune(repo) == [])


@test
def test_wsl_bash_is_recognised_and_the_line_names_both(ctx: Ctx):
    ctx.check("System32's bash is WSL's", PT._is_wsl(r"C:\WINDOWS\system32\bash.exe"))
    ctx.check("the Store's bash is WSL's", PT._is_wsl(r"C:\Users\x\AppData\Local\Microsoft\WindowsApps\bash.exe"))
    ctx.check("Git's bash is not", not PT._is_wsl(r"C:\Program Files\Git\usr\bin\bash.exe"))
    if sys.platform != "win32":
        ctx.check("off Windows nothing is said", PT.bash_fix() == ("", ""))
        return
    import os
    import shutil
    real = shutil.which
    try:
        shutil.which = lambda name, path=None: r"C:\WINDOWS\system32\bash.exe" if name == "bash" else real(name, path=path)
        prefix, line = PT.bash_fix({"PATH": os.environ.get("PATH", "")})
    finally:
        shutil.which = real
    if PT.git_bash() is None:
        ctx.check(f"no Git bash: the fix, and the gate stops, got {line!r}", prefix is None and "run the gate from Git Bash" in line)
    else:
        ctx.check(f"Git's bin folder first, in one line, got {prefix!r} / {line!r}", bool(prefix) and "WSL's" in line
                  and "Git's bash" in line and "\n" not in line)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="prepush tree"))
