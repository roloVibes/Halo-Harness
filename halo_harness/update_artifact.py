"""halo_harness.update_artifact -- compare the installed build's own archive
with the release's `checksums.txt` (3.0.1.0 review item 81, the clause the
3.0.2.0 fix pass left open).

`scripts/release.py` publishes, per tag, `halo-harness-<version>.tar.gz`
(the tag's `git archive`) and `checksums.txt` (`<sha256>  <name>`). Only an
install made FROM an archive has something to compare with that line:
PEP 610 records it as `archive_info` in `direct_url.json`, with the
archive's sha256 when the installer knew it (uv records it; pip does when
the URL carries `#sha256=`), and a `file://` archive that still exists can
be hashed again. A `git+https://...` install (the documented one) and a
checkout install record `vcs_info` / `dir_info`: the installer built a
wheel from a clone and kept no artifact, so there is nothing to hash and
the check reports `no-artifact` instead of guessing.
"""

from __future__ import annotations

import hashlib
import posixpath
from typing import Callable, Optional
from urllib.parse import unquote, urlparse

CHECKSUMS_NAME = "checksums.txt"


def http_get_text(url: str, *, timeout: float = 10.0) -> Optional[str]:
    """`checksums.txt` as text, or None on any failure (offline included)."""
    try:
        import urllib.request
        from halo_harness.providers.http import urlopen_tls
        req = urllib.request.Request(url, headers={"User-Agent": "halo"})
        with urlopen_tls(req, timeout=timeout) as resp:
            return resp.read(1 << 20).decode("utf-8", "replace")
    except Exception:
        return None


def archive_digest(d: Optional[dict]) -> "tuple[Optional[str], Optional[str], str]":
    """`(sha256, archive file name, why)` for an archive install; the digest
    is None (with `why`) when the install has no archive or no known hash."""
    if not isinstance(d, dict):
        return None, None, "no install metadata (direct_url.json) -- a source directory, not an archive install"
    if isinstance(d.get("vcs_info"), dict) or isinstance(d.get("dir_info"), dict):
        return None, None, ("installed from a git or directory source: the installer kept no archive, "
                            "so there is nothing to compare with checksums.txt")
    info = d.get("archive_info")
    url = str(d.get("url") or "")
    if not isinstance(info, dict) or not url:
        return None, None, "direct_url.json names no archive"
    name = posixpath.basename(unquote(urlparse(url).path))
    hashes = info.get("hashes") if isinstance(info.get("hashes"), dict) else {}
    digest = hashes.get("sha256")
    legacy = str(info.get("hash") or "")
    if not digest and legacy.startswith("sha256="):
        digest = legacy.split("=", 1)[1]
    if not digest and urlparse(url).scheme == "file":
        from halo_harness.update import _url_to_path
        p = _url_to_path(url)
        if p is not None and p.is_file():
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
    if not digest:
        return None, name, "the installer recorded no sha256 for the archive and the file is not on this machine"
    return digest.lower(), name, ""


def parse_checksums(text: str) -> dict:
    """`{file name: sha256}` from sha256sum-layout lines (`*name` too)."""
    out = {}
    for line in (text or "").splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and len(parts[0]) == 64:
            out[parts[1].strip().lstrip("*")] = parts[0].lower()
    return out


def check_installed_artifact(*, direct_url: "object" = None, version: Optional[str] = None,
                             fetch_json: Optional[Callable] = None,
                             fetch_text: Optional[Callable] = None) -> dict:
    """`{"status", "detail"}`; status is `match`, `mismatch`, `no-artifact`
    (git/dir/source install), `no-hash`, `no-checksums` (the release has no
    checksums.txt or no line for this archive) or `unavailable` (the release
    could not be read). Never raises."""
    from halo_harness import update as upd
    if direct_url is None:
        direct_url = upd._direct_url()
    if version is None:
        from halo_harness import __version__ as version
    digest, name, why = archive_digest(direct_url)
    if digest is None:
        return {"status": "no-artifact" if name is None else "no-hash", "detail": why}
    tag = f"v{version}"
    assets = upd.tag_checksums(tag, fetch_json=fetch_json)
    if assets is None:
        return {"status": "unavailable", "detail": f"could not read release {tag} (offline or rate-limited)"}
    asset = next((a for a in assets if isinstance(a, dict) and a.get("name") == CHECKSUMS_NAME), None)
    if asset is None:
        return {"status": "no-checksums", "detail": f"release {tag} carries no {CHECKSUMS_NAME}"}
    text = (fetch_text or http_get_text)(str(asset.get("browser_download_url") or ""))
    if text is None:
        return {"status": "unavailable", "detail": f"could not download {tag}'s {CHECKSUMS_NAME}"}
    want = parse_checksums(text).get(name)
    if want is None:
        return {"status": "no-checksums", "detail": f"{tag}'s {CHECKSUMS_NAME} has no line for {name}"}
    if want == digest:
        return {"status": "match", "detail": f"{name} matches {tag}'s {CHECKSUMS_NAME} (sha256 {digest[:12]})"}
    return {"status": "mismatch",
            "detail": f"{name} does NOT match {tag}'s {CHECKSUMS_NAME}: installed {digest[:12]}, release {want[:12]}"}


def report_line(result: dict) -> Optional[str]:
    """The `halo update` report line, or None for an install with no
    archive (a git or checkout install says nothing here)."""
    if result.get("status") == "no-artifact":
        return None
    return f"installed archive: {result.get('status')} -- {result.get('detail')}"
