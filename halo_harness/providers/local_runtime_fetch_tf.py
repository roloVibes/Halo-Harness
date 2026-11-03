"""halo_harness.providers.local_runtime_fetch_tf -- Halo 3.3.9.3: TensorFold's Linux release archive, fetched the way
providers/local_runtime_fetch.py fetches llama-server (one more `repo` + asset-name table on the same fetcher: the
release list, the download, the digest check, the unpack), into `~/.halo/runtimes/tensorfold-<tag>/` -- never on PATH,
removed by `halo local runtime remove` (or `halo local runtime remove tensorfold-<tag>`).

The release table (README "Linux with an NVIDIA GPU", tools/release/package.sh, the v1.2.1 release's asset list; from
the source, unverified against a live run): tags `v<version>` (the Mac app's `app-v<version>` releases carry no Linux
archive and are skipped); per platform `tensorfold-<version>-<platform>.tar.gz` (`linux-x86_64`, `linux-aarch64`) and
its `tensorfold-<version>-<platform>.tar.gz.sha256` ("<hex>  <archive name>", sha256sum's format); the archive holds
`tensorfold-<version>-<platform>/bin/tensorfold-native` with its `lib/` and `share/` beside it (kept together, as the
README says). Two checks before the unpack: GitHub's per-asset `digest` (local_runtime_fetch.verify_digest) when the
release lists one, and the `.sha256` file's own hex -- both must agree with the bytes.

    TABLE = {"linux-x86_64": ..., "linux-aarch64": ...}       asset_names(version, platform) -> (archive, sha256 file)
    pick(releases, platform) -> (release, archive asset, sha256 asset) | None   newest `v` tag that carries both
    sha256_of(text, name) -> hex | None                       the .sha256 file's hex for that archive name
    install(state_dir, release, archive, sha, *, fetcher=None, tmp_dir=None) -> (ok, message)
    ensure(state_dir, *, confirm, os_name, machine, fetcher=None, releases=None) -> (argv prefix | None, lines)
        the consent sentence (the archive, its size, the URL, the destination) first; nothing moves without a yes
"""

from __future__ import annotations

import hashlib
import re
import tempfile
from pathlib import Path
from typing import Optional

from halo_harness.tensorfold import REPO, platform_word

TABLE = {"linux-x86_64": "tensorfold-{v}-linux-x86_64.tar.gz", "linux-aarch64": "tensorfold-{v}-linux-aarch64.tar.gz"}
_TAG = re.compile(r"^v(\d+(?:\.\d+)*)$")


def asset_names(version: str, plat: str) -> "tuple[str, str]":
    name = TABLE[plat].format(v=version)
    return name, name + ".sha256"


def _vt(v: str) -> tuple:
    return tuple(int(x) for x in v.split("."))


def pick(releases, plat: str):
    if plat not in TABLE:
        return None
    tagged = []
    for r in releases or []:
        m = _TAG.match(str((r or {}).get("tag_name") or "")) if isinstance(r, dict) else None
        if m and not r.get("draft"):
            tagged.append((_vt(m.group(1)), m.group(1), r))
    for _k, v, r in sorted(tagged, key=lambda t: t[0], reverse=True):
        want, sha = asset_names(v, plat)
        assets = {a.get("name"): a for a in r.get("assets") or [] if isinstance(a, dict)}
        if want in assets and sha in assets:
            return r, assets[want], assets[sha]
    return None


def sha256_of(text: str, name: str) -> Optional[str]:
    for line in str(text or "").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == name and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            return parts[0].lower()
        if len(parts) == 1 and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            return parts[0].lower()
    return None


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def install(state_dir, release: dict, archive: dict, sha: dict, *, fetcher=None,
            tmp_dir: Optional[Path] = None) -> "tuple[bool, str]":
    from halo_harness.providers.local_runtime import runtimes_dir
    from halo_harness.providers.local_runtime_fetch import download_asset, unpack_archive, verify_digest
    tag = str(release.get("tag_name") or "latest")
    work = Path(tmp_dir) if tmp_dir is not None else Path(tempfile.mkdtemp(prefix="halo-tf-dl-"))
    sha_path, arc_path = work / sha["name"], work / archive["name"]
    ok, msg = download_asset(sha["browser_download_url"], sha_path, fetcher=fetcher)
    if not ok:
        return False, f"{sha['name']}: {msg}"
    want = sha256_of(sha_path.read_text(encoding="utf-8", errors="replace"), archive["name"])
    if want is None:
        return False, f"{sha['name']} names no sha256 for {archive['name']}"
    ok, msg = download_asset(archive["browser_download_url"], arc_path, fetcher=fetcher)
    if not ok:
        return False, f"{archive['name']}: {msg}"
    if archive.get("digest") and not verify_digest(arc_path, archive["digest"]):
        return False, f"digest verification failed for {archive['name']} (GitHub's digest)"
    if _sha(arc_path) != want:
        return False, f"digest verification failed for {archive['name']} (its .sha256 says {want[:12]}...)"
    dest = runtimes_dir(state_dir) / f"tensorfold-{tag}"
    ok, msg = unpack_archive(arc_path, dest)
    return (True, f"installed TensorFold {tag} into {dest} (sha256 {want[:12]}... checked)") if ok else (False, msg)


def ensure(state_dir, *, confirm, os_name: str, machine: str, fetcher=None,
           releases=None) -> "tuple[Optional[list], list]":
    from halo_harness.providers.local_runtime import runtimes_dir
    from halo_harness.providers.local_runtime_fetch import fetch_release_list
    from halo_harness.providers.ollama_panel import human_bytes
    from halo_harness.tensorfold import LINUX_NEEDS
    from halo_harness.tensorfold.requirements import fetched
    plat = platform_word(os_name, machine)
    if not plat:
        from halo_harness.tensorfold import install_line
        return None, [f"no tensorfold binary: {install_line(os_name, machine)}"]
    got = releases if releases is not None else fetch_release_list(REPO, per_page=10, fetcher=fetcher)
    if not got:
        return None, [f"could not read TensorFold's release list ({REPO}): download tensorfold-<version>-{plat}.tar.gz "
                      f"and its .sha256 from its releases page and set huggingface.tensorfold_bin to its bin/tensorfold-native"]
    chosen = pick(got, plat)
    if chosen is None:
        return None, [f"no TensorFold release lists a {plat} archive with its .sha256"]
    release, archive, sha = chosen
    dest = runtimes_dir(state_dir) / f"tensorfold-{release.get('tag_name')}"
    lines = [f"Halo found no tensorfold binary and can download {archive['name']} ({human_bytes(int(archive.get('size') or 0))}, "
             f"its .sha256 checked) and unpack it into {dest} -- never added to PATH, removable with `halo local runtime "
             f"remove tensorfold-{release.get('tag_name')}`; it needs {LINUX_NEEDS}.",
             f"  {archive['name']}: {archive.get('browser_download_url')}"]
    if not confirm("Download and install TensorFold now?"):
        from halo_harness.tensorfold import install_line
        return None, lines + [f"Declined -- {install_line(os_name, machine)}"]
    ok, msg = install(state_dir, release, archive, sha, fetcher=fetcher)
    lines.append(msg)
    path = fetched(state_dir) if ok else None
    if ok and path is None:
        lines.append(f"the archive holds no bin/tensorfold-native under {dest}")
    return ([str(path)] if path else None), lines
