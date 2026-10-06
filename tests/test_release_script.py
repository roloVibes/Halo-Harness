"""tests.test_release_script -- scripts/release.py (2.0.4 round 0
tooling): drives the real script's main() against a scratch git repo
(never this repo -- a release run must never touch the actual Halo-
Harness checkout), asserting the printed step list, both refusals (a
dirty tree, a missing CHANGELOG section), and the version write. Every
mutating/network-reaching call (git commit/tag/push, uv, ssh) goes
through an injected `run_fn` stub in every non-dry-run test here -- a
real one of those must never run from inside this suite. The read-only
`git status` dirty check always runs for real against the scratch repo
(local, hermetic, safe).
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

# Loaded by file path (never via sys.path + `import release`) so this
# suite can't collide with, or be fooled by, some other "release" module
# anywhere else on sys.path.
_spec = importlib.util.spec_from_file_location("halo_release_script", REPO_DIR / "scripts" / "release.py")
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)

_INIT_PY_TEMPLATE = '"""scratch package for test_release_script.py."""\n\n__version__ = "{version}"\n'
_CHANGELOG_TEMPLATE = """# Changelog

## [{version}] - {heading_date}

### Tooling

- **First bullet of the scratch release.**
- **Second bullet of the scratch release.**

## [0.0.1] - 2026-01-01

### Earlier

- Nothing interesting yet.
"""


def _scratch_repo(version: str = "9.9.9", *, unreleased: bool = True, dirty_extra: bool = False) -> Path:
    """A real (throwaway) git repo shaped just enough like Halo-Harness
    for release.py to operate on: halo_harness/__init__.py (at a
    DIFFERENT version, so a real run's "step 2" write is observable) and
    CHANGELOG.md, `git init`-ed and committed clean unless `dirty_extra`
    asks for an uncommitted file under tests/."""
    repo = Path(tempfile.mkdtemp(prefix="release-script-test-"))
    (repo / "halo_harness").mkdir()
    (repo / "tests").mkdir()
    (repo / "docs").mkdir()
    (repo / "halo_harness" / "__init__.py").write_text(_INIT_PY_TEMPLATE.format(version="9.9.8"), encoding="utf-8")
    heading_date = "unreleased" if unreleased else "2026-01-01"
    (repo / "CHANGELOG.md").write_text(
        _CHANGELOG_TEMPLATE.format(version=version, heading_date=heading_date), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=str(repo), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(repo), check=True)
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "scratch init"], cwd=str(repo), check=True)
    if dirty_extra:
        (repo / "tests" / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
    return repo


def _fake_run(calls: list):
    def _run(cmd, **kwargs):
        calls.append(cmd)

        class _R:
            returncode = 0
            stdout = ""
        return _R()
    return _run


@test
def test_dry_run_prints_the_full_step_list_and_touches_nothing(ctx: Ctx):
    repo = _scratch_repo("9.9.9")
    rc = release.main(["9.9.9", "--dry-run"], repo_dir=repo)
    ctx.check(f"dry-run exits 0 on a clean repo with a proper CHANGELOG section, got {rc}", rc == 0)
    init_text = (repo / "halo_harness" / "__init__.py").read_text(encoding="utf-8")
    ctx.check("dry-run never writes the version file", "9.9.8" in init_text and "9.9.9" not in init_text)
    changelog_text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    ctx.check("dry-run never dates the CHANGELOG section", "[9.9.9] - unreleased" in changelog_text)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=str(repo), capture_output=True, text=True,
                             check=True)
    ctx.check(f"dry-run leaves the tree exactly as clean as it found it, got {status.stdout!r}",
              status.stdout.strip() == "")


@test
def test_dry_run_step_list_names_every_deliverable_2_step(ctx: Ctx):
    """Pins the step list itself -- the brief's own "asserts the step
    list" -- against the exact actions deliverable 2 names."""
    repo = _scratch_repo("9.9.9")
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = release.main(["9.9.9", "--dry-run"], repo_dir=repo)
    ctx.check(f"exits 0, got {rc}", rc == 0)
    out = buf.getvalue()
    for expected in ('__init__.py::__version__ to "9.9.9"', "unreleased", "git commit",
                      "git tag -a v9.9.9", "git push origin master", "git push origin v9.9.9",
                      "uv tool install --reinstall"):
        ctx.check(f"the printed summary mentions {expected!r}, got:\n{out}", expected in out)


@test
def test_refuses_on_a_dirty_tree_dry_run_and_real(ctx: Ctx):
    repo = _scratch_repo("9.9.9", dirty_extra=True)
    rc = release.main(["9.9.9", "--dry-run"], repo_dir=repo)
    ctx.check(f"dry-run refuses (nonzero exit) on a dirty tree under tests/, got {rc}", rc != 0)

    def _boom(cmd, **kwargs):
        raise AssertionError(f"no subprocess call may run after the dirty-tree refusal, got {cmd}")

    rc_real = release.main(["9.9.9"], repo_dir=repo, run_fn=_boom, pids_fn=lambda: [])
    ctx.check(f"the real (non-dry-run) path refuses identically, got {rc_real}", rc_real != 0)


@test
def test_refuses_when_the_changelog_section_is_missing(ctx: Ctx):
    repo = _scratch_repo("9.9.9", unreleased=False)  # dated, not "unreleased" -- the exact missing-section case
    rc = release.main(["9.9.9", "--dry-run"], repo_dir=repo)
    ctx.check(f"refuses when CHANGELOG.md has no '## [9.9.9] - unreleased' section, got {rc}", rc != 0)


@test
def test_version_write_updates_init_py_and_dates_the_changelog(ctx: Ctx):
    """The non-dry-run path, every subprocess call stubbed -- no real git
    push/tag/uv ever runs. Proves deliverable 2 steps 2-4."""
    repo = _scratch_repo("9.9.9")
    calls: list = []
    rc = release.main(["9.9.9"], repo_dir=repo, run_fn=_fake_run(calls), pids_fn=lambda: [])
    ctx.check(f"a real run exits 0 on a clean, well-formed scratch repo, got {rc}", rc == 0)
    init_text = (repo / "halo_harness" / "__init__.py").read_text(encoding="utf-8")
    ctx.check(f'__init__.py now says 9.9.9, got {init_text!r}', '__version__ = "9.9.9"' in init_text)
    changelog_text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    ctx.check("the CHANGELOG section is now dated, not 'unreleased'",
              "[9.9.9] - unreleased" not in changelog_text and "[9.9.9] - 20" in changelog_text)
    ctx.check(f"git commit/tag/push all went through the stub, got {calls}",
              any(c[:2] == ["git", "commit"] for c in calls)
              and any(c[:2] == ["git", "tag"] for c in calls)
              and any(c[:2] == ["git", "push"] for c in calls))
    commit_call = next(c for c in calls if c[:2] == ["git", "commit"])
    message = commit_call[commit_call.index("-m") + 1]
    ctx.check(f"the commit message's subject line matches the brief, got {message!r}",
              message.startswith("release: Halo Harness 9.9.9"))
    ctx.check(f"the commit message body carries the CHANGELOG section's first bullets, got {message!r}",
              "First bullet of the scratch release." in message)


@test
def test_version_is_verified_not_rewritten_when_it_already_matches(ctx: Ctx):
    """`write_version` directly (bypassing main()/the git checks): the
    scratch repo's __init__.py starts at "9.9.8" (see _scratch_repo), so
    the first call to "9.9.9" is a real change; calling it again with the
    SAME target version is deliverable 2 step 2's "or verifies it already
    is" -- a no-op, not a second write."""
    repo = _scratch_repo("9.9.9")
    changed = release.write_version("9.9.9", repo_dir=repo)
    ctx.check(f"the first call changes 9.9.8 -> 9.9.9, got changed={changed}", changed is True)
    changed_again = release.write_version("9.9.9", repo_dir=repo)
    ctx.check(f"the second call is a no-op (already 9.9.9), got changed={changed_again}", changed_again is False)


@test
def test_no_install_skips_the_local_and_remote_install_steps(ctx: Ctx):
    repo = _scratch_repo("9.9.9")
    calls: list = []

    def _boom_pids():
        raise AssertionError("other_halo_pids must never be consulted under --no-install")

    rc = release.main(["9.9.9", "--no-install", "--remote", "user@host"], repo_dir=repo,
                       run_fn=_fake_run(calls), pids_fn=_boom_pids)
    ctx.check(f"exits 0, got {rc}", rc == 0)
    ctx.check(f"no uv/ssh call was ever made, got {calls}", not any(c[0] in ("uv", "ssh") for c in calls))


@test
def test_remote_runs_the_exact_documented_ssh_command(ctx: Ctx):
    repo = _scratch_repo("9.9.9")
    calls: list = []
    rc = release.main(["9.9.9", "--remote", "user@host"], repo_dir=repo, run_fn=_fake_run(calls), pids_fn=lambda: [])
    ctx.check(f"exits 0, got {rc}", rc == 0)
    ssh_calls = [c for c in calls if c[0] == "ssh"]
    ctx.check(f"exactly one ssh call, to user@host, got {ssh_calls}",
              len(ssh_calls) == 1 and ssh_calls[0][1] == "user@host")
    ctx.check(f"the remote command matches the brief exactly, got {ssh_calls[0][2]!r}",
              ssh_calls[0][2] == "cd ~/Halo-Harness && git fetch --tags && git checkout v9.9.9 "
                                  "&& uv tool install --reinstall . && halo --version")


@test
def test_a_running_halo_session_skips_reinstall_and_prints_the_command_instead(ctx: Ctx):
    repo = _scratch_repo("9.9.9")
    calls: list = []
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = release.main(["9.9.9"], repo_dir=repo, run_fn=_fake_run(calls), pids_fn=lambda: [4321])
    ctx.check(f"exits 0, got {rc}", rc == 0)
    ctx.check(f"uv is never actually invoked while a session looks like it's running, got {calls}",
              not any(c[0] == "uv" for c in calls))
    ctx.check("the uv command is printed instead", "uv tool install --reinstall git+" in buf.getvalue())
    ctx.check("the pid is named", "4321" in buf.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
