"""tests.test_rig_real_home_guard -- Halo 3.6.0.1 (fix package "test-rig", batch 2): a test run never writes into the
developer's REAL Claude Code folder, even when the shell has CLAUDE_CONFIG_DIR set (people who keep several Claude
profiles set it; `claude_config_dir()` and `claude_json_path()` rightly follow it over the home in real use).

1. A child python whose environment names a scratch home AND a CLAUDE_CONFIG_DIR standing for the person's real
   folder imports the rig the way every test module does, then resolves and writes Claude's config: both paths are
   inside the scratch home, the "real" `.claude.json` is byte-for-byte untouched, and neither CLAUDE_CONFIG_DIR nor
   GOVERNOR_STATE_DIR reaches a process the test starts.
2. Through tests/run_all.py (a child run over two tiny modules): a module that sets CLAUDE_CONFIG_DIR and does not
   restore it cannot hand it to the next module; the next module's Claude paths are in its own home.
3. run_all's watch of the shell's CLAUDE_CONFIG_DIR: a module that MAKES a file there fails (a named line), a module
   that only CHANGES an existing one gets a warning line and is not failed (the developer's own Claude Code may write
   its profile during a run).
Every child is ended in a finally. Run: python -m tests.test_rig_real_home_guard
"""
from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

_MARKER = b'{"projects": {"/the/real/one": {"allowedTools": ["Bash"]}}, "marker": "the person\'s own file"}\n'


def _child_env(home: Path, real: Path) -> dict:
    env = dict(os.environ)
    for k in ("BRIDGE_STATE_DIR", "GOVERNOR_STATE_DIR"):
        env.pop(k, None)
    env.update(BRIDGE_TEST_HOME=str(home), CLAUDE_CONFIG_DIR=str(real), GOVERNOR_STATE_DIR=str(real / "governor"),
               PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1", OLLAMA_HOST="http://127.0.0.1:9",
               HALO_NO_UPDATER="1")
    return env


def _run_child(args: list, env: dict, timeout: float = 300) -> "tuple[int, str]":
    proc = subprocess.Popen(args, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    try:
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode, out
    finally:
        if proc.poll() is None:
            proc.kill()
        with contextlib.suppress(Exception):
            proc.wait(timeout=10)


def _scratch() -> "tuple[Path, Path, Path]":
    root = Path(tempfile.mkdtemp(prefix="rig-real-home-"))
    home, real = root / "home", root / "real-claude"
    home.mkdir()
    real.mkdir()
    (real / ".claude.json").write_bytes(_MARKER)
    return root, home, real


def _inside(p: str, folder: Path) -> bool:
    try:
        Path(p).resolve().relative_to(folder.resolve())
        return True
    except ValueError:
        return False


_IMPORT_LIKE_A_TEST = r'''
import json, os, subprocess, sys
from tests.helpers.runner import new_registry  # what every test module does first
from halo_harness.config.paths import claude_config_dir, claude_json_path
cfg, cj = claude_config_dir(), claude_json_path()
cj.parent.mkdir(parents=True, exist_ok=True)
cj.write_text('{"projects": {"/scratch/project": {}}}', encoding="utf-8")
cfg.mkdir(parents=True, exist_ok=True)
(cfg / "settings.json").write_text("{}", encoding="utf-8")
grand = subprocess.run([sys.executable, "-c",
                        "import os; print(os.environ.get('CLAUDE_CONFIG_DIR', '') + '|' + os.environ.get('GOVERNOR_STATE_DIR', ''))"],
                       capture_output=True, text=True, timeout=120).stdout.strip()
print("GOT " + json.dumps({"cfg": str(cfg), "cj": str(cj), "grand": grand}))
'''


@test
def test_the_rig_keeps_claude_config_in_the_scratch_home(ctx: Ctx):
    root, home, real = _scratch()
    rc, out = _run_child([sys.executable, "-c", _IMPORT_LIKE_A_TEST], _child_env(home, real))
    got_line = [ln for ln in out.splitlines() if ln.startswith("GOT ")]
    ctx.check(f"the child ran (rc {rc}): {out[-600:]}", rc == 0 and len(got_line) == 1)
    got = json.loads(got_line[0][4:])
    ctx.check(f"claude_config_dir() is inside the scratch home, not the shell's CLAUDE_CONFIG_DIR: {got['cfg']}",
              _inside(got["cfg"], home) and not _inside(got["cfg"], real))
    ctx.check(f"claude_json_path() is inside the scratch home: {got['cj']}",
              _inside(got["cj"], home) and not _inside(got["cj"], real))
    ctx.check("the person's own .claude.json is byte-for-byte untouched",
              (real / ".claude.json").read_bytes() == _MARKER)
    ctx.check("nothing was written into the person's folder", sorted(p.name for p in real.iterdir()) == [".claude.json"])
    ctx.check(f"a process the test starts gets neither CLAUDE_CONFIG_DIR nor GOVERNOR_STATE_DIR: {got['grand']!r}",
              got["grand"] == "|")


_RUN_ALL_CHILD = r'''
import os, sys
sys.path.insert(0, os.environ["RIG_GUARD_PKG_ROOT"])
import tests.run_all as R
names = os.environ["RIG_GUARD_MODULES"].split(",")
R.discover_test_modules = lambda: list(names)
R._real_sessions_snapshot = lambda: set()
sys.exit(R.main([]))
'''

_LEAKS_THE_VARIABLE = '''
import os
from tests.helpers.runner import new_registry
test, TESTS = new_registry()
@test
def test_sets_it_and_does_not_restore(ctx):
    os.environ["CLAUDE_CONFIG_DIR"] = os.environ["RIG_GUARD_REAL"]
'''

_WRITES_CLAUDE_CONFIG = '''
import json, os
from tests.helpers.runner import new_registry
test, TESTS = new_registry()
@test
def test_writes_claude_config(ctx):
    from halo_harness.config.paths import claude_json_path, home
    cj = claude_json_path()
    cj.parent.mkdir(parents=True, exist_ok=True)
    cj.write_text('{"projects": {}}', encoding="utf-8")
    with open(os.environ["RIG_GUARD_OUT"], "w", encoding="utf-8") as f:
        json.dump({"env": os.environ.get("CLAUDE_CONFIG_DIR"), "cj": str(cj), "home": str(home())}, f)
'''

_MAKES_A_REAL_FILE = '''
import os
from tests.helpers.runner import new_registry
test, TESTS = new_registry()
@test
def test_makes_a_file_in_the_real_folder(ctx):
    with open(os.path.join(os.environ["RIG_GUARD_REAL"], "settings.json"), "w") as f:
        f.write("{}")
'''

_CHANGES_A_REAL_FILE = '''
import os
from tests.helpers.runner import new_registry
test, TESTS = new_registry()
@test
def test_changes_the_real_claude_json(ctx):
    with open(os.path.join(os.environ["RIG_GUARD_REAL"], ".claude.json"), "w") as f:
        f.write('{"projects": {}, "changed": "by a test that stands for the person\\'s own Claude Code"}')
'''


def _package(root: Path, sources: list) -> "list[str]":
    pkg = f"_rig_guard_{uuid.uuid4().hex[:8]}"
    (root / "pkgs" / pkg).mkdir(parents=True)
    (root / "pkgs" / pkg / "__init__.py").write_text("", encoding="utf-8")
    names = []
    for i, src in enumerate(sources):
        (root / "pkgs" / pkg / f"test_guard_{i}.py").write_text(src, encoding="utf-8")
        names.append(f"{pkg}.test_guard_{i}")
    return names


def _run_all_over(root: Path, home: Path, real: Path, sources: list) -> "tuple[int, str, list]":
    names = _package(root, sources)
    env = _child_env(home, real)
    env.update(RIG_GUARD_PKG_ROOT=str(root / "pkgs"), RIG_GUARD_MODULES=",".join(names),
               RIG_GUARD_OUT=str(root / "out.json"), RIG_GUARD_REAL=str(real))
    rc, out = _run_child([sys.executable, "-c", _RUN_ALL_CHILD], env)
    return rc, out, names


@test
def test_run_all_drops_the_variable_before_each_module(ctx: Ctx):
    root, home, real = _scratch()
    rc, out, names = _run_all_over(root, home, real, [_LEAKS_THE_VARIABLE, _WRITES_CLAUDE_CONFIG])
    ctx.check(f"the run is green (rc {rc}): {out[-900:]}", rc == 0)
    got = json.loads((root / "out.json").read_text(encoding="utf-8"))
    ctx.check(f"the next module does not see the variable an earlier module left set: {got['env']!r}",
              got["env"] is None)
    ctx.check(f"its .claude.json is in its own home ({got['cj']}, home {got['home']})",
              _inside(got["cj"], Path(got["home"])) and not _inside(got["cj"], real))
    ctx.check("the person's own .claude.json is byte-for-byte untouched",
              (real / ".claude.json").read_bytes() == _MARKER)


@test
def test_run_all_fails_a_module_that_makes_a_file_in_the_real_folder(ctx: Ctx):
    root, home, real = _scratch()
    rc, out, names = _run_all_over(root, home, real, [_MAKES_A_REAL_FILE, _CHANGES_A_REAL_FILE])
    lines = [ln for ln in out.splitlines() if "[REAL CLAUDE CONFIG]" in ln]
    ctx.check(f"the run is red (rc {rc}): {out[-900:]}", rc == 1)
    ctx.check(f"the module that made settings.json is named: {lines}",
              any(names[0] in ln and "settings.json" in ln and "was made" in ln for ln in lines))
    ctx.check(f"the module that only changed .claude.json gets a warning line: {lines}",
              any(names[1] in ln and ".claude.json" in ln and "a warning" in ln for ln in lines))
    ctx.check("exactly one module is failed for it (the maker, not the changer)",
              out.count("[FAIL] real Claude config") == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
