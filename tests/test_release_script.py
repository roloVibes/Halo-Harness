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
# Shaped exactly like the real README.md's own badge markup (the two
# spots `release._README_BADGE_RE` matches) -- "9.9.8" so a real run's
# own rewrite to the target version is observable the same way the
# version-file write already is.
_README_TEMPLATE = (
    '# Scratch\n\n<p align="center">\n'
    '  <img alt="version 9.9.8" src="https://img.shields.io/badge/version-9.9.8-5b4bd6">\n'
    "</p>\n"
)
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
    (repo / "README.md").write_text(_README_TEMPLATE, encoding="utf-8")
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
        # 2.0.6 round 8: build_release_artifact's `git archive -o <path>`
        # is the one command whose SIDE EFFECT the release flow needs --
        # fake it by creating the artifact file, so the sha256 + upload
        # steps have something real to read.
        if len(cmd) >= 2 and cmd[0] == "git" and "archive" in cmd:
            try:
                out = Path(cmd[cmd.index("-o") + 1])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"fake-archive-contents")
            except (OSError, ValueError):
                pass

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
    push/tag/uv ever runs. Proves deliverable 2 steps 2-4. `--no-github-
    release`: this test is about the version/CHANGELOG/commit steps, not
    the (separately pinned, below) GitHub-release step."""
    repo = _scratch_repo("9.9.9")
    calls: list = []
    rc = release.main(["9.9.9", "--no-github-release"], repo_dir=repo, run_fn=_fake_run(calls), pids_fn=lambda: [])
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

    rc = release.main(["9.9.9", "--no-install", "--no-github-release", "--remote", "user@host"], repo_dir=repo,
                       run_fn=_fake_run(calls), pids_fn=_boom_pids)
    ctx.check(f"exits 0, got {rc}", rc == 0)
    ctx.check(f"no uv/ssh call was ever made, got {calls}", not any(c[0] in ("uv", "ssh") for c in calls))


@test
def test_remote_runs_the_exact_documented_ssh_command(ctx: Ctx):
    repo = _scratch_repo("9.9.9")
    calls: list = []
    rc = release.main(["9.9.9", "--remote", "user@host", "--no-github-release"], repo_dir=repo,
                       run_fn=_fake_run(calls), pids_fn=lambda: [])
    ctx.check(f"exits 0, got {rc}", rc == 0)
    ssh_calls = [c for c in calls if c[0] == "ssh"]
    ctx.check(f"exactly one ssh call, to user@host, got {ssh_calls}",
              len(ssh_calls) == 1 and ssh_calls[0][1] == "user@host")
    ctx.check(f"the remote command matches the brief exactly, got {ssh_calls[0][2]!r}",
              ssh_calls[0][2] == "cd ~/Halo-Harness && git fetch --tags && git checkout v9.9.9 "
                                  "&& uv tool install --reinstall . && halo --version")


@test
def test_identity_adds_the_key_and_batch_mode_to_the_ssh_call(ctx: Ctx):
    """2.0.4 release: the remote step ran a plain `ssh user@host`, which fell
    back to a password prompt on a non-terminal stdin and failed. With
    --identity the key precedes the host and ssh is non-interactive; the
    remote command itself is unchanged."""
    repo = _scratch_repo("9.9.9")
    calls: list = []
    rc = release.main(["9.9.9", "--remote", "user@host", "--identity", "some/key", "--no-github-release"],
                       repo_dir=repo, run_fn=_fake_run(calls), pids_fn=lambda: [])
    ctx.check(f"exits 0, got {rc}", rc == 0)
    ssh_calls = [c for c in calls if c[0] == "ssh"]
    ctx.check(f"exactly one ssh call, got {ssh_calls}", len(ssh_calls) == 1)
    cmd = list(ssh_calls[0]) if ssh_calls else []
    ctx.check(f"the key and the non-interactive options precede the host, got {cmd}",
              len(cmd) == 9
              and cmd[1:7] == ["-i", "some/key", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15"]
              and cmd[7] == "user@host")
    ctx.check(f"the remote command is unchanged, got {cmd[-1:]}",
              cmd[-1:] == ["cd ~/Halo-Harness && git fetch --tags && git checkout v9.9.9 "
                           "&& uv tool install --reinstall . && halo --version"])


@test
def test_a_running_halo_session_skips_reinstall_and_prints_the_command_instead(ctx: Ctx):
    repo = _scratch_repo("9.9.9")
    calls: list = []
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = release.main(["9.9.9", "--no-github-release"], repo_dir=repo, run_fn=_fake_run(calls),
                           pids_fn=lambda: [4321])
    ctx.check(f"exits 0, got {rc}", rc == 0)
    ctx.check(f"uv is never actually invoked while a session looks like it's running, got {calls}",
              not any(c[0] == "uv" for c in calls))
    ctx.check("the uv command is printed instead", "uv tool install --reinstall git+" in buf.getvalue())
    ctx.check("the pid is named", "4321" in buf.getvalue())


@test
def test_readme_badge_is_rewritten_on_a_real_run(ctx: Ctx):
    """Deliverable 6 (packaging): the README badge rewrite, through a
    real (non-dry-run) `main()` -- both the alt text and the badge URL
    move to the new version in one pass; every OTHER line in the scratch
    README is untouched."""
    repo = _scratch_repo("9.9.9")
    calls: list = []
    rc = release.main(["9.9.9", "--no-github-release"], repo_dir=repo, run_fn=_fake_run(calls), pids_fn=lambda: [])
    ctx.check(f"exits 0, got {rc}", rc == 0)
    readme = (repo / "README.md").read_text(encoding="utf-8")
    ctx.check(f'alt text now says "version 9.9.9", got {readme!r}', 'alt="version 9.9.9"' in readme)
    ctx.check("badge URL now encodes 9.9.9", "badge/version-9.9.9-5b4bd6" in readme)
    ctx.check("the old version is gone from the badge", "9.9.8" not in readme)
    ctx.check("every other line survives untouched", "# Scratch" in readme)


@test
def test_dry_run_never_touches_the_readme_badge(ctx: Ctx):
    repo = _scratch_repo("9.9.9")
    rc = release.main(["9.9.9", "--dry-run"], repo_dir=repo)
    ctx.check(f"exits 0, got {rc}", rc == 0)
    readme = (repo / "README.md").read_text(encoding="utf-8")
    ctx.check("dry-run leaves the badge exactly as it found it", "version 9.9.8" in readme)


@test
def test_write_readme_badge_version_refuses_cleanly_with_no_badge_markup(ctx: Ctx):
    repo = _scratch_repo("9.9.9")
    (repo / "README.md").write_text("# No badge here at all.\n", encoding="utf-8")
    raised = False
    try:
        release.write_readme_badge_version("9.9.9", repo_dir=repo)
    except release.ReleaseError as e:
        raised = True
        ctx.check(f"the refusal names README.md, got {e}", "README.md" in str(e))
    ctx.check("a missing badge raises ReleaseError (never a traceback)", raised)


@test
def test_github_release_uses_gh_cli_when_present(ctx: Ctx):
    """Deliverable 6 + 2.0.6 round 8: `gh` on PATH is the preferred path --
    the release create AND the artifact/checksums upload both go through
    `run_fn`, never a real subprocess, and the CHANGELOG section's own
    body is passed verbatim as the release notes."""
    repo = _scratch_repo("9.9.9")
    calls: list = []
    rc = release.main(["9.9.9"], repo_dir=repo, run_fn=_fake_run(calls), pids_fn=lambda: [],
                       gh_path_fn=lambda: "/usr/bin/gh")
    ctx.check(f"exits 0, got {rc}", rc == 0)
    gh_calls = [c for c in calls if c and c[0] == "/usr/bin/gh"]
    creates = [c for c in gh_calls if c[1:3] == ["release", "create"]]
    uploads = [c for c in gh_calls if c[1:3] == ["release", "upload"]]
    ctx.check(f"exactly one gh release create call, got {gh_calls}", len(creates) == 1)
    ctx.check(f"and exactly one upload call, got {gh_calls}", len(uploads) == 1)
    cmd = creates[0]
    ctx.check(f"it creates the right tag, got {cmd}", cmd[3] == "v9.9.9")
    notes = cmd[cmd.index("--notes") + 1]
    ctx.check(f"the notes carry the CHANGELOG section's own bullet, got {notes!r}",
              "First bullet of the scratch release." in notes)
    # 2.0.6 round 8: the upload carries the tag's own tar.gz (built by
    # `git archive` of the tag -- the tree and nothing else) and its
    # checksums.txt, both real files under a temp dir
    up = uploads[0]
    ctx.check(f"the upload targets the same tag, got {up}", up[3] == "v9.9.9")
    names = [Path(a).name for a in up[4:]]
    ctx.check(f"the artifact and checksums ride together, got {names}",
              "halo-harness-9.9.9.tar.gz" in names and "checksums.txt" in names)
    ctx.check("curl is never also called when gh is present", not any(c[0] == "curl" for c in calls))


@test
def test_github_release_falls_back_to_curl_with_a_credential_token_when_gh_is_absent(ctx: Ctx):
    """No `gh` on PATH -- `git_credential_token` (itself ALSO routed
    through `run_fn`, never a real `git credential fill`) supplies the
    token, and the POST goes out via `curl`, still only through
    `run_fn`. The real token value is never visible outside that one
    injected seam -- in particular, never in the printed step list.

    round-6-ci-red finding 5: vibes/review.md finding 17 moved the token
    OFF argv (`-H "Authorization: token ..."` used to be readable by any
    local user's `ps`/`/proc`) into a 0600 `-K` curl config file instead
    -- argv now carries only `-K <path>`, never the header. This test's
    old assertion (an `-H Authorization...` pair in argv) pinned the
    PRE-finding-17 transport and went stale the moment finding 17 landed;
    it now reads the config file's own content (the actual transport the
    token rides in today) through the SAME injected `run_fn` seam, before
    `publish_github_release`'s `finally` deletes it."""
    repo = _scratch_repo("9.9.9")
    calls: list = []
    cfg_contents: list = []

    def _run(cmd, **kwargs):
        if cmd and cmd[0] == "curl" and "-K" in cmd:
            cfg_path = cmd[cmd.index("-K") + 1]
            cfg_contents.append(Path(cfg_path).read_text(encoding="utf-8"))
        return _fake_run(calls)(cmd, **kwargs)

    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = release.main(["9.9.9"], repo_dir=repo, run_fn=_run, pids_fn=lambda: [],
                           gh_path_fn=lambda: None, token_fn=lambda repo_dir, run_fn=None: "s3cr3t-token")
    ctx.check(f"exits 0, got {rc}", rc == 0)
    curl_calls = [c for c in calls if c and c[0] == "curl"]
    ctx.check(f"exactly one curl call, got {calls}", len(curl_calls) == 1)
    cmd = curl_calls[0]
    ctx.check(f"it POSTs to the releases endpoint, got {cmd}",
              "https://api.github.com/repos/roloVibes/Halo-Harness/releases" in cmd)
    ctx.check(f"the token never rides on argv any more, got {cmd}",
              not any("s3cr3t-token" in part for part in cmd))
    ctx.check(f"the token rides in the curl config file's own Authorization header, got {cfg_contents!r}",
              len(cfg_contents) == 1 and cfg_contents[0].strip() == 'header = "Authorization: token s3cr3t-token"')
    ctx.check("the real token is never in the printed step list", "s3cr3t-token" not in buf.getvalue())


@test
def test_github_release_refuses_cleanly_when_gh_absent_and_no_token(ctx: Ctx):
    repo = _scratch_repo("9.9.9")
    calls: list = []
    rc = release.main(["9.9.9"], repo_dir=repo, run_fn=_fake_run(calls), pids_fn=lambda: [],
                       gh_path_fn=lambda: None, token_fn=lambda repo_dir, run_fn=None: None)
    ctx.check(f"refuses (nonzero exit) rather than guess, got {rc}", rc != 0)
    ctx.check("no gh/curl call was ever made", not any(c[0] in ("gh", "curl") for c in calls if c))


@test
def test_no_github_release_flag_skips_detection_entirely(ctx: Ctx):
    """`--no-github-release` skips the step OUTRIGHT -- it must never even
    ask whether `gh` is on PATH or a credential token is stored."""
    repo = _scratch_repo("9.9.9")
    calls: list = []

    def _boom():
        raise AssertionError("gh_path_fn must never be consulted under --no-github-release")
    rc = release.main(["9.9.9", "--no-github-release"], repo_dir=repo, run_fn=_fake_run(calls), pids_fn=lambda: [],
                       gh_path_fn=_boom)
    ctx.check(f"exits 0, got {rc}", rc == 0)
    ctx.check("no gh/curl call was ever made", not any(c[0] in ("gh", "curl") for c in calls if c))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
