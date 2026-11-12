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

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

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
