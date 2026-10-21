"""halo_harness.ext.files -- a pack's folders and its private files
(extension API 1.0).

    pack_dir("doc-review")     # the pack's own folder (read-only: Halo never writes there), or None
    data_dir("doc-review")     # ~/.halo/packs/.data/doc-review/ -- the pack's own place to write
    write_private("doc-review", "notes/today.md", text)   # [] when written

A relative path lands in the pack's data folder. A path outside it needs
the `home-write` permission, requested in pack.yaml and granted by you
(`halo pack enable <id> --grant home-write`); without it the call answers
one line naming the permission and writes nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def _check_id(pack_id) -> None:
    from halo_harness.packs.names import pack_id_problem
    line = pack_id_problem(pack_id)
    if line:
        raise ValueError(line)


def pack_dir(pack_id: str, *, cwd=None) -> Optional[Path]:
    from halo_harness.packs.discover import find
    _check_id(pack_id)
    found = find(pack_id, cwd=cwd)
    return found.root if found is not None else None


def data_dir(pack_id: str) -> Path:
    from halo_harness.packs.discover import user_packs_dir
    _check_id(pack_id)
    return user_packs_dir() / ".data" / pack_id


def target(pack_id: str, path) -> "tuple[Optional[Path], str]":
    """`(absolute path, "")` where a write may go, or `(None, the line saying why not)`."""
    from halo_harness.ext.grants import is_granted
    base = data_dir(pack_id)
    p = Path(path)
    if not p.is_absolute():
        if ".." in p.parts:
            return None, f"{path}: a path in the pack's data folder does not climb out of it (..)"
        return base / p, ""
    try:
        p.resolve().relative_to(base.resolve())
        return p, ""
    except ValueError:
        pass
    if is_granted(pack_id, "home-write"):
        return p, ""
    return None, (f"{path} is outside {pack_id}'s data folder; writing there needs the home-write permission "
                  f"(halo pack enable {pack_id} --grant home-write)")


def write_private(pack_id: str, path, text: str) -> "list[str]":
    """A 0600 file written atomically (privateio.write_private_atomic); `[]` on success, else one line."""
    from halo_harness.privateio import write_private_atomic
    dest, problem = target(pack_id, path)
    if dest is None:
        return [problem]
    try:
        write_private_atomic(dest, str(text))
    except OSError as e:
        return [f"cannot write {dest}: {e}"]
    return []


__all__ = ["pack_dir", "data_dir", "write_private"]
