"""halo_harness.privateio -- the ONE private-file write helper (vibes/
review.md findings 14/15, R5): every file this harness writes that carries
credentials (the proxy launch file with the Databricks PAT, the env file
with every provider key, curl config files carrying a GitHub token) goes
through `write_private_atomic`, never a bare `open(path, "w")`.

Three properties, in one place:

  * PRIVATE BY CONSTRUCTION -- the temp file is created by mkstemp, which
    is 0600 on POSIX before a single byte is written (a bare `open(...,
    "w")` creates with the process umask, usually 0644 -- world-readable
    for the window the file exists, and forever if the process dies
    before the chmod that used to come after).
  * ATOMIC -- `os.replace` onto the target, so a crash mid-write can
    never truncate a file that already had every stored key in it (the
    env file's old in-place write lost ALL credentials to a half-written
    line; now the old file survives untouched until the new one is
    complete).
  * NO COLLATERAL CHMOD -- callers that also want a private DIRECTORY
    call `ensure_private_dir` explicitly with a path they own;
    `_write_env_var`'s old code chmod 0700'd the PARENT of whatever
    HALO_ENV_FILE pointed at (set it to `~/.env` and it chmod'd $HOME).

Windows: no mode bits exist; mkstemp's 0600 and the chmod calls are
harmless no-ops there, the atomicity still holds.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_private_atomic(path: Path, data: str) -> None:
    """Write `data` to `path` as a 0600 file, atomically (mkstemp in the
    same directory + os.replace, so the target is either the complete old
    content or the complete new content, never a truncate-in-progress).
    Creates `path.parent` if needed (plain mkdir -- see the module
    docstring for why this helper deliberately does NOT chmod it)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        # mkstemp already made the temp 0600 on POSIX; os.replace keeps
        # the temp's mode (a plain rename preserves it), so the target
        # lands 0600 too. Best-effort on filesystems without mode bits.
        try:
            os.chmod(tmp_name, 0o600)
        except OSError:
            pass
        os.replace(tmp_name, path)
    except Exception:
        # Never leave the temp file behind on a failed write -- it can
        # carry the very credentials this helper exists to protect.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def ensure_private_dir(path: Path) -> None:
    """chmod 0700 a directory this harness OWNS (the proxy state dir, the
    canonical `~/.config/halo`). Callers must pass a path they own --
    this is deliberately opt-in per call site (finding 15's whole bug was
    a writer chmod-ing a directory it did NOT own). No-op on Windows."""
    if os.name == "nt":
        return
    try:
        os.chmod(str(path), 0o700)
    except OSError:
        pass
