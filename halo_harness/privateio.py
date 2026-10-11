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


def write_atomic_keep_mode(path: Path, data: str, *, new_file_mode: int = 0o644) -> None:
    """`write_private_atomic`'s sibling for a file that is NOT always secret
    (a `settings.json` whose `env` block may hold tokens): the temp file is
    private while it is written, and the target lands with the mode the old
    file had (`new_file_mode` when there was none) -- a 0600 file never
    comes back 0644, and a shared project file never comes back 0600."""
    path = Path(path)
    try:
        mode = os.stat(path).st_mode & 0o777
    except OSError:
        mode = new_file_mode
    write_private_atomic(path, data)
    if os.name != "nt":
        try:
            os.chmod(path, mode)
        except OSError:
            pass


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


# ---- 2.0.10 finding 24: the state tree is owner-only ------------------------
#
# `~/.halo` holds every prompt, every tool result and (shadow repo) a copy of
# each edited file. Directories this harness creates are 0700 and the
# transcript files 0600; an existing tree is tightened once per state dir
# (`tighten_state_tree`, marker file) with a single notice. All of it is a
# no-op on Windows (no mode bits).

IS_POSIX = os.name != "nt"
_TIGHTENED_MARKER = ".modes-v1"


def _user_home() -> Path:
    from halo_harness.config.paths import home
    return home()


def _chmod(path, mode: int) -> bool:
    if not IS_POSIX:
        return False
    try:
        os.chmod(str(path), mode)
        return True
    except OSError:
        return False


def private_mkdir(path: Path) -> None:
    """`mkdir -p` where EVERY directory this call creates (parents included)
    is 0700. Directories that already exist keep their mode."""
    path = Path(path)
    missing = []
    probe = path
    while not probe.exists() and probe != probe.parent:
        missing.append(probe)
        probe = probe.parent
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            continue
        _chmod(directory, 0o700)  # the umask can only remove bits; this pins 0700


def private_opener(path, flags: int) -> int:
    """`open(..., opener=private_opener)`: a file this call creates is 0600."""
    return os.open(path, flags, 0o600)


def private_write_text(path: Path, text: str) -> None:
    """Write a (non-atomic) text file, 0600 when created."""
    with open(path, "w", encoding="utf-8", opener=private_opener) as f:
        f.write(text)


def _owner_only(path: str, *, is_dir: bool) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    import stat as _stat
    if _stat.S_ISLNK(st.st_mode):
        return False
    mode = _stat.S_IMODE(st.st_mode)
    want = (mode & 0o700) | (0o700 if is_dir else 0)
    if want != mode:
        return _chmod(path, want)
    return False


def tighten_state_tree(home: Path, *, force: bool = False) -> int:
    """Drop group/other permission bits on `home` and everything under it
    (owner bits are kept, so an owner-executable script stays executable).
    Runs the full walk once per state dir (a marker file records it) unless
    `force`; returns how many entries changed. Windows: 0."""
    home = Path(home)
    if not IS_POSIX or not home.is_dir() or home == _user_home() or home == Path(home.anchor):
        return 0
    changed = int(_owner_only(str(home), is_dir=True))
    marker = home / _TIGHTENED_MARKER
    if marker.exists() and not force:
        return changed
    for root, dirs, files in os.walk(str(home)):
        for name in dirs:
            changed += int(_owner_only(os.path.join(root, name), is_dir=True))
        for name in files:
            changed += int(_owner_only(os.path.join(root, name), is_dir=False))
    try:
        marker.write_text("owner-only modes applied\n", encoding="utf-8")
        _chmod(marker, 0o600)
    except OSError:
        pass
    return changed


def tighten_state_tree_notice(home: Path) -> int:
    """`tighten_state_tree` plus ONE stderr line when it changed anything."""
    changed = tighten_state_tree(home)
    if changed:
        import sys
        print(f"halo: made {changed} entr{'y' if changed == 1 else 'ies'} under {home} owner-only "
              "(0700 directories, 0600 files); transcripts and snapshots are no longer readable by "
              "other accounts", file=sys.stderr)
    return changed
