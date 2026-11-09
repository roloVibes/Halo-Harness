"""halo_harness.providers.hf_paths -- where a downloaded file may land (Halo 3.3.14.0 R2, REVIEW #14 PERMS-8; the
download itself is providers/hf_download.py).

    target(root, commit, name) -> Path   <root>/snapshots/<commit>/<name>, refused (HubError "path", one line) for a
        name or commit that would land anywhere else: a drive (`C:evil`, `D:x.gguf`, `C:/Users/...`), any `:` (a stream
        name too), a backslash, a leading `/`, an empty / `.` / `..` part; and the absolute path must be inside the
        model folder's snapshots (a lexical check: no file-system resolve)
    part(root, f, final) -> Path   the `.part` file of a checked target: <root>/blobs/<hex>.part, the hex being the
        hub's sha256 or git blob id when it is hex, else the sha256 of the checked name (never a hub value as given)
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

_SHA256, _BLOB = re.compile(r"[0-9a-fA-F]{64}"), re.compile(r"[0-9a-fA-F]{40}")


def _refuse(what: str):
    from halo_harness.providers.hf_download import HubError
    return HubError("path", f"{what}: the hub returned a name that does not stay in the model folder; nothing written")


def target(root, commit: str, name: str) -> Path:
    name, commit = str(name or ""), str(commit or "")
    if not name or any(ch in name for ch in ":\\") or name.startswith("/") or \
            any(p in ("", ".", "..") for p in name.split("/")):
        raise _refuse(name)
    if not commit or any(ch in commit for ch in ":/\\") or commit in (".", ".."):
        raise _refuse(commit)
    final = Path(root) / "snapshots" / commit / name
    # the absolute, case-folded path must stay under <root>/snapshots: a lexical check, never the file system's
    # resolve (realpath of a path that does not exist yet differs between hosts; the checks above already leave no
    # `..`, drive, `:` or `\` to escape with)
    base = os.path.normcase(os.path.abspath(Path(root) / "snapshots")) + os.sep
    if not os.path.normcase(os.path.abspath(final)).startswith(base):
        raise _refuse(name)
    return final


def part(root, f: dict, final: Path) -> Path:
    sha, blob = str(f.get("sha256") or ""), str(f.get("blob_id") or "")
    key = (sha.lower() if _SHA256.fullmatch(sha) else blob.lower() if _BLOB.fullmatch(blob) else
           hashlib.sha256(final.relative_to(Path(root)).as_posix().encode("utf-8")).hexdigest())
    return Path(root) / "blobs" / f"{key}.part"
