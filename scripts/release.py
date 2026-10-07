"""scripts/release.py -- Halo Harness 2.0.4 round 0 (tooling): one command
for the release checklist the orchestrator was running by hand (version
bump, CHANGELOG date, commit, annotated tag, push, local/remote install
refresh). A repo script, not a `halo` subcommand -- it operates on THIS
checkout's own git tree, never on the installed harness.

Run:
    python scripts/release.py <version> [--date YYYY-MM-DD]
                               [--remote user@host ...] [--identity key] [--no-install] [--dry-run]

    python scripts/release.py 2.0.4 --dry-run   # prints every step, runs nothing

No hostname/address/username ever appears in this file except the two the
brief itself fixes (the public `github.com/roloVibes/Halo-Harness` repo
URL, and the literal word "localhost" nowhere here at all) -- every
`--remote` target comes from the command line, never a literal in this
script (tests/test_privacy_scan.py enforces this tree-wide).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Callable, Optional

REPO_DIR = Path(__file__).resolve().parent.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

_VERSION_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"\s*$', re.MULTILINE)
_REPO_URL = "https://github.com/roloVibes/Halo-Harness"
_DIRTY_PATHS = ("halo_harness", "tests", "docs")

# round 2b (deliverable 6): the README's own version badge -- ONE regex
# over both the alt text ("version X.Y.Z") and the shields.io badge URL
# segment ("badge/version-X.Y.Z-<color>") -- `write_readme_badge_version`
# below substitutes the SAME new version into both halves in one pass.
_README_BADGE_RE = re.compile(
    r'(<img alt="version )([^"]+)(" src="https://img\.shields\.io/badge/version-)([^-"]+)(-)')


class ReleaseError(Exception):
    """A plain, one-line refusal reason -- main() prints str(e) to stderr
    and returns 1, never a traceback, for every precondition this script
    checks on purpose (a dirty tree, a missing CHANGELOG section)."""


def dirty_files(repo_dir: Path = REPO_DIR, paths=_DIRTY_PATHS) -> "list[str]":
    """`git status --porcelain`, scoped to `paths` only -- deliverable 2
    step 1: a change under plans/ or scripts/ itself never blocks a
    release; one under the shipped package, its tests, or its docs always
    does. Includes untracked files (git's own default), so a brand-new,
    never-added file under one of these roots refuses too."""
    result = subprocess.run(["git", "status", "--porcelain", "--", *paths],
                             cwd=str(repo_dir), capture_output=True, text=True, check=True)
    return [line[3:] for line in result.stdout.splitlines() if line.strip()]


def read_version(repo_dir: Path = REPO_DIR) -> str:
    init_path = repo_dir / "halo_harness" / "__init__.py"
    m = _VERSION_RE.search(init_path.read_text(encoding="utf-8"))
    if not m:
        raise ReleaseError(f'could not find __version__ = "..." in {init_path}')
    return m.group(1)


def write_version(version: str, repo_dir: Path = REPO_DIR) -> bool:
    """Deliverable 2 step 2: sets `__version__` to `version`, or verifies
    it already is -- returns True iff the file actually changed."""
    init_path = repo_dir / "halo_harness" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")
    new_text, n = _VERSION_RE.subn(f'__version__ = "{version}"', text, count=1)
    if n == 0:
        raise ReleaseError(f'could not find __version__ = "..." in {init_path}')
    if new_text == text:
        return False
    init_path.write_text(new_text, encoding="utf-8")
    return True


def write_readme_badge_version(version: str, repo_dir: Path = REPO_DIR) -> bool:
    """Deliverable 6 (packaging, the owner's own weak-spot report: "the
    README badge embedded in METADATA still says version 2.0.1"): sets
    README.md's version badge -- both the alt text and the badge URL --
    to `version`, in one regex substitution; returns True iff the file
    actually changed. Raises ReleaseError when the badge markup isn't
    found at all (same "a hard requirement a release needs satisfied
    before it starts" rule `unreleased_section_body` below already
    follows for the CHANGELOG section)."""
    readme_path = repo_dir / "README.md"
    text = readme_path.read_text(encoding="utf-8")
    new_text, n = _README_BADGE_RE.subn(rf"\g<1>{version}\g<3>{version}\g<5>", text, count=1)
    if n == 0:
        raise ReleaseError(f"could not find the version badge markup in {readme_path}")
    if new_text == text:
        return False
    readme_path.write_text(new_text, encoding="utf-8")
    return True


def unreleased_section_body(version: str, repo_dir: Path = REPO_DIR) -> str:
    """Deliverable 2 step 3: the body of the exact `## [<version>] -
    unreleased` section (everything up to, not including, the next `## [`
    heading or EOF). Raises ReleaseError when that heading is missing --
    the one hard requirement a release needs satisfied before it starts."""
    text = (repo_dir / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = f"## [{version}] - unreleased"
    start = text.find(heading)
    if start == -1:
        raise ReleaseError(f'CHANGELOG.md has no "{heading}" section -- add it before releasing')
    body_start = start + len(heading)
    next_heading = text.find("\n## [", body_start)
    return text[body_start:] if next_heading == -1 else text[body_start:next_heading]


def set_changelog_date(version: str, date_str: str, repo_dir: Path = REPO_DIR) -> None:
    """Rewrites the section heading from "- unreleased" to "- <date_str>"
    in place; everything else in CHANGELOG.md is untouched."""
    changelog_path = repo_dir / "CHANGELOG.md"
    text = changelog_path.read_text(encoding="utf-8")
    old = f"## [{version}] - unreleased"
    new = f"## [{version}] - {date_str}"
    if old not in text:
        raise ReleaseError(f'CHANGELOG.md has no "{old}" section -- add it before releasing')
    changelog_path.write_text(text.replace(old, new, 1), encoding="utf-8")


def commit_message_body(section_body: str, max_bullets: int = 5) -> str:
    """Deliverable 2 step 4's "message body from the CHANGELOG section's
    first bullets" -- the section's own top-level `- ` lines, verbatim,
    never re-summarized here."""
    bullets = [ln.strip() for ln in section_body.splitlines() if ln.strip().startswith("- ")]
    return "\n".join(bullets[:max_bullets])


def _gh_cli_path() -> "Optional[str]":
    import shutil
    return shutil.which("gh")


def git_credential_token(repo_dir: Path = REPO_DIR, *, run_fn: "Optional[Callable]" = None) -> "Optional[str]":
    """`git credential fill` against github.com -- the token this box is
    ALREADY authenticated with for git itself (gh's own credential
    helper, the OS keychain, a PAT `git config` already points at), so
    there is nothing new to set up or type here. Never printed, never
    logged, never written to a file by this function -- held only in the
    returned string, for `publish_github_release` below to pass straight
    to `curl`'s own argv. `None` when the store has nothing for this host
    (the caller decides what that means); never raises."""
    if run_fn is None:
        run_fn = subprocess.run
    try:
        result = run_fn(["git", "credential", "fill"], cwd=str(repo_dir), capture_output=True, text=True,
                         input="protocol=https\nhost=github.com\n\n", check=False)
    except Exception:
        return None
    for line in (getattr(result, "stdout", "") or "").splitlines():
        if line.startswith("password="):
            token = line[len("password="):].strip()
            return token or None
    return None


def build_release_artifact(version: str, *, repo_dir: Path = REPO_DIR,
                            run_fn: "Optional[Callable]" = None,
                            tmp_dir: "Optional[Path]" = None) -> "tuple[Path, Path]":
    """2.0.6 round 8 (the v2.0.4 review's item 7, the half 2.0.5 left):
    build the tag's own source archive (`git archive` of the tag -- the
    tree and nothing else, no working-tree dirt possible) and its
    `checksums.txt` (`<sha256>  <name>`, the sha256sum layout every
    verifier reads). Returns `(artifact_path, checksums_path)` under
    `tmp_dir` (a real tempfile dir when the caller passes none) -- the
    caller uploads both as the release's assets. `halo update --verify`
    checks the checksums asset exists for the tag before installing."""
    import hashlib
    import tempfile
    if run_fn is None:
        run_fn = subprocess.run
    tag = f"v{version}"
    out_dir = Path(tmp_dir) if tmp_dir is not None else Path(tempfile.mkdtemp(prefix="halo-release-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = out_dir / f"halo-harness-{version}.tar.gz"
    run_fn(["git", "-C", str(repo_dir), "archive", "--format=tar.gz",
            "-o", str(artifact), tag], check=True)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    checksums = out_dir / "checksums.txt"
    checksums.write_text(f"{digest}  {artifact.name}\n", encoding="utf-8")
    return artifact, checksums


def publish_github_release(version: str, notes: str, *, repo_dir: Path = REPO_DIR,
                            run_fn: "Optional[Callable]" = None, gh_path_fn: "Optional[Callable]" = None,
                            token_fn: "Optional[Callable]" = None) -> str:
    """Deliverable 6: publishes a GitHub release for tag `v<version>`
    with `notes` (the CHANGELOG section's own body) -- through the `gh`
    CLI when it's on PATH (the common case: already authenticated as
    whoever is running this release), else `curl` against the REST API
    with a token from `git_credential_token` above. BOTH paths run
    EXCLUSIVELY through `run_fn` -- this function never touches a socket,
    `requests`, or `urllib` itself, so a test can pin the exact command a
    real run would make without any real network call ever being
    possible (host rule: "never call the network directly here"). Raises
    ReleaseError when `gh` is absent AND no credential token is stored --
    `--no-github-release` (the CLI flag, `main()` below) is the documented
    way to skip this step outright rather than hit that refusal."""
    if run_fn is None:
        run_fn = subprocess.run
    tag = f"v{version}"
    gh = (gh_path_fn or _gh_cli_path)()
    if gh:
        artifact, checksums = build_release_artifact(version, repo_dir=repo_dir, run_fn=run_fn)
        run_fn([gh, "release", "create", tag, "--title", f"Halo Harness {version}", "--notes", notes],
               cwd=str(repo_dir), check=True)
        run_fn([gh, "release", "upload", tag, str(artifact), str(checksums)],
               cwd=str(repo_dir), check=True)
        return f"gh release create {tag} + artifact upload (via the gh CLI)"
    token = (token_fn or git_credential_token)(repo_dir, run_fn=run_fn)
    if not token:
        raise ReleaseError("no `gh` CLI on PATH and `git credential fill` returned no usable github.com "
                            "token -- cannot publish the GitHub release (--no-github-release skips this step)")
    url = "https://api.github.com/repos/roloVibes/Halo-Harness/releases"
    payload = json.dumps({"tag_name": tag, "name": f"Halo Harness {version}", "body": notes})
    created = run_fn(["curl", "-sS", "-X", "POST", url, "-H", f"Authorization: token {token}",
                      "-H", "Accept: application/vnd.github+json", "-d", payload],
                     check=True, capture_output=True, text=True)
    # 2.0.6 round 8: upload the artifact + checksums to the release we
    # just made -- the release's numeric id comes from that same response
    # (the upload endpoint needs it). Unparseable response -> the release
    # itself exists but has no assets; say so rather than guessing.
    import re as _re
    m = _re.search(r"\"id\"\s*:\s*(\d+)", getattr(created, "stdout", "") or "")
    if not m:
        return (f"POST {url} (via curl) -- release created, but the asset upload was skipped: "
                "the create response's id could not be read (use the gh CLI for asset uploads)")
    artifact, checksums = build_release_artifact(version, repo_dir=repo_dir, run_fn=run_fn)
    upload_base = f"https://uploads.github.com/repos/roloVibes/Halo-Harness/releases/{m.group(1)}/assets"
    for path in (artifact, checksums):
        run_fn(["curl", "-sS", "-X", "POST", f"{upload_base}?name={path.name}",
                "-H", f"Authorization: token {token}",
                "-H", "Content-Type: application/octet-stream",
                "--data-binary", f"@{path}"], check=True)
    return f"POST {url} + {upload_base} artifact upload (via curl, token from git credential fill)"


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="release.py", description="Tag and ship a Halo Harness release.")
    p.add_argument("version", help='e.g. "2.0.4"')
    p.add_argument("--date", default=None, metavar="YYYY-MM-DD", help="defaults to today")
    p.add_argument("--remote", action="append", default=[], metavar="user@host",
                   help="also refresh the install on this remote over ssh (repeatable)")
    p.add_argument("--identity", default=None, metavar="PATH",
                   help="ssh private key for the --remote refresh; ssh then runs non-interactively "
                        "(BatchMode=yes, ConnectTimeout=15). Without it the call is a plain `ssh user@host`.")
    p.add_argument("--no-install", action="store_true", help="skip refreshing any local/remote install")
    p.add_argument("--no-github-release", action="store_true",
                   help="skip publishing a GitHub release for the tag")
    p.add_argument("--dry-run", action="store_true", help="print every step; run and write nothing")
    return p


def main(argv: "Optional[list]" = None, *, repo_dir: Path = REPO_DIR,
         run_fn: "Optional[Callable]" = None, pids_fn: "Optional[Callable]" = None,
         gh_path_fn: "Optional[Callable]" = None, token_fn: "Optional[Callable]" = None) -> int:
    """`run_fn`/`pids_fn`/`gh_path_fn`/`token_fn` are test seams (default:
    real `subprocess.run` / `halo_harness.update.other_halo_pids` /
    `shutil.which("gh")` / `git_credential_token`) for every command that
    would otherwise push to a real remote, touch `uv`'s real tool
    environment, shell out over ssh, or publish a real GitHub release --
    never monkeypatch `subprocess.run` globally to test this script, pass
    these instead. The read-only `git status` dirty check always runs
    for real (local, hermetic, safe even in a test against a scratch
    repo); only the mutating/network-reaching calls go through `run_fn`."""
    if run_fn is None:
        run_fn = subprocess.run
    if pids_fn is None:
        from halo_harness.update import other_halo_pids as pids_fn  # noqa: F811 -- default seam, deferred import
    args = build_arg_parser().parse_args(argv)
    version = args.version
    date_str = args.date or date.today().isoformat()
    steps: "list[str]" = []

    def step(description: str) -> None:
        steps.append(description)

    try:
        dirty = dirty_files(repo_dir)
        if dirty:
            raise ReleaseError("refusing: the tree is dirty under halo_harness/, tests/, or docs/: "
                                + ", ".join(dirty))
        step("tree is clean under halo_harness/, tests/, docs/")

        current_version = read_version(repo_dir)
        if current_version == version:
            step(f'halo_harness/__init__.py already says __version__ = "{version}"')
        else:
            step(f'set halo_harness/__init__.py::__version__ to "{version}" (was "{current_version}")')
            if not args.dry_run:
                write_version(version, repo_dir)

        section_body = unreleased_section_body(version, repo_dir)  # raises ReleaseError when missing
        step(f'CHANGELOG.md has a "## [{version}] - unreleased" section; set its date to {date_str}')
        if not args.dry_run:
            set_changelog_date(version, date_str, repo_dir)

        # Deliverable 6: the README badge rewrite is staged into the SAME
        # commit as the version bump and the CHANGELOG date below -- one
        # release, one commit, exactly like before this round.
        step(f"rewrite README.md's version badge to {version!r}")
        if not args.dry_run:
            write_readme_badge_version(version, repo_dir)

        body_text = commit_message_body(section_body)
        commit_subject = f"release: Halo Harness {version}"
        full_message = commit_subject if not body_text else f"{commit_subject}\n\n{body_text}"
        step(f"git commit -m {commit_subject!r} (+ {len(body_text.splitlines())} body line(s) from the CHANGELOG)")
        step(f'git tag -a v{version} -m "Halo Harness {version}"')
        step("git push origin master")
        step(f"git push origin v{version}")
        if not args.dry_run:
            run_fn(["git", "add", "halo_harness/__init__.py", "CHANGELOG.md", "README.md"],
                   cwd=str(repo_dir), check=True)
            run_fn(["git", "commit", "-m", full_message], cwd=str(repo_dir), check=True)
            run_fn(["git", "tag", "-a", f"v{version}", "-m", f"Halo Harness {version}"], cwd=str(repo_dir), check=True)
            run_fn(["git", "push", "origin", "master"], cwd=str(repo_dir), check=True)
            run_fn(["git", "push", "origin", f"v{version}"], cwd=str(repo_dir), check=True)

        if args.no_github_release:
            step("--no-github-release: skip publishing the GitHub release")
        else:
            step(f"publish a GitHub release for v{version}, notes = the CHANGELOG section")
            if not args.dry_run:
                release_desc = publish_github_release(version, section_body, repo_dir=repo_dir, run_fn=run_fn,
                                                        gh_path_fn=gh_path_fn, token_fn=token_fn)
                steps[-1] = f"{steps[-1]} ({release_desc})"

        install_cmd = ["uv", "tool", "install", "--reinstall", f"git+{_REPO_URL}@v{version}"]
        if args.no_install:
            step("--no-install: skip refreshing any local or remote install")
        else:
            # A dry run never queries the real process list either -- it
            # is a (harmless) real OS call, and --dry-run's own contract
            # is "run nothing"; this means a dry run always PREVIEWS the
            # "refresh it" branch even if a real run later would print the
            # command instead -- an accepted limitation of a preview.
            others = [] if args.dry_run else (pids_fn() or [])
            if others:
                pid_list = ", ".join(str(p) for p in others)
                step(f"a halo session looks like it's running (pid {pid_list}) -- not reinstalling; "
                     f"run this yourself once it's closed:\n    {' '.join(install_cmd)}")
            else:
                step(f"refresh the local install: {' '.join(install_cmd)}")
                if not args.dry_run:
                    run_fn(install_cmd, check=True)
            for remote in args.remote:
                remote_cmd = (f"cd ~/Halo-Harness && git fetch --tags && git checkout v{version} "
                              f"&& uv tool install --reinstall . && halo --version")
                ssh_cmd = ["ssh"]
                if args.identity:
                    # A release runs unattended: with a key named, ssh must never
                    # fall back to a password prompt (the 2.0.4 remote step did,
                    # and failed on a stdin that is not a terminal).
                    ssh_cmd += ["-i", args.identity, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15"]
                ssh_cmd += [remote, remote_cmd]
                step(f"refresh the install on {remote}: {' '.join(ssh_cmd[:-1])} {remote_cmd!r}")
                if not args.dry_run:
                    run_fn(ssh_cmd, check=True)
    except ReleaseError as e:
        print(f"release.py: {e}", file=sys.stderr)
        return 1

    label = f"Halo Harness {version} ({date_str})" + (" [DRY RUN -- nothing executed]" if args.dry_run else "")
    print("-" * min(72, max(len(label), 40)))
    print(label)
    for i, s in enumerate(steps, 1):
        print(f"  {i}. {s}")
    print("-" * min(72, max(len(label), 40)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
