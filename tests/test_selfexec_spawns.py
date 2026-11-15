"""tests.test_selfexec_spawns -- Halo's own interpreter never imports from the working folder when it starts a model
server or a pack's check (3.6.0.0 fix pass, package models-ollama): the R10 rule (`selfexec.python_argv`, the `-P`
form on 3.11+, the bootstrap on 3.10) carried to the spawns R10 left behind.

Pinned:
- the MLX model server's argv (`providers.local_runtime.find_runtime_binary("mlx_lm")` and
  `providers.local_server_cmd.binary("mlx")`) is the safe form: started from a folder that holds its own
  `mlx_lm/server.py`, that file is never run (the server is started with no `cwd=`, so it runs in the project folder);
- the first-run pack's Setup check starts `halo start --yes --no-studio` in the safe form (`selfexec.is_self` sees it,
  so `fix_kw` hands the child this installation);
- no `[sys.executable, "-m", ...]` is left in the package or its shipped packs, but the one that means to import from
  its folder: a pack's own test modules, run from the pack's folder (`packs/test_run_own.py`).
Run: python -m tests.test_selfexec_spawns
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "halo_harness"


class _MlxFound:
    """`importlib.util.find_spec("mlx_lm")` answers as if mlx-lm were installed (it is not, on any CI runner)."""

    def __enter__(self):
        self.real = importlib.util.find_spec
        real = self.real
        importlib.util.find_spec = lambda name, *a, **k: (object() if name == "mlx_lm" else real(name, *a, **k))
        return self

    def __exit__(self, *exc):
        importlib.util.find_spec = self.real
        return False


def _poisoned(tmp: Path) -> "tuple[Path, Path]":
    """A project folder holding its own `mlx_lm` package whose server module leaves a flag when it runs."""
    proj = tmp / "project"
    (proj / "mlx_lm").mkdir(parents=True)
    flag = tmp / "the-project-mlx-ran.txt"
    (proj / "mlx_lm" / "__init__.py").write_text("", encoding="utf-8")
    (proj / "mlx_lm" / "server.py").write_text(f"open({str(flag)!r}, 'a').write('ran')\n", encoding="utf-8")
    return proj, flag


def _runs_project_code(argv: list, proj: Path, flag: Path) -> "tuple[bool, str]":
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONSAFEPATH")}
    r = subprocess.run(list(argv) + ["--help"], cwd=str(proj), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60, stdin=subprocess.DEVNULL)
    return flag.exists(), (r.stdout + r.stderr)[-300:]


@test
def test_the_mlx_server_from_local_runtime_never_runs_the_project_folders_mlx_lm(ctx: Ctx):
    from halo_harness.providers.local_runtime import find_runtime_binary
    from halo_harness.selfexec import python_argv
    with _MlxFound():
        argv = find_runtime_binary("mlx_lm")
    ctx.check(f"the safe form python_argv('mlx_lm.server'), got {argv}", argv == python_argv("mlx_lm.server"))
    tmp = Path(tempfile.mkdtemp(prefix="halo-fx-mlx-"))
    try:
        proj, flag = _poisoned(tmp)
        ran, tail = _runs_project_code(argv or [], proj, flag)
        ctx.check(f"started from a folder holding mlx_lm/server.py, that file did not run, got ran={ran} {tail!r}",
                  not ran)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@test
def test_the_mlx_server_from_local_server_cmd_never_runs_the_project_folders_mlx_lm(ctx: Ctx):
    from halo_harness.providers import local_server_cmd as C
    from halo_harness.selfexec import python_argv
    saved_sys, saved_net = C.sys, os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)
    C.sys = SimpleNamespace(platform="darwin", executable=sys.executable, version_info=sys.version_info)
    try:
        with _MlxFound():
            argv, how = C.binary("mlx")
    finally:
        C.sys = saved_sys
        if saved_net is not None:
            os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = saved_net
    ctx.check(f"the safe form python_argv('mlx_lm.server'), got {argv} ({how})", argv == python_argv("mlx_lm.server"))
    tmp = Path(tempfile.mkdtemp(prefix="halo-fx-mlx-"))
    try:
        proj, flag = _poisoned(tmp)
        ran, tail = _runs_project_code(argv or [], proj, flag)
        ctx.check(f"started from a folder holding mlx_lm/server.py, that file did not run, got ran={ran} {tail!r}",
                  not ran)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@test
def test_the_first_run_packs_setup_check_starts_halo_in_the_safe_form(ctx: Ctx):
    from halo_harness.selfexec import is_self, python_argv
    path = PKG / "templates" / "packs" / "first-run" / "setup" / "check.py"
    spec = importlib.util.spec_from_file_location("_fx_first_run_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    seen: list = []

    def run(argv, **kw):
        seen.append(list(argv))
        return SimpleNamespace(returncode=0)

    mod.subprocess = SimpleNamespace(run=run, DEVNULL=subprocess.DEVNULL)
    rc = mod.main()
    argv = seen[0] if seen else []
    head = python_argv()
    ctx.check(f"one run, exit 0, got {rc} {seen}", rc == 0 and len(seen) == 1)
    ctx.check(f"`halo start --yes --no-studio` in the safe form {head}, got {argv}",
              argv[:len(head)] == head and argv[len(head):] == ["start", "--yes", "--no-studio"])
    ctx.check(f"selfexec.is_self sees Halo's own child (so fix_kw hands it this installation), got {argv}",
              is_self(argv))


@test
def test_halo_update_still_names_the_safe_form_mlx_server_as_this_installs(ctx: Ctx):
    # the updater counts this install's own interpreter serving a model before it replaces the install
    from halo_harness.update import halo_what
    prefix = "/home/u/.local/share/uv/tools/halo-harness"
    got = halo_what(f"{prefix}/bin/python -P -m mlx_lm.server --model /m --port 9", prefix=prefix)
    ctx.check(f"`python -P -m mlx_lm.server` under the install is 'mlx', got {got}", got == "mlx")


SPAWN = re.compile(r"""\w*sys\.executable\s*,\s*(?:["']-[A-Za-z]+["']\s*,\s*)*["']-m["']""")
ALLOWED = {
    # a pack's own test modules run from the pack's folder: the folder IS the code under test
    "halo_harness/packs/test_run_own.py",
}


@test
def test_no_plain_python_dash_m_is_left_in_the_package_or_its_shipped_packs(ctx: Ctx):
    hits = []
    for p in sorted(PKG.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(REPO).as_posix()
        if rel in ALLOWED:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if SPAWN.search(line):
                hits.append(f"{rel}:{i}")
    ctx.check(f"every Halo child is built with selfexec.python_argv (or ext.host.halo_command), got {hits}", not hits)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
