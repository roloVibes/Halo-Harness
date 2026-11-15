"""tests.test_update_pip_lock -- 3.6.0.0 fix package update-install: `halo update` on a pipx or pip install passes
pip a versions-only copy of requirements.lock. Every line of the lock carries `--hash=sha256:...`, which puts pip
in hash-checking mode for the whole install, and pip cannot hash a git URL or a folder: "Can't verify hashes for
these requirements because we don't have a way to hash version control repositories" / "... because they point to
directories". So every update of a pipx or pip install ended in the updater's restore. uv does not compare a
constraints file's hashes, so its commands keep the lock as it is.

1. pin_locally gives pipx's `--pip-args="--constraint <url>"` and pip's `--constraint <url or path>` a local copy
   without hashes (markers kept), and fails closed as before when the lock cannot be read;
2. the real pip (dry run, no index, nothing installed) accepts the command an update would run for a pip-installed
   checkout -- and refuses the hashed lock, so the test proves what it claims.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402

ensure_scoped_state_dir_once()

from halo_harness import update as upd  # noqa: E402
from halo_harness import update_install as UI  # noqa: E402

test, TESTS = new_registry()

H = "0" * 64
HASHED = (f"# header\nrich==15.0.0 \\\n    --hash=sha256:{H} \\\n    --hash=sha256:{'1' * 64}\n    # via halo-harness\n"
          f"pywin32==312 ; sys_platform == 'win32' \\\n    --hash=sha256:{H}\n").encode()
URL = "https://raw.githubusercontent.com/roloVibes/Halo-Harness/v3.5.0.1/requirements.lock"


def _constraint_file(cmd: str) -> Path:
    m = re.search(r"--constraint\s+[\"']?([^\"'\s]+(?: [^\"'\s]+)*?requirements\.lock)", cmd)
    return Path(m.group(1)) if m else Path("")


@test
def test_pipx_and_pip_get_a_lock_without_hashes(ctx: Ctx):
    spec = "git+https://github.com/roloVibes/Halo-Harness@v3.5.0.1"
    for cmd in (f'pipx install --force --pip-args="--constraint {URL}" {spec}',
                f"python -m pip install --upgrade --constraint {URL} {spec}"):
        got, note = UI.pin_locally(cmd, fetch=lambda u: HASHED)
        lock = _constraint_file(got or "")
        text = lock.read_text(encoding="utf-8") if lock.is_file() else ""
        ctx.check(f"{cmd.split()[0]}: the URL is replaced by a local copy, got {got!r} {note!r}",
                  bool(got) and URL not in got and lock.is_file() and note == "" and got.endswith(spec))
        ctx.check(f"{cmd.split()[0]}: versions and markers kept, no hash left, got {text!r}",
                  "rich==15.0.0" in text and "pywin32==312 ; sys_platform == 'win32'" in text and "--hash" not in text)
    folder = Path(tempfile.mkdtemp(prefix="halo-piplock-"))
    (folder / "requirements.lock").write_bytes(HASHED)
    cmd = f'python -m pip install --upgrade --constraint "{folder / "requirements.lock"}" -e "{folder}"'
    got, _note = UI.pin_locally(cmd)
    lock = _constraint_file(got or "")
    ctx.check(f"a checkout's own lock (a path) gets the same copy, got {got!r}",
              bool(got) and lock.is_file() and lock != folder / "requirements.lock"
              and "--hash" not in lock.read_text(encoding="utf-8"))

    def boom(_u):
        raise OSError("offline")
    got, note = UI.pin_locally(f"python -m pip install --upgrade --constraint {URL} {spec}", fetch=boom)
    ctx.check(f"not fetched: nothing runs, said once, got {got!r} {note!r}", got is None and "nothing was installed" in note)
    uv = f"uv tool install --reinstall --constraints {URL} {spec}"
    got, _note = UI.pin_locally(uv, fetch=lambda u: HASHED)
    ctx.check("uv keeps the lock as it is (it does not compare a constraints file's hashes)",
              "--hash=sha256:" in _constraint_file(got.replace("--constraints", "--constraint")).read_text(encoding="utf-8"))


@test
def test_the_real_pip_accepts_what_an_update_of_a_pip_install_runs(ctx: Ctx):
    try:
        import setuptools  # noqa: F401 -- the tiny project below builds without isolation
        r = subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise ImportError("no pip")
    except ImportError:
        raise SkipTest("pip or setuptools is not in this interpreter")
    proj = Path(tempfile.mkdtemp(prefix="halo-piplock-proj-"))
    (proj / "tinypkg").mkdir()
    (proj / "tinypkg" / "__init__.py").write_text("", encoding="utf-8")
    (proj / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools"]\nbuild-backend = '
                                         '"setuptools.build_meta"\n[project]\nname = "tinypkg"\nversion = "1.0"\n',
                                         encoding="utf-8")
    (proj / "requirements.lock").write_bytes(HASHED)
    prefix = tempfile.mkdtemp(prefix="halo-piplock-prefix-")  # no uv receipt, no pipx metadata: the pip branch

    def no_tools(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, "", "")
    cmd = upd._tool_reinstall_cmd(prefix, no_tools, editable=False, path=str(proj))
    ctx.check(f"the pip branch with the checkout's lock, got {cmd!r}", " -m pip install" in cmd and "--constraint" in cmd)
    dry = " -m pip install --dry-run --no-index --no-deps --no-build-isolation --disable-pip-version-check "

    def pip(c):
        return subprocess.run(c.replace(" -m pip install ", dry, 1), shell=True, cwd=str(proj), capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=240)
    raw = pip(cmd)
    ctx.check(f"control: pip refuses the hashed lock for a folder, got {raw.returncode} {raw.stderr[-300:]!r}",
              raw.returncode != 0 and "verify hashes" in (raw.stdout + raw.stderr))
    pinned, note = UI.pin_locally(cmd)
    done = pip(pinned or "")
    ctx.check(f"the command an update runs passes pip, got {done.returncode} {(done.stdout + done.stderr)[-400:]!r}",
              done.returncode == 0 and "tinypkg" in done.stdout and note == "")
    shutil.rmtree(proj, ignore_errors=True)


_PYPROJ = ('[build-system]\nrequires = ["setuptools"]\nbuild-backend = "setuptools.build_meta"\n'
           '[project]\nname = "{name}"\nversion = "{ver}"\ndependencies = [{deps}]\n'
           '[tool.setuptools]\npackages = ["{pkg}"]\n')


@test
def test_a_pip_checkout_update_gets_the_lock_of_the_release_it_pulls(ctx: Ctx):
    """Checker, batch 1: the lock was copied when the update started, BEFORE the command's own `git pull`, so pip
    got the old release's pins against the new release's pyproject (ResolutionImpossible, then a restore). Real git,
    two local wheels (dep 1.0 / 2.0), a clone one release behind, pip --dry-run --no-index: nothing is installed."""
    import hashlib
    try:
        import setuptools  # noqa: F401
        for c in (["git", "--version"], [sys.executable, "-m", "pip", "--version"]):
            if subprocess.run(c, capture_output=True, text=True, timeout=60).returncode != 0:
                raise OSError(c[0])
    except (ImportError, OSError):
        raise SkipTest("git, pip or setuptools is missing here")
    root = Path(tempfile.mkdtemp(prefix="halo-piplock-pull-"))
    wh = root / "wheels"

    def sh(args):
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        if r.returncode != 0:
            raise AssertionError(f"{args}: {r.stdout[-300:]} {r.stderr[-500:]}")
    for ver in ("1.0", "2.0"):
        d = root / f"dep-{ver}"
        (d / "dep").mkdir(parents=True)
        (d / "dep" / "__init__.py").write_text("", encoding="utf-8")
        (d / "pyproject.toml").write_text(_PYPROJ.format(name="dep", ver=ver, deps="", pkg="dep"), encoding="utf-8")
        sh([sys.executable, "-m", "pip", "wheel", "-q", "--no-deps", "--no-build-isolation", "--no-index",
            "--disable-pip-version-check", "-w", str(wh), str(d)])
    origin = root / "origin"
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-C", str(origin)]
    sh(["git", "init", "-q", str(origin)])
    (origin / "app").mkdir()
    (origin / "app" / "__init__.py").write_text("", encoding="utf-8")

    def release(ver):
        h = hashlib.sha256(next(wh.glob(f"dep-{ver}-*.whl")).read_bytes()).hexdigest()
        (origin / "pyproject.toml").write_text(_PYPROJ.format(name="app", ver=ver, deps=f'"dep=={ver}"', pkg="app"),
                                               encoding="utf-8")
        (origin / "requirements.lock").write_text(f"dep=={ver} \\\n    --hash=sha256:{h}\n", encoding="utf-8")
        sh(git + ["add", "-A"])
        sh(git + ["commit", "-q", "-m", f"v{ver}"])
    release("1.0")
    clone = root / "clone"
    sh(["git", "clone", "-q", str(origin), str(clone)])
    release("2.0")  # the new release: the clone has not pulled it yet

    def no_tools(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, "", "")
    from halo_harness import update_checkout as uc
    prefix = tempfile.mkdtemp(prefix="halo-piplock-prefix-")  # no uv receipt, no pipx metadata: the pip branch
    cmd = (uc.sync_cmd(str(clone), upd._quote_for_shell, detached=False, target=None) + " && "
           + upd._tool_reinstall_cmd(prefix, no_tools, editable=False, path=str(clone)))
    pinned, note = UI.pin_locally(cmd)  # what update_cli / update_detached do before the runner runs the command
    dry = f' -m pip install --dry-run --no-index --find-links "{wh}" --no-build-isolation --disable-pip-version-check '
    r = subprocess.run((pinned or "").replace(" -m pip install ", dry, 1), shell=True, cwd=str(clone),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    out = r.stdout + r.stderr
    ctx.check(f"pip resolves the pulled release with its own pins, got {r.returncode} {out[-600:]!r} for {pinned!r}",
              r.returncode == 0 and note == "" and re.search(r"Would install.*app-2\.0", out) is not None
              and "dep-2.0" in out)
    shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
