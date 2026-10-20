"""tests.test_review3_z3 -- pins for fix pass round Z, items Z9-Z10 (Z8, the
level band's docstring, went with the game themes in 3.1.5.0):

  * Z9   `halo --version` under a cp1252 stdout encoding, decoded as UTF-8
  * Z10  an archive install is compared with its release's checksums.txt;
         a git+URL install has no artifact and says nothing

Run: python -m tests.test_review3_z3
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.doc_parts import doc_text  # 3.1.1.0 R3: COMMANDS.md is split into parts
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_z9_version_banner_under_a_cp1252_stream_decodes_as_utf8(ctx: Ctx):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "BRIDGE_STATE_DIR"))}
    env["PYTHONPATH"] = str(REPO_DIR)
    env["PYTHONIOENCODING"] = "cp1252"
    r = subprocess.run([sys.executable, "-m", "halo_harness", "--version"], env=env, cwd=str(REPO_DIR),
                       capture_output=True, encoding="utf-8", errors="replace", timeout=30)
    ctx.check(f"exit 0 under cp1252, got {r.returncode} {r.stderr[-300:]!r}", r.returncode == 0)
    ctx.check("the banner and version line arrive", isinstance(r.stdout, str) and "halo" in r.stdout)
    ctx.check("nothing was written as replacement characters", "�" not in r.stdout)
    src = (REPO_DIR / "tests" / "test_cli_flags.py").read_text(encoding="utf-8")
    body = src[src.index("def test_version_flag_short_and_long"):src.index("def test_proxy_version_delegates")]
    ctx.check("test_cli_flags decodes its children as UTF-8",
              'encoding="utf-8", errors="replace"' in body and "text=True" not in body
              and 'env["PYTHONIOENCODING"] = "utf-8"' in src)


def _assets(names):
    return [{"name": n, "browser_download_url": f"https://example.invalid/{n}"} for n in names]


@test
def test_z10_an_archive_install_is_checked_against_checksums(ctx: Ctx):
    from halo_harness import update_artifact as A
    blob = b"halo release archive bytes"
    digest = hashlib.sha256(blob).hexdigest()
    name = "halo-harness-3.0.2.0.tar.gz"
    url = f"https://github.com/roloVibes/Halo-Harness/releases/download/v3.0.2.0/{name}"
    sums = f"{digest}  {name}\n"
    calls = []

    def fetch_json(u, **_kw):
        calls.append(u)
        return {"assets": _assets([name, "checksums.txt"])}
    d = {"url": url, "archive_info": {"hashes": {"sha256": digest}}}
    r = A.check_installed_artifact(direct_url=d, version="3.0.2.0", fetch_json=fetch_json, fetch_text=lambda u: sums)
    ctx.check(f"match, got {r}", r["status"] == "match" and calls and calls[0].endswith("/tags/v3.0.2.0"))
    bad = {"url": url, "archive_info": {"hash": "sha256=" + "0" * 64}}
    r = A.check_installed_artifact(direct_url=bad, version="3.0.2.0", fetch_json=fetch_json, fetch_text=lambda u: sums)
    ctx.check(f"a different archive is a mismatch, got {r}", r["status"] == "mismatch")
    ctx.check("the report line names it", "mismatch" in (A.report_line(r) or ""))
    local = Path(tempfile.mkdtemp(prefix="z10-")) / name
    local.write_bytes(blob)
    fd = {"url": local.resolve().as_uri(), "archive_info": {}}
    r = A.check_installed_artifact(direct_url=fd, version="3.0.2.0", fetch_json=fetch_json, fetch_text=lambda u: sums)
    ctx.check(f"a local file:// archive with no recorded hash is hashed again, got {r}", r["status"] == "match")
    r = A.check_installed_artifact(direct_url={"url": url, "archive_info": {}}, version="3.0.2.0",
                                   fetch_json=fetch_json, fetch_text=lambda u: sums)
    ctx.check(f"no hash and no local file: no-hash, got {r}", r["status"] == "no-hash")
    r = A.check_installed_artifact(direct_url=d, version="3.0.2.0", fetch_json=lambda u, **k: {"assets": _assets([name])},
                                   fetch_text=lambda u: sums)
    ctx.check(f"a release without checksums.txt says so, got {r}", r["status"] == "no-checksums")
    r = A.check_installed_artifact(direct_url=d, version="3.0.2.0", fetch_json=lambda u, **k: None,
                                   fetch_text=lambda u: sums)
    ctx.check(f"an unreadable release is unavailable, got {r}", r["status"] == "unavailable")


@test
def test_z10_a_git_or_checkout_install_has_no_artifact(ctx: Ctx):
    from halo_harness import update_artifact as A

    def never(*_a, **_k):
        raise AssertionError("no network for an install with no archive")
    git = {"url": "https://github.com/roloVibes/Halo-Harness.git",
           "vcs_info": {"vcs": "git", "commit_id": "a" * 40, "requested_revision": "v3.0.2.0"}}
    r = A.check_installed_artifact(direct_url=git, version="3.0.2.0", fetch_json=never, fetch_text=never)
    ctx.check(f"git+URL: no-artifact, got {r}", r["status"] == "no-artifact" and "no archive" in r["detail"])
    ctx.check("and the report prints nothing for it", A.report_line(r) is None)
    r = A.check_installed_artifact(direct_url={"url": "file:///x", "dir_info": {}}, version="3", fetch_json=never,
                                   fetch_text=never)
    ctx.check("a checkout install: no-artifact", r["status"] == "no-artifact")
    docs = doc_text("COMMANDS.md")
    ctx.check("COMMANDS.md says a git+https install keeps no archive",
              re.search(r"`git\+https://\.\.\.` install and a checkout install keep no archive", docs) is not None)


@test
def test_z10_halo_update_check_prints_the_archive_line_on_stable(ctx: Ctx):
    from halo_harness import update as upd
    from halo_harness import update_artifact as A
    from halo_harness import update_cli
    saved = (upd.installed_build, upd.latest_available, upd.install_kind, upd.commits_between,
             upd.commit_is_ancestor, A.check_installed_artifact, upd.default_channel)
    upd.default_channel = lambda build=None: "stable"
    upd.installed_build = lambda **k: {"version": "3.0.2.0", "commit": "abc1234", "checkout": None}
    upd.latest_available = lambda *a, **k: {"channel": "stable", "commit": "abc1234", "ref": "v3.0.2.0"}
    upd.install_kind = lambda **k: {"kind": "uv_tool", "spec": "x", "reinstall_cmd": "uv tool install x"}
    upd.commits_between = lambda *a, **k: ([], 0)
    upd.commit_is_ancestor = lambda *a, **k: None
    A.check_installed_artifact = lambda **k: {"status": "match", "detail": "halo-harness-3.0.2.0.tar.gz matches"}
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = update_cli.cmd_update(["--check"])
    finally:
        (upd.installed_build, upd.latest_available, upd.install_kind, upd.commits_between,
         upd.commit_is_ancestor, A.check_installed_artifact, upd.default_channel) = saved
    out = buf.getvalue()
    ctx.check(f"--check is up to date (rc 0), got {rc}", rc == 0)
    ctx.check(f"the archive line is printed, got {out!r}", "installed archive: match" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
