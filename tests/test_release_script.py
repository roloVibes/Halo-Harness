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

import contextlib
import io
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
    # 3.6.0.0 R13: a release starts from origin/master -- the scratch repo's origin is a LOCAL bare repo
    origin = Path(tempfile.mkdtemp(prefix="release-script-origin-")) / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "branch", "-M", "master"], cwd=str(repo), check=True)
    subprocess.run(["git", "remote", "add", "origin", str(origin)], cwd=str(repo), check=True)
    subprocess.run(["git", "push", "-q", "-u", "origin", "master"], cwd=str(repo), check=True, capture_output=True)
    if dirty_extra:
        (repo / "tests" / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
    return repo


_GREEN_GH = []


def _green_gh():
    """One shared all-green fake gh: a test that builds `_fake_run(calls)` per command still sees its own dispatch."""
    if not _GREEN_GH:
        from tests.helpers.fake_gh import FakeGh
        _GREEN_GH.append(FakeGh())
    return _GREEN_GH[0]


def _fake_run(calls: list, gh=None):
    """3.1.0.0 R1: step 0's `gh run` / `gh workflow` calls go to a fake gh
    (tests/helpers/fake_gh.py; both platforms green by default) and are not
    recorded in `calls`, so the release-publishing assertions below see only
    the release's own commands."""
    fake_gh = gh if gh is not None else _green_gh()

    def _run(cmd, **kwargs):
        if len(cmd) >= 2 and cmd[0] == "gh" and cmd[1] in ("run", "workflow"):
            return fake_gh(cmd, **kwargs)
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
                      "uv tool install --reinstall", "git switch -c rc/9.9.9", "git merge --ff-only rc/9.9.9"):
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
def test_install_tag_urls_are_rewritten_on_a_real_run(ctx: Ctx):
    """2.0.10 security finding 26: the install one-liners pin a tag URL;
    the release rewrites README.md and docs/INSTALL.md to the version
    being tagged, in the same commit; a dry run leaves them alone."""
    url = "https://raw.githubusercontent.com/roloVibes/Halo-Harness/v9.9.8/scripts/install-halo.sh | bash"
    ps1 = "irm https://raw.githubusercontent.com/roloVibes/Halo-Harness/v9.9.8/scripts/install-halo.ps1 | iex"
    repo = _scratch_repo("9.9.9")
    readme_path = repo / "README.md"
    nl = chr(10)
    readme_path.write_text(readme_path.read_text(encoding="utf-8") + nl + url + nl, encoding="utf-8")
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "INSTALL.md").write_text("# Install" + nl + nl + url + nl + nl + ps1 + nl, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "tag urls"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "push", "-q", "origin", "master"], cwd=str(repo), check=True, capture_output=True)
    rc = release.main(["9.9.9", "--dry-run"], repo_dir=repo)
    ctx.check(f"dry run exits 0, got {rc}", rc == 0)
    ctx.check("dry run leaves the tag URL alone", "v9.9.8/scripts/install-halo.sh" in readme_path.read_text(encoding="utf-8"))
    calls: list = []
    rc = release.main(["9.9.9", "--no-github-release"], repo_dir=repo, run_fn=_fake_run(calls), pids_fn=lambda: [])
    ctx.check(f"real run exits 0, got {rc}", rc == 0)
    readme = readme_path.read_text(encoding="utf-8")
    install = (repo / "docs" / "INSTALL.md").read_text(encoding="utf-8")
    ctx.check("README one-liner now pins v9.9.9", "v9.9.9/scripts/install-halo.sh" in readme and "v9.9.8/" not in readme)
    ctx.check("INSTALL.md sh and ps1 one-liners pin v9.9.9",
              "v9.9.9/scripts/install-halo.sh" in install and "v9.9.9/scripts/install-halo.ps1" in install and "v9.9.8/" not in install)
    added = [c for c in calls if c[:2] == ["git", "add"]]
    ctx.check(f"docs/INSTALL.md is staged into the release commit, got {added}",
              any("docs/INSTALL.md" in c for c in added))


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
    notes = Path(cmd[cmd.index("--notes-file") + 1]).read_text(encoding="utf-8")  # a file, not an argument
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


# ---- 3.6.0.0 R13: the release goes through the candidate branch rc/<version> (scripts/release_gate.py) ----
def _main_out(argv, repo, gh):
    import contextlib
    import io
    calls: list = []
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = release.main(argv, repo_dir=repo, run_fn=_fake_run(calls, gh), pids_fn=lambda: [])
    return rc, out.getvalue(), err.getvalue(), calls


def _git(calls: list) -> list:
    return [c[1:] for c in calls if c and c[0] == "git" and "archive" not in c]


@test
def test_the_dry_run_names_the_candidate_branch_and_its_gate_and_calls_no_gh(ctx: Ctx):
    from tests.helpers.fake_gh import FakeGh
    repo, gh = _scratch_repo("9.9.9"), FakeGh()
    rc, out, err, calls = _main_out(["9.9.9", "--dry-run"], repo, gh)
    ctx.check(f"exits 0, got {rc} {err}", rc == 0)
    for expected in ("git switch -c rc/9.9.9", "on rc/9.9.9", "git push -u origin rc/9.9.9",
                     "gate: wait for the suites run (push) on rc/9.9.9", "suites (windows, py3.12, shard 3/4)",
                     "git merge --ff-only rc/9.9.9", "git push origin master", "git tag -a v9.9.9"):
        ctx.check(f"the dry run names {expected!r}", expected in out)
    ctx.check(f"no gh and no git call in a dry run, got {gh.calls} {calls}", gh.calls == [] and calls == [])


@test
def test_a_green_candidate_branch_moves_master_then_tags(ctx: Ctx):
    from tests.helpers.fake_gh import FakeGh
    repo, gh = _scratch_repo("9.9.9"), FakeGh(polls=2)
    rc, out, err, calls = _main_out(["9.9.9", "--no-github-release", "--no-install"], repo, gh)
    ctx.check(f"exits 0, got {rc} {err}", rc == 0)
    git = _git(calls)
    order = [["switch", "-c", "rc/9.9.9"], ["push", "-u", "origin", "rc/9.9.9"], ["switch", "master"],
             ["merge", "--ff-only", "rc/9.9.9"], ["push", "origin", "master"], ["push", "origin", "v9.9.9"]]
    ctx.check(f"every step ran, got {git}", all(o in git for o in order))
    idx = [git.index(o) for o in order if o in git]
    ctx.check(f"in order: branch, push it, master, fast-forward, push master, push the tag, got {git}",
              idx == sorted(idx) and len(idx) == len(order))
    commit = next(i for i, c in enumerate(git) if c[:1] == ["commit"])
    tag = next(i for i, c in enumerate(git) if c[:1] == ["tag"])
    ctx.check("the version commit is made on the branch, before its push; the tag after master moved",
              git.index(["switch", "-c", "rc/9.9.9"]) < commit < git.index(["push", "-u", "origin", "rc/9.9.9"])
              and git.index(["push", "origin", "master"]) < tag)
    listed = [c for c in gh.gh_calls() if c[1:3] == ["run", "list"]]
    ctx.check(f"the gate asked for the branch's run of the exact sha, got {listed[:1]}",
              listed and "rc/9.9.9" in listed[0] and _head(repo) in listed[0])
    ctx.check(f"the summary names the accepted run, got {out}",
              "gate: suites run 303 on rc/9.9.9: all 19 required jobs concluded success" in out)
    ctx.check(f"no emergency line when no switch is given, got {out} {err}", "EMERGENCY" not in out + err)


@test
def test_a_red_candidate_branch_stops_the_release_naming_the_jobs_and_tags_nothing(ctx: Ctx):
    from tests.helpers.fake_gh import FakeGh
    win, mac = "suites (windows, py3.12, shard 2/4)", "suites (macos, py3.12, shard 0/4)"
    for gh, argv, want in ((FakeGh(conclusions={win: "failure"}), [], win),
                           (FakeGh(conclusions={"studio-ui (build + drift gate)": None}), [], "studio-ui"),
                           (FakeGh(conclusions={mac: "failure"}), [], mac),
                           (FakeGh(conclusions={"realcheck (macos, installed)": None}), [],
                            "realcheck (macos, installed): missing"),
                           (FakeGh(conclusions={"realcheck (linux)": "failure"}), [], "realcheck (linux): failure")):
        repo = _scratch_repo("9.9.9")
        rc, out, err, calls = _main_out(["9.9.9", "--no-github-release", "--no-install", *argv], repo, gh)
        git = _git(calls)
        ctx.check(f"{want}: exits 1 naming the failing job, got {rc} {err!r}",
                  rc == 1 and "failing jobs" in err and want in err and "nothing was tagged" in err)
        ctx.check(f"{want}: the candidate branch was pushed, then nothing else, got {git}",
                  ["push", "-u", "origin", "rc/9.9.9"] in git and not any(c[:1] == ["tag"] for c in git)
                  and ["push", "origin", "master"] not in git and not any(c[:1] == ["merge"] for c in git))


@test
def test_the_emergency_switches_leave_out_macos_or_realcheck_and_say_so(ctx: Ctx):
    """3.6.0.0: macOS and the real-use check are required by default; each can be left out only by a switch named
    so nobody passes it by accident, and the run says loudly which legs it did not require."""
    from tests.helpers.fake_gh import FakeGh
    mac = "suites (macos, py3.12, shard 0/4)"
    rc, out, err, calls = _main_out(["9.9.9", "--no-github-release", "--no-install", "--emergency-skip-macos-gate"],
                                    _scratch_repo("9.9.9"),
                                    FakeGh(conclusions={mac: "failure", "realcheck (macos)": None}))
    ctx.check(f"--emergency-skip-macos-gate: a red macOS shard and a missing macOS realcheck leg pass, got {rc} {err!r}",
              rc == 0 and "all 13 required jobs concluded success" in out)
    ctx.check(f"it names the switch and the six legs it left out, on stderr and in the summary, got {out!r} {err!r}",
              all("EMERGENCY --emergency-skip-macos-gate" in s and mac in s and "realcheck (macos, installed)" in s
                  for s in (out, err)))
    rc, out, err, calls = _main_out(["9.9.9", "--no-github-release", "--no-install",
                                     "--emergency-skip-realcheck-gate"], _scratch_repo("9.9.9"),
                                    FakeGh(conclusions={"realcheck (windows, installed)": "failure"}))
    ctx.check(f"--emergency-skip-realcheck-gate: a red realcheck leg passes and the switch is named, got {rc} {out!r}",
              rc == 0 and "all 13 required jobs concluded success" in out
              and "EMERGENCY --emergency-skip-realcheck-gate" in out and "realcheck (windows, installed)" in out)
    rc, out, err, calls = _main_out(["9.9.9", "--no-github-release", "--no-install", "--emergency-skip-realcheck-gate"],
                                    _scratch_repo("9.9.9"), FakeGh(conclusions={mac: "failure"}))
    ctx.check(f"the realcheck switch does not let a red macOS shard through, got {rc} {err!r}",
              rc == 1 and f"{mac}: failure" in err)
    rc, out, err, calls = _main_out(["9.9.9", "--dry-run", "--emergency-skip-macos-gate",
                                     "--emergency-skip-realcheck-gate"], _scratch_repo("9.9.9"), FakeGh())
    ctx.check(f"a dry run names both switches and requires the nine others, got {out!r}",
              rc == 0 and "--emergency-skip-macos-gate --emergency-skip-realcheck-gate" in out
              and "all 9 required jobs" in out)
    for old in ("--require-macos", "--require-realcheck"):
        gh = FakeGh()
        rc, out, err, calls = _main_out(["9.9.9", old, "--no-github-release", "--no-install"], _scratch_repo("9.9.9"), gh)
        ctx.check(f"{old} refuses in one line (it is the default now) and runs nothing, got {rc} {err!r}",
                  rc == 1 and "is the default now" in err and err.strip().count("\n") == 0 and calls == [] and gh.calls == [])
        ctx.check(f"{old} is not an option any more", old not in release.build_arg_parser().format_help())


@test
def test_skip_windows_is_gone_and_retries_are_printed_as_warnings(ctx: Ctx):
    from tests.helpers.fake_gh import FakeGh
    repo, gh = _scratch_repo("9.9.9"), FakeGh()
    rc, out, err, calls = _main_out(["9.9.9", "--skip-windows", "--no-github-release", "--no-install"], repo, gh)
    ctx.check(f"--skip-windows refuses in one line and runs nothing, got {rc} {err!r} {calls}",
              rc == 1 and "--skip-windows is gone" in err and err.strip().count("\n") == 0 and calls == [] and gh.calls == [])
    ctx.check("--skip-windows is not an option any more",
              "--skip-windows" not in release.build_arg_parser().format_help())
    gh = FakeGh(retried=[("suites (windows, py3.12, shard 1/4)", "test_studio_local")])
    rc, out, err, calls = _main_out(["9.9.9", "--no-github-release", "--no-install"], _scratch_repo("9.9.9"), gh)
    ctx.check(f"a retry warns in the summary and the release goes on, got {rc} {out}",
              rc == 0 and "warning: suites (windows, py3.12, shard 1/4): test_studio_local -- driver retried once" in out)


def _head(repo) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True, check=True).stdout.strip()


@test
def test_the_shipped_packs_halo_min_follows_the_release(ctx: Ctx):
    """3.2.0.0 R7: the shipped reference pack requires the release it ships in -- `halo: {min: "X.Y"}` becomes the
    version's major.minor in the SAME release commit as `__version__` (tests/test_reference_pack.py pins the pair;
    tests/test_quickstart_docs.py pins `__version__` to the newest dated CHANGELOG section, so no commit before the
    release could carry the bump). A dry run names the step and leaves the file; the pack is staged."""
    repo = _scratch_repo("9.9.9")
    pack = repo / release._SHIPPED_PACK
    pack.parent.mkdir(parents=True)
    pack.write_text('id: doc-review\nhalo_api: {min: "1.0", max: "1.9"}\nhalo: {min: "9.8"}\ncapabilities: [docs.review]\n',
                    encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "the shipped pack"], cwd=str(repo), check=True)
    subprocess.run(["git", "push", "-q", "origin", "master"], cwd=str(repo), check=True, capture_output=True)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = release.main(["9.9.9", "--dry-run"], repo_dir=repo, run_fn=_fake_run([]), pids_fn=lambda: [])
    ctx.check(f"a dry run exits 0 and names the step, got {rc} {out.getvalue()[-400:]!r}",
              rc == 0 and 'halo: {min: "9.9"}' in out.getvalue())
    ctx.check("a dry run leaves pack.yaml as it was", 'halo: {min: "9.8"}' in pack.read_text(encoding="utf-8"))
    calls: list = []
    rc = release.main(["9.9.9", "--no-github-release"], repo_dir=repo, run_fn=_fake_run(calls), pids_fn=lambda: [])
    text = pack.read_text(encoding="utf-8")
    ctx.check(f"a real run sets the major.minor, got {rc} {text!r}", rc == 0 and 'halo: {min: "9.9"}' in text and "9.8" not in text)
    ctx.check("the other lines survive", 'halo_api: {min: "1.0", max: "1.9"}' in text and "capabilities: [docs.review]" in text)
    added = [c for c in calls if c[:2] == ["git", "add"]]
    ctx.check(f"pack.yaml is staged into the release commit, got {added}", any(release._SHIPPED_PACK.as_posix() in c for c in added))


# ---- the judge's pass (3.6.0.0 R13): resume after a red gate, a refused push, the main line as GitHub has it ----
def _real_git(repo, gh, refuse=None):
    """git for real inside the scratch repo (its origin is a local bare repo), gh faked; `refuse`: an argv that fails
    the way a protected or moved remote refuses it."""
    def run(cmd, **kw):
        if cmd and cmd[0] == "gh":
            return gh(cmd, **kw)
        assert cmd and cmd[0] == "git", cmd  # nothing but git, only in the scratch repo
        if refuse is not None and list(cmd) == refuse:
            raise subprocess.CalledProcessError(1, cmd, "", "! [rejected] master -> master (fetch first)")
        r = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True)
        if r.returncode:
            raise subprocess.CalledProcessError(r.returncode, cmd, r.stdout, r.stderr)
        return r
    return run


def _release(repo, gh, refuse=None):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = release.main(["9.9.9", "--no-github-release", "--no-install"], repo_dir=repo,
                          run_fn=_real_git(repo, gh, refuse), pids_fn=lambda: [])
    return rc, out.getvalue(), err.getvalue()


def _g(repo, *a) -> str:
    return subprocess.run(["git", *a], cwd=str(repo), capture_output=True, text=True).stdout.strip()


@test
def test_a_red_gate_then_a_plain_rerun_resumes_and_tags(ctx: Ctx):
    from tests.helpers.fake_gh import FakeGh
    repo = _scratch_repo("9.9.9")
    rc, _o, err = _release(repo, FakeGh(conclusions={"suites (windows, py3.12, shard 2/4)": "failure"}))
    ctx.check(f"1st run, red: exit 1, nothing tagged, got {rc} {err!r}", rc == 1 and _g(repo, "tag") == ""
              and "nothing was tagged" in err)
    version_commit = _g(repo, "rev-parse", "rc/9.9.9")
    rc, out, err = _release(repo, FakeGh())
    ctx.check(f"2nd run on rc/9.9.9 after the job turned green: resumes, exit 0, got {rc} {err!r}",
              rc == 0 and "already holds the version commit" in out)
    ctx.check("no second version commit; master and the tag are that commit, on origin too",
              _g(repo, "rev-parse", "rc/9.9.9") == version_commit == _g(repo, "rev-parse", "master")
              == _g(repo, "rev-parse", "origin/master") == _g(repo, "rev-parse", "v9.9.9^{commit}")
              and _g(repo, "ls-remote", "--tags", "origin", "v9.9.9") != "")
    _g(repo, "switch", "-q", "master")
    rc, out, err = _release(repo, FakeGh())
    ctx.check(f"3rd run from master: the release is there, a re-run finishes cleanly, got {rc} {err!r}", rc == 0)


@test
def test_a_refused_push_names_what_is_done_and_what_is_left(ctx: Ctx):
    from tests.helpers.fake_gh import FakeGh
    repo = _scratch_repo("9.9.9")
    rc, _o, err = _release(repo, FakeGh(), refuse=["git", "push", "origin", "master"])
    ctx.check(f"no traceback: exit 1 with the failed command and git's own line, got {rc} {err!r}",
              rc == 1 and "`git push origin master` failed (exit 1): ! [rejected]" in err)
    ctx.check(f"what is done, then what is left in order, got {err!r}",
              "done: git fetch origin; git switch -c rc/9.9.9" in err and "git merge --ff-only rc/9.9.9" in err
              and 'left to do, in order: git push origin master; git tag -a v9.9.9 -m "Halo Harness 9.9.9"; '
                  "git push origin v9.9.9" in err and "resumes from rc/9.9.9" in err)
    rc, _o, err = _release(repo, FakeGh())
    ctx.check(f"a plain re-run finishes it, got {rc} {err!r}", rc == 0 and _g(repo, "rev-parse", "origin/master")
              == _g(repo, "rev-parse", "rc/9.9.9") and _g(repo, "tag") == "v9.9.9")


@test
def test_a_release_starts_from_origin_master_and_refuses_a_foreign_branch(ctx: Ctx):
    from tests.helpers.fake_gh import FakeGh
    repo = _scratch_repo("9.9.9")
    (repo / "notes.txt").write_text("local only\n", encoding="utf-8")
    _g(repo, "add", "notes.txt")
    _g(repo, "commit", "-qm", "a local commit not on origin")
    rc, _o, err = _release(repo, FakeGh())
    ctx.check(f"HEAD ahead of origin/master: refused in one line before anything is written, got {rc} {err!r}",
              rc == 1 and "is not origin/master" in err and err.strip().count("\n") == 0 and _g(repo, "branch", "--list",
                                                                                                "rc/9.9.9") == "")
    repo = _scratch_repo("9.9.9")
    _g(repo, "branch", "rc/9.9.9")  # a branch of that name that is not a version commit
    rc, _o, err = _release(repo, FakeGh())
    ctx.check(f"an rc branch that is not the version commit: refused, never reused, got {rc} {err!r}",
              rc == 1 and "exists but is not the version commit" in err and "git branch -D rc/9.9.9" in err)


# 3.6.0.4 S batch 2: the release of 3.6.0.3 died on its resume on Windows -- `git show rc/<v>:CHANGELOG.md` was decoded
# with the locale's code page (cp1252), which has no byte 0x9d of the terminal's prompt glyph (U+276F).
_CP1252_CHILD = r"""
import importlib.util, json, locale, sys
locale.getencoding = lambda: "cp1252"            # what a Windows console's Python decodes a pipe with
locale.getpreferredencoding = lambda do_setlocale=True: "cp1252"
spec = importlib.util.spec_from_file_location("halo_release_script", sys.argv[1])
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
from pathlib import Path
repo = Path(sys.argv[2])
out = {}
try:
    out["state"] = list(release.candidate_state("9.9.9", repo))
    out["changelog"] = release._git_out(repo, "show", "rc/9.9.9:CHANGELOG.md")
except Exception as e:
    out["error"] = f"{type(e).__name__}: {e}"
print(json.dumps(out))
"""


@test
def test_the_resume_reads_a_non_ascii_changelog_through_git_as_utf8_whatever_the_code_page(ctx: Ctx):
    import json
    from tests.helpers.fake_gh import FakeGh
    repo = _scratch_repo("9.9.9")
    glyph = "❯"  # bytes E2 9D AF; cp1252 has no 0x9d
    log = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    log = log.replace("- Nothing interesting yet.", f"- Type at the {glyph} prompt; café, naïve, — dashes.")
    (repo / "CHANGELOG.md").write_text(log, encoding="utf-8")
    _g(repo, "commit", "-qam", "a changelog with the prompt glyph")
    _g(repo, "push", "-q", "origin", "master")
    rc, _o, err = _release(repo, FakeGh(conclusions={"suites (windows, py3.12, shard 2/4)": "failure"}))
    ctx.check(f"1st run, red gate: exit 1, rc/9.9.9 holds the version commit, got {rc} {err!r}",
              rc == 1 and _g(repo, "rev-parse", "rc/9.9.9") != "")
    # The read runs in a child Python with UTF-8 mode OFF (CI sets PYTHONUTF8=1) and the locale's encoding forced to
    # cp1252, so the child decodes a pipe as a Windows console's Python does, on every platform.
    child = subprocess.run([sys.executable, "-X", "utf8=0", "-c", _CP1252_CHILD,
                            str(REPO_DIR / "scripts" / "release.py"), str(repo)],
                           capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    lines = (child.stdout or "").strip().splitlines()
    got = json.loads(lines[-1]) if lines and lines[-1].startswith("{") else {"error": (child.stderr or "")[-400:]}
    ctx.check(f"the resume's own read succeeds under cp1252: (True, <rc sha>), got {got}",
              got.get("state") == [True, _g(repo, "rev-parse", "rc/9.9.9")])
    ctx.check(f"git's UTF-8 text comes through whole, the glyph included, got {str(got)[:300]}",
              f"Type at the {glyph} prompt; café, naïve" in (got.get("changelog") or ""))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
