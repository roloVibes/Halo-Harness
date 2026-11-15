r"""tests.test_bare_spawns -- Halo 3.4.1.2 (PACKS-4): on Windows a bare-name subprocess (`git`, `netsh` ...) ran
`<name>.exe` from the current folder, so a repo holding `git.exe` ran it the moment Halo asked git for the branch. Now
(halo_harness/subprocess_safe.py):

1. `import halo_harness` sets `NoDefaultCurrentDirectoryInExePath=1` on Windows before anything spawns (a fresh process
   without it has it after the import), and the children inherit it;
2. every module of the package and the shipped packs spawns through the safe module, which resolves a bare argv[0] to
   its absolute path over the PATH folders, never the current one: a static scan fails on any `subprocess.<fn>([
   "<bare name>", ...])` reached through the standard module, so a new one fails this suite;
3. Windows only: a current folder holding a fake `git.exe` (a copy of hostname.exe) is not what runs, through the safe
   module or through `agent.prompt.collect_git_info`;
4. a test that replaced the standard `subprocess.run` / `Popen` still gets the call as written.
Run: python -m tests.test_bare_spawns
"""
from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
ROOT = Path(__file__).resolve().parent.parent / "halo_harness"
SPAWNS = {"run", "Popen", "call", "check_call", "check_output"}
#: user-facing scaffolds copied into a new pack (run outside Halo, stdlib only), and the safe module itself
SKIP = ("templates/pack-kit/", "subprocess_safe.py", "templates/packs/concord/policy/")


def _stdlib_names(tree) -> "tuple[set, set]":
    mods, funcs = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.asname or a.name for a in node.names if a.name == "subprocess"}
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            funcs |= {a.asname or a.name for a in node.names if a.name in SPAWNS}
    return mods, funcs


def _bare(node) -> bool:
    if not isinstance(node, (ast.List, ast.Tuple)) or not node.elts:
        return False
    first = node.elts[0]
    return isinstance(first, ast.Constant) and isinstance(first.value, str) and bool(first.value) \
        and not any(ch in first.value for ch in "/\\:") and not os.path.isabs(first.value)


def bare_spawns() -> list:
    out = []
    for p in sorted(ROOT.rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if "node_modules" in p.parts or "__pycache__" in p.parts or any(s in rel for s in SKIP):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        mods, funcs = _stdlib_names(tree)
        if not mods and not funcs:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args or not _bare(node.args[0]):
                continue
            f = node.func
            std = (isinstance(f, ast.Attribute) and f.attr in SPAWNS and isinstance(f.value, ast.Name)
                   and f.value.id in mods) or (isinstance(f, ast.Name) and f.id in funcs)
            if std:
                out.append(f"{rel}:{node.lineno}: {node.args[0].elts[0].value!r} through the standard subprocess")
    return out


@test
def test_packs4_no_bare_name_spawn_through_the_standard_module(ctx: Ctx):
    found = bare_spawns()
    ctx.check("every bare-name spawn goes through halo_harness.subprocess_safe (`from halo_harness import "
              f"subprocess_safe as subprocess`); found: {found[:10]}", not found)


@test
def test_packs4_the_import_sets_the_windows_guard(ctx: Ctx):
    env = {k: v for k, v in os.environ.items() if k.lower() != "nodefaultcurrentdirectoryinexepath"}
    env["PYTHONPATH"] = str(ROOT.parent)
    got = subprocess.run([sys.executable, "-c", "import os, halo_harness; "
                          "print(os.environ.get('NoDefaultCurrentDirectoryInExePath', '-'))"],
                         env=env, capture_output=True, text=True, timeout=60).stdout.strip()
    want = "1" if sys.platform == "win32" else "-"
    ctx.check(f"after `import halo_harness`: {got!r} (want {want!r})", got == want)


@test
def test_packs4_a_planted_exe_in_the_cwd_is_not_run(ctx: Ctx):
    if sys.platform != "win32":
        ctx.check("POSIX: exec never searches the current folder for a bare name (PATH folders only)", True)
        return
    from halo_harness import subprocess_safe as S
    real = shutil.which("hostname", path=os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"))
    if not real or not shutil.which("git"):
        ctx.check("no hostname.exe or no git on this box: nothing to plant", True)
        return
    cwd = Path(tempfile.mkdtemp(prefix="bare-spawn-")).resolve()
    shutil.copy(real, cwd / "git.exe")
    ctx.check(f"exe('git') is a PATH folder's, got {S.exe('git')}", Path(S.exe("git")).parent != cwd)
    host = subprocess.run([real], capture_output=True, text=True, timeout=30).stdout.strip()
    old = os.environ.pop("NoDefaultCurrentDirectoryInExePath", None)  # the safe module alone resolves it
    try:
        out = S.run(["git", "--version"], cwd=str(cwd), capture_output=True, text=True, timeout=30).stdout.strip()
    finally:
        if old is not None:
            os.environ["NoDefaultCurrentDirectoryInExePath"] = old
    ctx.check(f"the real git ran, not the planted copy: {out!r}", out.startswith("git version") and out != host)
    from halo_harness.agent.prompt import collect_git_info
    info = str(collect_git_info(cwd))
    ctx.check(f"collect_git_info in that folder never ran the copy, got {info[:120]!r}", host not in info)


def _plant(folder: Path, name: str, body: str) -> Path:
    """A runnable script `name` in `folder`: `<name>.cmd` on Windows, an executable sh file elsewhere."""
    p = folder / (name + (".cmd" if sys.platform == "win32" else ""))
    p.write_text(("@echo off\r\n" + body + "\r\n") if sys.platform == "win32" else ("#!/bin/sh\n" + body + "\n"),
                 encoding="utf-8")
    os.chmod(p, 0o755)
    return p


@test
def test_fx_which_never_answers_from_the_current_folder(ctx: Ctx):
    """3.6.0.0 fx windows-shell: `subprocess_safe.which` is `shutil.which` over the PATH folders alone. A program only
    the current folder holds is not found (Python 3.10 / 3.11's shutil.which on Windows puts the current folder first),
    nor through a relative PATH entry (`.` or an empty one), on every platform."""
    from halo_harness import subprocess_safe as S
    base = Path(tempfile.mkdtemp(prefix="which-cwd-")).resolve()
    here, there = base / "proj", base / "bin"
    here.mkdir()
    there.mkdir()
    name = "halo-fx-probe-tool"
    planted = _plant(here, name, "echo planted")
    old_cwd, old_path = os.getcwd(), os.environ.get("PATH")
    os.chdir(here)
    os.environ["PATH"] = os.pathsep.join([".", "", str(there)])
    try:
        ctx.check(f"only the current folder holds it: None, got {S.which(name)!r}", S.which(name) is None)
        real = _plant(there, name, "echo real")
        got = S.which(name)
        ctx.check(f"the PATH folder's copy, got {got!r}", bool(got) and Path(got).parent == there)
        ctx.check("an absolute path names its own file", S.which(str(planted)) == str(planted))
        alt = S.which(name, path=os.pathsep.join([".", str(there)]))
        ctx.check(f"an explicit path= keeps its absolute folders only, got {alt!r}",
                  bool(alt) and Path(alt).parent == there)
        ctx.check("a folder is never a program", S.which("bin", path=str(base)) is None)
        ctx.check(f"found = {real.name} exists", real.is_file())
    finally:
        os.chdir(old_cwd)
        if old_path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = old_path


@test
def test_fx_windows_which_a_dotted_name_gets_only_runnable_files(ctx: Ctx):
    """Batch 1 repair: for a name with a dot whose ending is not in PATHEXT (`python3.12`) the safe `which` also tried
    the bare file, which Windows cannot run; the standard function tries name + PATHEXT only."""
    if sys.platform != "win32":
        raise SkipTest("PATHEXT is Windows's")
    from halo_harness import subprocess_safe as S
    there = Path(tempfile.mkdtemp(prefix="which-dot-")).resolve()
    (there / "python3.12").write_text("not a program")
    ctx.check(f"a bare `python3.12` is not a program, got {S.which('python3.12', path=str(there))!r}",
              S.which("python3.12", path=str(there)) is None)
    exe = there / "python3.12.exe"
    exe.write_bytes(b"MZ")
    got = S.which("python3.12", path=str(there))
    ctx.check(f"python3.12.exe is, got {got!r}", bool(got) and Path(got).name.lower() == "python3.12.exe")
    ctx.check("a PATHEXT ending names its own file", Path(S.which("python3.12.exe", path=str(there))) == exe)


@test
def test_fx_windows_a_planted_rg_cmd_in_the_project_is_not_run_by_grep(ctx: Ctx):
    """3.6.0.0 fx windows-shell: on Windows `import halo_harness` makes `shutil.which` the safe one, so the ~90 places
    that ask it for a program (Grep's rg, Setup's halo, gh, ffmpeg, nvidia-smi, the updater's python ...) never get a
    file from the current folder, on Python 3.10 / 3.11 too."""
    if sys.platform != "win32":
        ctx.check("POSIX: shutil.which never searches the current folder (PATH folders only)", True)
        return
    import halo_harness  # noqa: F401
    from halo_harness import subprocess_safe as S
    from halo_harness.tools.base import ToolContext
    from halo_harness.tools.grep_tool import GrepTool
    here = Path(tempfile.mkdtemp(prefix="which-rg-")).resolve()
    marker = here / "PLANTED-RAN.txt"
    _plant(here, "rg", f'echo ran> "{marker}"')
    (here / "a.txt").write_text("hello\n", encoding="utf-8")
    old_cwd = os.getcwd()
    os.chdir(here)
    try:
        hit = shutil.which("rg")
        ctx.check(f"shutil.which('rg') is not the project's file, got {hit!r}",
                  not hit or Path(hit).resolve().parent != here)
        res = GrepTool().run({"pattern": "hello", "path": str(here)}, ToolContext(cwd=here))
        ctx.check(f"Grep still searched, got {res.content[:200]!r}", "a.txt" in res.content)
    finally:
        os.chdir(old_cwd)
    ctx.check("the project's rg.cmd never ran", not marker.exists())
    ctx.check("shutil.which is subprocess_safe.which after the import", shutil.which is getattr(S, "which", None))


@test
def test_packs4_a_tests_replacement_still_gets_the_call(ctx: Ctx):
    from halo_harness import subprocess_safe as S
    seen = []
    real_run, real_popen = subprocess.run, subprocess.Popen
    subprocess.run = lambda argv, **kw: seen.append(("run", list(argv)))
    subprocess.Popen = lambda argv, **kw: seen.append(("Popen", list(argv)))
    try:
        S.run(["git", "status"])
        S.Popen(["git", "log"])
    finally:
        subprocess.run, subprocess.Popen = real_run, real_popen
    ctx.check(f"the fake saw the argv as written, got {seen}", seen == [("run", ["git", "status"]),
                                                                       ("Popen", ["git", "log"])])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
