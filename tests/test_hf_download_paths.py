r"""tests.test_hf_download_paths -- a downloaded file stays in its model folder (Halo 3.3.14.0 R2, REVIEW #14 PERMS-8
and #35 PERMS-14; providers/hf_paths.py, providers/hf_download._fetch, providers/local_runtime_fetch.py):

1. names a hub could list -- `C:evil`, `D:x.gguf`, `C:/Users/x/evil.bat`, `..\x`, `../x`, `a/../../x`, `/abs`,
   `x.gguf:stream` -- and a commit with a separator each answer one line (HubError "path") and write nothing;
   `sub/model.gguf` is fine;
2. the `.part` file is named from the checked target: a hub sha256 of `../../evil` does not name it;
3. the runtime fetch removes the archives it downloaded (and its own temp folder), whether the install worked or not.
No network: _fetch refuses before any request; the runtime fetch gets its bytes from a fake fetcher.
Run: python -m tests.test_hf_download_paths
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.config_seed import ConfigHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BAD = ["C:evil", "D:x.gguf", "C:/Users/x/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/evil.bat",
       "..\\x", "../x", "a/../../x", "/abs/x", "x.gguf:stream", "a//b", "."]


def _files(root: Path) -> list:
    return [p for p in root.rglob("*") if p.is_file()]


@test
def test_a_name_that_leaves_the_folder_writes_nothing(ctx: Ctx):
    from halo_harness.providers import hf_download as D
    from halo_harness.providers import hf_paths
    with ConfigHome() as h:
        root = h.home / "models" / "org--repo"
        root.mkdir(parents=True)
        for name in BAD:
            try:
                D._fetch("org/repo", {"name": name, "size": 3}, root, "abc123", None, lambda _s: None, None)
                ctx.check(f"{name!r} refused", False)
            except D.HubError as e:
                ctx.check(f"{name!r}: one line, got {e}", "does not stay in the model folder" in str(e))
        for commit in ("../x", "a/b", "C:x", ".."):
            try:
                hf_paths.target(root, commit, "model.gguf")
                ctx.check(f"commit {commit!r} refused", False)
            except D.HubError:
                pass
        ctx.check("nothing was written", _files(h.home) == [])
        ok = hf_paths.target(root, "abc123", "sub/model.gguf")
        ctx.check(f"a plain sub-folder name is fine, got {ok}", ok == root / "snapshots" / "abc123" / "sub" / "model.gguf")


@test
def test_the_part_is_named_from_the_checked_target(ctx: Ctx):
    from halo_harness.providers import hf_paths
    root = Path(tempfile.mkdtemp(prefix="hf-part-"))
    final = hf_paths.target(root, "abc123", "model.gguf")
    sha = hashlib.sha256(b"x").hexdigest()
    ctx.check("a hex sha256 names it", hf_paths.part(root, {"sha256": sha}, final) == root / "blobs" / f"{sha}.part")
    bad = hf_paths.part(root, {"sha256": "../../../evil", "blob_id": "..\\x"}, final)
    ctx.check(f"a hub value that is not hex does not, got {bad}", bad.parent == root / "blobs"
              and "evil" not in bad.name and len(bad.stem) == 64)


@test
def test_the_runtime_fetch_removes_its_downloads(ctx: Ctx):
    from halo_harness.providers import local_runtime_fetch as F
    with ConfigHome() as h:
        work = h.home / "work"
        work.mkdir()
        zip_path = h.home / "a.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("llama-server", b"pretend binary")
        body = zip_path.read_bytes()
        asset = {"name": "llama-b1-bin-x.zip", "browser_download_url": "https://example.invalid/a.zip",
                 "digest": "sha256:" + hashlib.sha256(body).hexdigest()}
        ok, msg = F.fetch_and_install_llama_server(state_dir=h.state, version_tag="b1", assets=[asset],
                                                   fetcher=lambda u, hd: (200, body), tmp_dir=work)
        ctx.check(f"installed, got {msg!r}", ok)
        ctx.check("the archive is gone from the work folder", list(work.iterdir()) == [])
        made, real = [], F.tempfile.mkdtemp
        F.tempfile.mkdtemp = lambda prefix="": made.append(real(prefix=prefix, dir=str(h.home))) or made[-1]
        try:
            ok, msg = F.fetch_and_install_llama_server(state_dir=h.state, version_tag="b2", assets=[
                {**asset, "digest": "sha256:" + "0" * 64}], fetcher=lambda u, hd: (200, body))
        finally:
            F.tempfile.mkdtemp = real
        ctx.check(f"a failed install, got {msg!r}", not ok and "digest" in msg)
        ctx.check(f"its temp folder is gone, got {made}", made and not Path(made[0]).exists())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
