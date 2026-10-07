"""tests.test_release_verify_round -- Halo 2.0.6 round 8: signed
releases, both halves.

The v2.0.4 model review's item 7 (the part 2.0.5 left open): every
release carries a checksummed artifact (the tag's own `git archive` +
its sha256 in `checksums.txt`), and `halo update` verifies the target
tag's release HAS that asset before installing -- a tag without one is
a broken or foreign release, not something to install unverified. A
branch/commit target has no release to check (skipped); an unreadable
release (offline, rate-limited) fails OPEN with a warning -- a network
blip must not block an explicitly requested update.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

REPO_DIR = Path(__file__).resolve().parent.parent


def _git_repo(tmp: Path) -> Path:
    (tmp / "file.txt").write_text("contents", encoding="utf-8")
    for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "t@t.invalid"],
                ["git", "config", "user.name", "T"], ["git", "add", "-A"],
                ["git", "commit", "-q", "-m", "init"], ["git", "tag", "-a", "v9.9.9", "-m", "x"]):
        subprocess.run(cmd, cwd=str(tmp), check=True)
    return tmp


@test
def test_build_release_artifact_hashes_the_tags_tree(ctx: Ctx):
    from scripts import release
    tmp = Path(tempfile.mkdtemp(prefix="relart-"))
    _git_repo(tmp)
    artifact, checksums = release.build_release_artifact("9.9.9", repo_dir=tmp)
    ctx.check("the artifact is the tag's tar.gz",
              artifact.name == "halo-harness-9.9.9.tar.gz" and artifact.is_file())
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    body = checksums.read_text(encoding="utf-8").strip()
    ctx.check(f"checksums.txt is the sha256sum layout, got {body!r}",
              body == f"{digest}  halo-harness-9.9.9.tar.gz")


@test
def test_tag_checksums_reads_the_release_assets(ctx: Ctx):
    from halo_harness import update as upd
    got = upd.tag_checksums("v1.0.0", fetch_json=lambda url: {
        "assets": [{"name": "halo-harness-1.0.0.tar.gz", "browser_download_url": "x"},
                   {"name": "checksums.txt", "browser_download_url": "y"}]})
    ctx.check(f"the assets list comes back, got {got}", isinstance(got, list) and len(got) == 2)
    ctx.check("a failed fetch is None", upd.tag_checksums("vX", fetch_json=lambda url: None) is None)
    ctx.check("a malformed release is None",
              upd.tag_checksums("vY", fetch_json=lambda url: {"message": "Not Found"}) is None)


@contextlib.contextmanager
def _fake_update_world(assets):
    """Patch update_cli's seams for cmd_update: a stale build, a newer
    available commit (so the update proceeds), a uv_tool kind with a
    retargetable spec, and a chosen tag_checksums answer (`assets`: a
    list, or None for offline). apply_update records instead of running."""
    from halo_harness import update_cli
    saved = {name: getattr(update_cli.upd, name) for name in
             ("installed_build", "default_channel", "latest_available", "install_kind",
              "commits_between", "commit_is_ancestor", "tag_checksums")}
    saved_apply = update_cli.apply_update
    applied = []
    try:
        update_cli.upd.installed_build = lambda **kw: {"checkout": None, "commit": "abc1234"}
        update_cli.upd.default_channel = lambda b: "stable"
        update_cli.upd.latest_available = lambda *a, **kw: {"channel": "stable", "commit": "def5678"}
        update_cli.upd.install_kind = lambda: {
            "kind": "uv_tool", "spec": "git+https://github.com/roloVibes/Halo-Harness@master",
            "reinstall_cmd": "uv tool install --reinstall git+https://github.com/roloVibes/Halo-Harness@master"}
        update_cli.upd.commits_between = lambda *a, **kw: (["behind"], 1)
        update_cli.upd.commit_is_ancestor = lambda *a, **kw: None
        update_cli.upd.tag_checksums = lambda tag, **kw: assets

        def _apply(*, cmd=None, force=False):
            applied.append(cmd)
            return 0
        update_cli.apply_update = _apply
        yield applied
    finally:
        for name, fn in saved.items():
            setattr(update_cli.upd, name, fn)
        update_cli.apply_update = saved_apply


@test
def test_update_refuses_a_tag_without_checksums(ctx: Ctx):
    from halo_harness import update_cli
    with _fake_update_world(assets=[]):  # a release that VERIFIABLY has no assets
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()) as err:
            rc = update_cli.cmd_update(["--to", "v9.8.7"])
        ctx.check(f"a tag without checksums.txt refuses (exit 1), got rc={rc}", rc == 1)
        ctx.check("the refusal names the tag and the escape hatch",
                  "checksums.txt" in err.getvalue() and "--no-verify" in err.getvalue())


@test
def test_update_installs_when_the_tag_has_checksums(ctx: Ctx):
    from halo_harness import update_cli
    with _fake_update_world(assets=[{"name": "halo-harness-9.8.7.tar.gz"},
                                    {"name": "checksums.txt"}]) as applied:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = update_cli.cmd_update(["--to", "v9.8.7"])
        ctx.check(f"a verified tag installs (exit 0), got rc={rc}", rc == 0)
        ctx.check("the reinstall actually ran", len(applied) == 1)


@test
def test_update_fails_open_offline_and_respects_no_verify(ctx: Ctx):
    from halo_harness import update_cli
    # offline: assets unreadable (None) -> installs with a printed warning
    with _fake_update_world(assets=None) as applied:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            rc = update_cli.cmd_update(["--to", "v9.8.7"])
        ctx.check(f"offline fails OPEN (installs, exit 0), got rc={rc}", rc == 0 and len(applied) == 1)
        ctx.check("the warning says so", "without the checksums check" in err.getvalue())
    # --no-verify: no check at all, even against a verifiably assetless tag
    with _fake_update_world(assets=[]) as applied:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = update_cli.cmd_update(["--to", "v9.8.7", "--no-verify"])
        ctx.check(f"--no-verify installs past an assetless tag, got rc={rc}", rc == 0 and len(applied) == 1)
    # a non-tag target (branch) has no release to check: installs either way
    with _fake_update_world(assets=[]) as applied:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = update_cli.cmd_update(["--to", "master"])
        ctx.check(f"a branch target skips the release check, got rc={rc}", rc == 0 and len(applied) == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
