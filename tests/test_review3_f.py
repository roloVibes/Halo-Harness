"""tests.test_review3_f -- 3.0.2.0 review fix pass, round F (install/update):
review items 14 (detached clone), 81 (stable channel retarget), 82 (the
lock pin on reinstall commands) and 155 (other_halo_pids positional match).
Every subprocess is a fake; nothing installs, pulls or lists real processes.
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from halo_harness import update as upd
from halo_harness import update_cli

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
GIT_URL = "git+https://github.com/roloVibes/Halo-Harness"


class _Proc:
    def __init__(self, stdout: str = "", returncode: int = 0):
        self.stdout, self.stderr, self.returncode = stdout, "", returncode


def _fake_run(table: dict):
    def run(cmd, **kwargs):
        joined = " ".join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
        for key, proc in table.items():
            if key in joined:
                return proc
        raise AssertionError(f"unexpected subprocess call: {joined!r}")
    return run


def _checkout() -> Path:
    path = Path(tempfile.mkdtemp(prefix="r3f-clone-"))
    (path / ".git").mkdir()
    return path


def _dir_direct_url(path: Path) -> dict:
    return {"url": f"file://{path.as_posix()}", "dir_info": {}}


_NOT_UV = {"uv tool list": _Proc("other v1\n"), "pipx list": _Proc("nothing\n")}


@test
def test_item14_detached_clone_is_fetched_and_checked_out_not_pulled(ctx: Ctx):
    path = _checkout()
    run_fn = _fake_run({"symbolic-ref": _Proc("", 1), **_NOT_UV})
    k = upd.install_kind(direct_url=_dir_direct_url(path), run_fn=run_fn, target="v3.0.2.0")
    cmd = k["reinstall_cmd"]
    ctx.check(f"kind is dir_checkout, got {k['kind']}", k["kind"] == "dir_checkout")
    ctx.check(f"detached clone: fetch --tags then checkout --detach <tag>, got {cmd!r}",
              "fetch --tags --force origin" in cmd and "checkout --detach v3.0.2.0" in cmd and "pull" not in cmd)
    run_fn = _fake_run({"symbolic-ref": _Proc("refs/heads/master\n", 0), **_NOT_UV})
    cmd = upd.install_kind(direct_url=_dir_direct_url(path), run_fn=run_fn, target="v3.0.2.0")["reinstall_cmd"]
    ctx.check(f"a clone on a branch still fast-forwards, got {cmd!r}", "pull --ff-only" in cmd and "--detach" not in cmd)
    run_fn = _fake_run({"symbolic-ref": _Proc("", 1), **_NOT_UV})
    cmd = upd.install_kind(direct_url=_dir_direct_url(path), run_fn=run_fn, target="origin/master")["reinstall_cmd"]
    ctx.check(f"main channel moves the detached clone to origin/master, got {cmd!r}",
              "checkout --detach origin/master" in cmd)


@test
def test_item14_pick_target_follows_the_channel(ctx: Ctx):
    from halo_harness.update_checkout import pick_target
    stable = {"channel": "stable", "commit": "abc1234", "ref": "v3.0.2.0"}
    main = {"channel": "main", "commit": "def5678", "ref": "master"}
    ctx.check("stable -> the newest tag", pick_target("stable", stable) == "v3.0.2.0")
    ctx.check("main -> origin/<branch>", pick_target("main", main) == "origin/master")
    ctx.check("--to wins", pick_target("stable", stable, "v9.9.9") == "v9.9.9")


@test
def test_item14_exact_tag_checkout_reads_as_the_stable_channel(ctx: Ctx):
    path = _checkout()
    run_fn = _fake_run({"rev-parse": _Proc("c0ffee1\n"), "branch": _Proc("\n"),
                        "describe --exact-match": _Proc("v3.0.1.0\n")})
    build = upd.installed_build(direct_url=_dir_direct_url(path), run_fn=run_fn)
    ctx.check(f"the exact tag becomes the requested revision, got {build}", build["requested_revision"] == "v3.0.1.0")
    ctx.check("so the default channel is stable", upd.default_channel(build) == "stable")
    run_fn = _fake_run({"rev-parse": _Proc("c0ffee1\n"), "branch": _Proc("master\n")})
    build = upd.installed_build(direct_url=_dir_direct_url(path), run_fn=run_fn)
    ctx.check("a branch checkout stays on main", upd.default_channel(build) == "main")


@test
def test_item14_four_part_tags_count_as_releases(ctx: Ctx):
    ctx.check("v3.0.2.0 is newer than v3.0.1.0 and v2.2.0",
              upd._newest_tag(["v2.2.0", "v3.0.1.0", "v3.0.2.0", "nightly"]) == "v3.0.2.0")
    out = "aaaaaaa1111111111111111111111111111111aa\trefs/tags/v3.0.1.0\n"
    ctx.check("stable ls-remote parsing sees a 4-part tag", upd._parse_ls_remote(out, "stable")["ref"] == "v3.0.1.0")


def _stable_rig(spec_rev: str, checksums):
    """Patch the update seams for a pinned git+URL install on the stable channel."""
    names = ("installed_build", "latest_available", "install_kind", "commits_between", "commit_is_ancestor",
             "other_halo_pids", "run", "default_channel", "tag_checksums")
    orig = {n: getattr(upd, n) for n in names}
    ran, asked = [], []
    spec = f"{GIT_URL}@{spec_rev}"
    upd.installed_build = lambda **kw: {"version": "3.0.1.0", "commit": "aaaaaaa", "requested_revision": spec_rev,
                                         "checkout": None, "branch": None, "editable": False}
    upd.default_channel = lambda build=None: "stable"
    upd.latest_available = lambda *a, **kw: {"channel": "stable", "commit": "bbbbbbb", "ref": "v3.0.2.0",
                                              "reason": None, "source": "live"}
    lock = upd.constraints_url(spec_rev)
    upd.install_kind = lambda **kw: {"kind": "uv_tool", "spec": spec,
                                      "reinstall_cmd": f"uv tool install --reinstall --constraints {lock} {spec}"}
    upd.commits_between = lambda *a, **kw: ([], 1)
    upd.commit_is_ancestor = lambda *a, **kw: None
    upd.other_halo_pids = lambda **kw: []
    upd.tag_checksums = lambda tag, **kw: asked.append(tag) or checksums

    def _run(cmd, **kw):
        if isinstance(cmd, list):
            return _Proc("halo 3.0.2.0\n")
        ran.append(cmd)
        return _Proc()
    upd.run = _run
    return orig, ran, asked


def _call(fn, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fn(argv)
    return code, out.getvalue(), err.getvalue()


@test
def test_item81_stable_update_retargets_the_pinned_tag_and_checks_the_release(ctx: Ctx):
    orig, ran, asked = _stable_rig("v3.0.1.0", [{"name": "checksums.txt"}])
    try:
        code, _out, _err = _call(update_cli.cmd_update, [])
    finally:
        for n, v in orig.items():
            setattr(upd, n, v)
    ctx.check(f"exit 0, got {code}", code == 0)
    ctx.check(f"the checksums gate looked at the new tag, got {asked}", asked == ["v3.0.2.0"])
    ctx.check(f"the reinstall targets the NEW tag, got {ran}",
              len(ran) == 1 and f"{GIT_URL}@v3.0.2.0" in ran[0] and "@v3.0.1.0" not in ran[0])
    ctx.check(f"the lock constraint moved to the new tag, got {ran}",
              upd.constraints_url("v3.0.2.0") in ran[0] and upd.constraints_url("v3.0.1.0") not in ran[0])


@test
def test_item81_a_release_without_checksums_is_refused_on_the_default_path(ctx: Ctx):
    orig, ran, asked = _stable_rig("v3.0.1.0", [{"name": "source.tar.gz"}])
    try:
        code, _out, err = _call(update_cli.cmd_update, [])
    finally:
        for n, v in orig.items():
            setattr(upd, n, v)
    ctx.check(f"refused with exit 1, got {code}", code == 1 and "no checksums.txt" in err)
    ctx.check(f"nothing was installed, got {ran}", ran == [])


@test
def test_item82_reinstall_commands_keep_the_lock_pin(ctx: Ctx):
    prefix = Path(tempfile.mkdtemp(prefix="r3f-prefix-"))
    (prefix / "uv-receipt.toml").write_text("[tool]\n", encoding="utf-8")
    d = {"url": "https://github.com/roloVibes/Halo-Harness",
         "vcs_info": {"vcs": "git", "commit_id": "abc1234567", "requested_revision": "v3.0.1.0"}}
    cmd = upd.install_kind(direct_url=d, prefix=str(prefix), run_fn=_fake_run({}))["reinstall_cmd"]
    ctx.check(f"git+ reinstall carries the tag's requirements.lock, got {cmd!r}",
              f"--constraints {upd.constraints_url('v3.0.1.0')}" in cmd)
    clone = _checkout()
    (clone / "requirements.lock").write_text("x==1\n", encoding="utf-8")
    run_fn = _fake_run({"symbolic-ref": _Proc("refs/heads/master\n", 0), **_NOT_UV})
    cmd = upd.install_kind(direct_url=_dir_direct_url(clone), run_fn=run_fn, prefix=str(prefix))["reinstall_cmd"]
    ctx.check(f"a clone reinstall uses the clone's own lock, got {cmd!r}", "--constraints" in cmd and "requirements.lock" in cmd)
    pipx = Path(tempfile.mkdtemp(prefix="r3f-pipx-"))
    (pipx / "pipx_metadata.json").write_text("{}", encoding="utf-8")
    cmd = upd.install_kind(direct_url=d, prefix=str(pipx), run_fn=_fake_run({"uv tool list": _Proc("x v1\n")}))["reinstall_cmd"]
    ctx.check(f"pipx gets the pin through --pip-args, got {cmd!r}", "--pip-args=" in cmd and "--constraint" in cmd)


@test
def test_item82_docs_and_installers_do_not_claim_hash_enforcement(ctx: Ctx):
    bad = ("are enforced by `pip install --require-hashes", "are checked by `uv pip install --require-hashes")
    for rel in ("scripts/install-halo.sh", "scripts/install-halo.ps1", "docs/INSTALL.md"):
        text = (REPO / rel).read_text(encoding="utf-8")
        ctx.check(f"{rel} no longer says the lock's hashes are checked on install", not any(b in text for b in bad))
    ctx.check("INSTALL.md says a constraints file pins versions only",
              "pins versions only" in (REPO / "docs" / "INSTALL.md").read_text(encoding="utf-8"))


@test
def test_item155_only_the_executable_position_names_halo(ctx: Ctx):
    f = upd._is_halo_cmdline
    for cmd in ("grep halo notes.txt", "man halo", "vim halo", "tail -f log | grep halo",
                "bash -c \"sleep 100; echo halo\"", "less /home/u/docs/halo", "code /home/u/projects/halo"):
        ctx.check(f"not halo: {cmd!r}", not f(cmd))
    for cmd in ("/usr/bin/halo --continue", "/usr/bin/python3 /usr/bin/halo --version",
                "/venv/bin/python /home/u/.local/bin/halo --continue", "python3 -m halo_harness -p hi",
                '"C:\\Program Files\\tools\\halo.exe" --continue',
                '"C:\\Python\\python.exe" "C:\\Users\\u\\.local\\bin\\halo.exe" doctor'):
        ctx.check(f"is halo: {cmd!r}", f(cmd))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
