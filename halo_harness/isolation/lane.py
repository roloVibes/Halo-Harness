"""halo_harness.isolation.lane -- the opt-ins applied where a worker starts (Halo 3.1.8.0 R5).

orchestra/adapters.py `spawn_worker` calls `prepare(lane, argv, env, ...)`
right before it runs the worker: the Orchestra CLI, Studio, the supervisor,
a team stage of kind orchestra and a workflow all start workers there.
Nothing declared: argv and env come back as they were and the lane file is
not touched. Declared: the lane file records what it runs with
(isolation/lines.py), the tool list rides in the worker's environment
(isolation/capabilities.py), the broker's values join the environment
(isolation/secrets.py), and the argv becomes the container's or the scoped
user's (container.py, scoped_user.py) on a seeded state dir (seed.py).
Whether the isolation can run is checked before any secret is read; a lane
that cannot run as declared raises `Stop` with the one line.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Optional

from halo_harness.isolation import Stop

WHICH = shutil.which  # how a CLI (docker, podman, sudo, op) is found; tests point it at a temp bin folder


def can_run(iso: dict, *, which=shutil.which, platform: str = sys.platform) -> Optional[str]:
    """The stop line when this host cannot run `iso`, else None (no process starts)."""
    if iso.get("mode") == "container":
        from halo_harness.isolation.container import NO_ENGINE, engine
        return None if engine(which) else NO_ENGINE
    from halo_harness.isolation.scoped_user import WINDOWS
    if platform == "win32":
        return WINDOWS
    return None if which("sudo") else "isolation: user asked, no sudo on this host"


def prepare(lane, argv: list, env: dict, *, run_dir, team: Optional[str] = None, runner=subprocess.run,
            which=None, platform: Optional[str] = None, sharer=None) -> "tuple[list, dict, tuple]":
    """`(argv, env, secret values)` for the lane's worker; raises Stop with the line it stops on."""
    from halo_harness.isolation import capabilities as C, lines as L, secrets as K, spec as S
    which, platform = which or WHICH, platform or sys.platform
    opt = S.for_lane(run_dir, lane.job, team=team)
    if not opt.declared:
        return argv, env, ()
    env = dict(env)
    record = L.lane_record(opt)
    lane.update(**record)
    if opt.caps is not None:
        env[C.CAPS_ENV], env[C.CAPS_BY_ENV] = ",".join(opt.caps), opt.caps_by
    env[C.OPT_INS_ENV] = "\n".join(record["opt_ins"])
    iso = opt.isolation
    stop = can_run(iso, which=which, platform=platform) if iso else None
    if stop:
        raise Stop(stop)
    values: dict = {}
    if opt.secrets:
        values = K.resolve(opt.secrets, runner=runner, which=which)
        env.update(values)
        env.update(K.worker_env(values, opt.secrets.get("pass")))
    if iso:
        from halo_harness.isolation.seed import seed
        from halo_harness.orchestra.goal import repo_root_of
        seed(run_dir, lane.n, lineup=opt.lineup, bio=opt.bio, cwd=repo_root_of(run_dir))
        if iso.get("mode") == "container":
            from halo_harness.isolation.container import wrap
            argv, env = wrap(argv, lane.worktree, env, iso, run_dir=run_dir, lane_n=lane.n, keys=list(values),
                             which=which)
        else:
            from halo_harness.isolation.scoped_user import wrap as wrap_user
            argv, env = wrap_user(argv, lane.worktree, env, iso, run_dir=run_dir, lane_n=lane.n, keys=list(values),
                                  which=which, platform=platform, sharer=sharer)
    return argv, env, tuple(values.values())
