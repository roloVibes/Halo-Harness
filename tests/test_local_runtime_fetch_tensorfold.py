"""tests.test_local_runtime_fetch_tensorfold -- Halo 3.3.9.3 deliverable 1 (the fetched binary): TensorFold's Linux
release archive through the llama-server fetcher's seams (providers/local_runtime_fetch_tf.py on local_runtime_fetch's
download / digest / unpack), against a release list of TensorFold's real shape (v1.2.1's nine assets: the Linux x86_64
and aarch64 archives and the macOS one, each with `.sha256` and `.sha256.sig`; the Mac app's `app-v1.0.0` release) and
a fake fetcher that answers only those URLs. The platform pick, the newest `v` tag that carries both files, the two
digest checks (GitHub's `digest` and the `.sha256` file), the consent sentence, the decline, the unpack under
`~/.halo/runtimes/tensorfold-<tag>/`, the binary found there, `halo local runtime remove`. Never the network.
Run: python -m tests.test_local_runtime_fetch_tensorfold
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.tf_home import TfHome  # noqa: E402

test, TESTS = new_registry()
BASE = "https://github.com/ashhart/TensorFold/releases/download"


def _archive(version: str, plat: str) -> bytes:
    buf = io.BytesIO()
    top = f"tensorfold-{version}-{plat}"
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for rel, data, mode in ((f"{top}/bin/tensorfold-native", b"#!/bin/sh\necho tensorfold-native " + version.encode()
                                 + b"\n", 0o755), (f"{top}/VERSION", version.encode() + b"\n", 0o644),
                                (f"{top}/lib/README", b"runtime libraries\n", 0o644)):
            info = tarfile.TarInfo(rel)
            info.size, info.mode = len(data), mode
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _release(version: str, *, files: dict, tag=None, sha_override=None, digest_override=None) -> dict:
    assets = []
    for plat in ("linux-aarch64", "linux-x86_64", "macos-arm64"):
        name = f"tensorfold-{version}-{plat}.tar.gz"
        data = _archive(version, plat)
        hexd = hashlib.sha256(data).hexdigest()
        sha_text = f"{sha_override or hexd}  {name}\n".encode()
        files[f"{BASE}/v{version}/{name}"] = data
        files[f"{BASE}/v{version}/{name}.sha256"] = sha_text
        assets += [{"name": name, "size": len(data), "browser_download_url": f"{BASE}/v{version}/{name}",
                    "digest": f"sha256:{digest_override or hexd}"},
                   {"name": name + ".sha256", "size": len(sha_text), "browser_download_url": f"{BASE}/v{version}/{name}.sha256",
                    "digest": f"sha256:{hashlib.sha256(sha_text).hexdigest()}"},
                   {"name": name + ".sha256.sig", "size": 64, "browser_download_url": f"{BASE}/v{version}/{name}.sha256.sig",
                    "digest": "sha256:" + "0" * 64}]
    return {"tag_name": tag or f"v{version}", "name": f"TensorFold {version}", "draft": False, "prerelease": False,
            "assets": assets}


def _fixture(**kw):
    files: dict = {}
    app = {"tag_name": "app-v1.0.0", "name": "TensorFold for Mac 1.0.0", "assets": [
        {"name": "TensorFold-1.0.0-arm64.dmg", "size": 1, "browser_download_url": f"{BASE}/app-v1.0.0/x.dmg"},
        {"name": "tensorfold-engine-1.2.1-darwin-arm64-metal.tar.gz", "size": 1,
         "browser_download_url": f"{BASE}/app-v1.0.0/engine.tar.gz"}]}
    mac_only = {"tag_name": "v1.2.2", "name": "TensorFold 1.2.2", "assets": [
        {"name": "tensorfold-1.2.2-macos-arm64.tar.gz", "size": 1, "browser_download_url": f"{BASE}/v1.2.2/m.tar.gz"}]}
    return [app, mac_only, _release("1.2.1", files=files, **kw), _release("1.2.0", files=files)], files


def _fetcher(files: dict, seen: list):
    def fetch(url, headers):
        seen.append(url)
        return (200, files[url]) if url in files else (404, b"")
    return fetch


@test
def test_the_table_and_the_pick(ctx: Ctx):
    from halo_harness.providers.local_runtime_fetch_tf import asset_names, pick, sha256_of
    from halo_harness.tensorfold import platform_word
    rel, _files = _fixture()
    ctx.check("the asset names", asset_names("1.2.1", "linux-x86_64") == ("tensorfold-1.2.1-linux-x86_64.tar.gz",
                                                                         "tensorfold-1.2.1-linux-x86_64.tar.gz.sha256"))
    got = pick(rel, "linux-x86_64")
    ctx.check(f"x86_64: v1.2.1 (the app's and the Mac-only v1.2.2 skipped), got {got and got[0]['tag_name']}",
              got and got[0]["tag_name"] == "v1.2.1" and got[1]["name"] == "tensorfold-1.2.1-linux-x86_64.tar.gz"
              and got[2]["name"].endswith(".sha256"))
    a = pick(rel, "linux-aarch64")
    ctx.check("aarch64 picks its own archive", a and a[1]["name"] == "tensorfold-1.2.1-linux-aarch64.tar.gz")
    ctx.check("the platform words", platform_word("linux", "x86_64") == "linux-x86_64" and platform_word("linux", "arm64")
              == "linux-aarch64" and platform_word("macos", "arm64") == "" and pick(rel, "") is None)
    hexd = "ab" * 32
    ctx.check("the .sha256 file's hex", sha256_of(f"{hexd}  tensorfold-1.2.1-linux-x86_64.tar.gz\n",
                                                  "tensorfold-1.2.1-linux-x86_64.tar.gz") == hexd
              and sha256_of(f"{hexd}  other.tar.gz\n", "tensorfold-1.2.1-linux-x86_64.tar.gz") is None)


@test
def test_ensure_fetches_verifies_and_installs(ctx: Ctx):
    from halo_harness.providers.local_runtime_fetch_tf import ensure
    from halo_harness.tensorfold.requirements import binary
    with TfHome() as h:
        h.set_hf(tensorfold_bin=None)
        from halo_harness.tensorfold import requirements as Q
        Q.SEAMS.update(which=lambda name: None)
        rel, files = _fixture()
        seen: list = []
        asked: list = []
        prefix, lines = ensure(h.state, confirm=lambda q: asked.append(q) or True, os_name="linux", machine="x86_64",
                               fetcher=_fetcher(files, seen), releases=None)
        ctx.check(f"the release list came through the fetcher's seam, got {seen[:1]}", seen and seen[0] ==
                  "https://api.github.com/repos/ashhart/TensorFold/releases?per_page=10" and prefix is None)
        seen.clear()
        prefix, lines = ensure(h.state, confirm=lambda q: asked.append(q) or True, os_name="linux", machine="x86_64",
                               fetcher=_fetcher(files, seen), releases=rel)
        dest = h.state / "runtimes" / "tensorfold-v1.2.1"
        ctx.check(f"the consent sentence first: archive, size, URL, destination, never on PATH, got {lines[:2]}",
                  "tensorfold-1.2.1-linux-x86_64.tar.gz (" in lines[0] and str(dest) in lines[0]
                  and "never added to PATH" in lines[0] and "R580" in lines[0] and lines[1].endswith(
                      f"{BASE}/v1.2.1/tensorfold-1.2.1-linux-x86_64.tar.gz") and asked)
        want = dest / "tensorfold-1.2.1-linux-x86_64" / "bin" / "tensorfold-native"
        ctx.check(f"installed and found, got {prefix} {lines[-1]}", prefix == [str(want)] and want.is_file()
                  and "sha256" in lines[-1] and (dest / "tensorfold-1.2.1-linux-x86_64" / "lib" / "README").is_file())
        ctx.check(f"only the fixture's URLs were asked, sha256 before the archive, got {seen}", seen == [
            f"{BASE}/v1.2.1/tensorfold-1.2.1-linux-x86_64.tar.gz.sha256", f"{BASE}/v1.2.1/tensorfold-1.2.1-linux-x86_64.tar.gz"])
        got, src = binary(h.state)
        ctx.check(f"requirements.binary finds the fetched one, got {got} {src}", got == [str(want)]
                  and "the release Halo fetched (tensorfold-v1.2.1)" == src)
        from halo_harness.local_cli import cmd_local
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_local(["runtime", "remove", "tensorfold-v1.2.1"])
        ctx.check(f"halo local runtime remove takes it out, got {code} {out.getvalue()!r}", code == 0 and not dest.exists())


@test
def test_decline_and_the_two_digest_checks(ctx: Ctx):
    from halo_harness.providers.local_runtime_fetch_tf import ensure
    with TfHome() as h:
        rel, files = _fixture()
        seen: list = []
        prefix, lines = ensure(h.state, confirm=lambda q: False, os_name="linux", machine="aarch64",
                               fetcher=_fetcher(files, seen), releases=rel)
        ctx.check(f"declined: nothing moved, the route said, got {lines[-1]}", prefix is None and not seen
                  and lines[-1].startswith("Declined -- halo local serve --runtime tensorfold --yes")
                  and not (h.state / "runtimes").exists())
        for kw, why in (({"sha_override": "cd" * 32}, "its .sha256 says"), ({"digest_override": "ef" * 32},
                                                                             "GitHub's digest")):
            rel, files = _fixture(**kw)
            prefix, lines = ensure(h.state, confirm=lambda q: True, os_name="linux", machine="x86_64",
                                   fetcher=_fetcher(files, []), releases=rel)
            ctx.check(f"a mismatch ({why}): refused, nothing unpacked, got {lines[-1]}", prefix is None and
                      "digest verification failed" in lines[-1] and why in lines[-1]
                      and not (h.state / "runtimes" / "tensorfold-v1.2.1").exists())
        prefix, lines = ensure(h.state, confirm=lambda q: True, os_name="macos", machine="arm64", releases=rel)
        ctx.check(f"the Mac takes Homebrew, never a fetch, got {lines}", prefix is None and len(lines) == 1
                  and "brew install ashhart/tensorfold/tensorfold" in lines[0])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
