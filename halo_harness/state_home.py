"""Halo's own folder (`~/.halo`, `bridge_home()`) must be usable before anything is started in it.

A read-only disk or home, a `~/.halo` left root-owned by a `sudo halo` run, or a `~/.halo` that is a file used to
end `halo -p`, `halo init` and the full-screen session with a traceback deep inside the first write. `problem()`
looks once, creating and writing nothing, and gives the one plain line to stop with; `line_for_error()` turns an
OSError that names a path inside Halo's own folders into that same line. `halo doctor` shows the same line as its
first row (doctor.py)."""
from __future__ import annotations

import errno
import os
from pathlib import Path
from typing import Optional


def line(path, reason: str, owner_of=None) -> str:
    """The one plain line for a folder Halo cannot use; `owner_of` is the folder whose owner or permissions are
    the cause when that is not `path` itself (a home that cannot be written)."""
    text = f"halo: cannot use {path} ({reason}) -- check the owner and permissions of {owner_of or path}"
    if os.name != "nt":
        text += f" (a `sudo halo` run leaves root-owned files: sudo chown -R $USER {owner_of or path})"
    return text


def problem(path: Optional[Path] = None) -> Optional[str]:
    """None when Halo's folder exists and can be read and written, or can be created; else the plain line.
    Nothing is created or written here."""
    if path is None:
        from halo_harness.config.paths import bridge_home
        path = bridge_home()
    path = Path(path)
    try:
        if path.exists() or path.is_symlink():
            if not path.is_dir():
                return line(path, os.strerror(errno.ENOTDIR))
            if not os.access(path, os.R_OK | os.W_OK | os.X_OK):
                return line(path, os.strerror(errno.EACCES))
            return None
        probe = path.parent
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        if not probe.is_dir():
            return line(path, f"{probe}: {os.strerror(errno.ENOTDIR)}", owner_of=probe)
        if not os.access(probe, os.W_OK | os.X_OK):
            return line(path, f"{probe} cannot be written: {os.strerror(errno.EACCES)}", owner_of=probe)
    except OSError as e:
        return line(path, e.strerror or str(e))
    return None


def _own_roots() -> "list[Path]":
    from halo_harness.config.paths import bridge_home, claude_config_dir, env_file_path
    roots = []
    for get in (bridge_home, claude_config_dir, lambda: env_file_path().parent):
        try:
            roots.append(Path(os.path.abspath(get())))
        except Exception:
            continue
    return roots


def line_for_error(exc: BaseException) -> Optional[str]:
    """The plain line for an OSError about a path inside Halo's own folders (its state folder, the Claude config
    folder, the credentials file's folder); None for anything else, which stays a real error."""
    if not isinstance(exc, OSError) or not exc.filename:
        return None
    try:
        failed = Path(os.path.abspath(os.fsdecode(exc.filename)))
    except (TypeError, ValueError):
        return None
    for root in _own_roots():
        if failed == root or root in failed.parents:
            return line(failed, exc.strerror or type(exc).__name__)
    return None
