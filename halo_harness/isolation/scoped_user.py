"""halo_harness.isolation.scoped_user -- `isolation: user` (Halo 3.1.8.0 R5).

On a POSIX host the worker runs as another OS user:

    sudo -n -u <name> --preserve-env=<names> -- <python> -m halo_harness -p ...

`--preserve-env` carries the run's own variables (the run folder, the lane,
the scoped state dir in BRIDGE_STATE_DIR, the tool list), the isolation's
`env` names and the broker's keys -- names only, never a value in argv.
Before it starts, the lane's worktree and the run folder are made
group-writable for that user (`share`: the group is `group:` or the user's
primary group, set on every file and folder, folders setgid so new files
keep it); you are a member of that group, and sudoers lets you run the
harness's python as that user with no password (`NOPASSWD:SETENV:`).
Windows has no scoped user in this round: `Stop`.
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path

from halo_harness.isolation import Stop

WINDOWS = "isolation: user is not available on Windows; use container"
BASE_KEYS = ("HALO_ORCHESTRA_RUN", "HALO_ORCHESTRA_LANE", "PYTHONIOENCODING", "BRIDGE_STATE_DIR")


def group_of(user: str, group: str = "") -> int:
    """The gid to share the lane's folders with."""
    import grp
    import pwd
    if group:
        try:
            return grp.getgrnam(group).gr_gid
        except KeyError:
            raise Stop(f"isolation: user: no group {group!r} on this host") from None
    try:
        return pwd.getpwnam(user).pw_gid
    except KeyError:
        raise Stop(f"isolation: user {user!r} does not exist on this host") from None


def share(paths, gid: int, skip=()) -> None:
    """chgrp + chmod g+rwX (folders also g+s) on every file and folder under `paths`, `skip` folders left out."""
    skip = [Path(s) for s in skip]
    for root in paths:
        for path in [Path(root), *Path(root).rglob("*")]:
            try:
                if path.is_symlink() or any(s in path.parents for s in skip):  # the folder itself stays reachable
                    continue
                os.chown(path, -1, gid)
                mode = path.stat().st_mode
                extra = stat.S_IRGRP | stat.S_IWGRP | (stat.S_IXGRP | stat.S_ISGID if path.is_dir() else 0)
                os.chmod(path, mode | extra | (stat.S_IXGRP if mode & stat.S_IXUSR else 0))
            except OSError as e:
                raise Stop(f"isolation: user could not share {path} with group {gid}: {e.strerror or e}") from None


def wrap(argv: list, cwd, env: dict, spec: dict, *, run_dir, lane_n: int, keys=(), which=shutil.which,
         platform: str = sys.platform, sharer=None) -> "tuple[list, dict]":
    """`(argv, env)` that run the worker as `spec["user"]`; `sharer(paths, spec)` (tests) replaces the chgrp step."""
    if platform == "win32":
        raise Stop(WINDOWS)
    user = str(spec.get("user") or "")
    if not user:
        raise Stop("isolation: user asked, no user named")
    sudo = which("sudo")
    if not sudo:
        raise Stop("isolation: user asked, no sudo on this host")
    from halo_harness.isolation.container import CONTROL_KEYS
    from halo_harness.isolation.seed import state_dir_for
    paths = [Path(cwd), Path(run_dir)]
    if sharer is not None:
        sharer(paths, spec)
    else:  # the other lanes' worktrees are theirs: the run folder is shared without wt/
        share(paths[:1], group_of(user, str(spec.get("group") or "")))
        share(paths[1:], group_of(user, str(spec.get("group") or "")), skip=[Path(run_dir) / "wt"])
    out_env = dict(env)
    out_env["BRIDGE_STATE_DIR"] = str(state_dir_for(run_dir, lane_n).resolve())
    names = sorted({*BASE_KEYS, *CONTROL_KEYS, *(spec.get("env") or []), *keys} & set(out_env))
    return [sudo, "-n", "-u", user, f"--preserve-env={','.join(names)}", "--", *argv], out_env
