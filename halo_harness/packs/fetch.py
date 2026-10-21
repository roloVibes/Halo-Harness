"""halo_harness.packs.fetch -- a pack's source: a folder or a git url
(Halo 3.2.0.0 R1).

    with fetched(source, state_dir=...) as (folder, problem):
        ...   # folder is a local copy (a folder as given, a fresh shallow clone of a url); problem is ''
    source_for("doc-review")   # a bare id: the first of config `packs.sources` that holds it

A url is cloned (`git clone --depth 1`) into a fresh folder under
`<state>/packs/.staging-<8 hex>/`, removed when the block ends. Offline mode
(`--offline`, `network.offline`) answers the one line offline mode always
prints ("offline mode: not connecting to <host>") and clones nothing.
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlparse

from halo_harness.packs.names import is_url


def configured_sources() -> "list[str]":
    """`packs.sources` in ~/.halo/config.json: folders holding packs (or one pack), and git urls of packs."""
    from halo_harness.theme import get_config_value
    raw = get_config_value("packs.sources", default=[])
    return [str(s) for s in raw if isinstance(s, str) and s.strip()] if isinstance(raw, list) else []


def source_for(target: str) -> str:
    """`target` as given when it is a url or a folder; for a bare pack id, the first of `packs.sources`
    that holds it (a folder `<source>/<id>/`, a folder that is the pack, a url ending in `<id>` or `<id>.git`)."""
    from halo_harness.packs.names import is_valid_pack_id
    if is_url(target) or Path(target).expanduser().exists() or not is_valid_pack_id(target):
        return target
    for src in configured_sources():
        if is_url(src):
            if src.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git") == target:
                return src
            continue
        base = Path(src).expanduser()
        if (base / target / "pack.yaml").is_file():
            return str(base / target)
        if base.name == target and (base / "pack.yaml").is_file():
            return str(base)
    return target


def host_of(url: str) -> str:
    if "://" in url:
        return urlparse(url).hostname or url
    return url.split("@", 1)[-1].split(":", 1)[0]  # git@host:path


def offline_line(url: str) -> str:
    """Offline mode's one line for `url`, or '' when the network is in use."""
    from halo_harness.providers.http import format_offline_refusal, offline_mode_enabled
    if url.startswith("file://") or not offline_mode_enabled():
        return ""
    return format_offline_refusal(host_of(url))


def _clone(url: str, dest: Path, timeout: float) -> str:
    try:
        result = subprocess.run(["git", "clone", "--depth", "1", "--", url, str(dest)],
                                capture_output=True, text=True, timeout=timeout,
                                encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as e:
        return f"git clone {url} did not run: {e}"
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()
        return f"git clone {url} failed: {tail[-1] if tail else 'exit ' + str(result.returncode)}"
    return ""


@contextlib.contextmanager
def fetched(source: str, *, state_dir=None, timeout: float = 120.0):
    from halo_harness.packs.state import packs_home
    if not is_url(source):
        from halo_harness.packs.names import is_valid_pack_id
        folder = Path(source).expanduser()
        missing = f"{source}: no such folder" + (f", and no pack {source} in config packs.sources"
                                                  if is_valid_pack_id(source) else "")
        yield (folder.resolve(), "") if folder.is_dir() else (None, missing)
        return
    line = offline_line(source)
    if line:
        yield None, line
        return
    staging = packs_home(state_dir) / f".staging-{uuid.uuid4().hex[:8]}"
    staging.parent.mkdir(parents=True, exist_ok=True)
    try:
        problem = _clone(source, staging / "src", timeout)
        yield (None, problem) if problem else (staging / "src", "")
    finally:
        rmtree(staging)


def rmtree(path: Path) -> None:
    """Remove a folder, a clone's read-only git objects too (Windows marks them read-only)."""
    import os
    import stat

    def _again(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    if Path(path).exists():
        shutil.rmtree(path, onerror=_again)


def files_of(folder: Path) -> "list[Path]":
    """Every file of a pack folder, relative, sorted; `.git` and Halo's own dot folders left out."""
    out = []
    for p in sorted(Path(folder).rglob("*")):
        rel = p.relative_to(folder)
        if rel.parts and rel.parts[0] in (".git",) or any(part == "__pycache__" for part in rel.parts):
            continue
        if p.is_file():
            out.append(rel)
    return out
