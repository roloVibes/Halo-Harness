"""halo_harness.isolation.container -- `isolation: container` (Halo 3.1.8.0 R5).

`wrap(argv, cwd, env, spec, run_dir=, lane_n=)` turns a worker's `halo -p`
argv into

    docker run --rm --network <host|none>
      -v <worktree>:/work -w /work -v <run folder>:/run -v <run>/state-<n>:/root/.halo
      [-v <the repo's .git>:<the same path>]      (a POSIX host: git works in /work)
      [-v <each mount>]
      -e HALO_ORCHESTRA_RUN=/run -e HALO_ORCHESTRA_LANE=<n> -e PYTHONIOENCODING=utf-8
      -e <KEY> ...                                 (names only: docker takes each value from its own env)
      <image> halo -p ...

The network is `host` unless the isolation says `network: none`: a worker
calls its model provider, so it needs the network; `none` fits a worker
that talks only to a model inside the image.
`podman` when there is no docker. The host's `~/.halo` is never mounted;
the scoped state dir is seed.py's. The environment the container sees is
only the names above: the isolation's `env`, the broker's keys and the
run's own control variables. No docker and no podman here: `Stop`.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

from halo_harness.isolation import Stop

WORK, RUN, STATE = "/work", "/run", "/root/.halo"
IMAGE_REPO = "halo-harness-worker"
SOURCE = "https://github.com/roloVibes/Halo-Harness.git"
CONTROL_KEYS = ("HALO_TOOLS_CAPS", "HALO_TOOLS_CAPS_BY", "HALO_OPT_INS", "HALO_SECRET_KEYS", "HALO_SECRET_PASS")
NO_ENGINE = "isolation: container asked, no docker or podman on this host"


def default_image() -> str:
    from halo_harness import __version__
    return f"{IMAGE_REPO}:{__version__}"


def dockerfile_path() -> Path:
    return Path(__file__).resolve().with_name("Dockerfile")


def dockerfile_text() -> str:
    try:
        return dockerfile_path().read_text(encoding="utf-8")
    except OSError:
        return ""


def engine(which=shutil.which) -> Optional[str]:
    """docker's path, else podman's, else None."""
    return which("docker") or which("podman") or None


def worker_args(argv: list) -> list:
    """What follows `python -m halo_harness` in a worker argv (the container runs `halo` itself)."""
    argv = list(argv)
    for i in range(len(argv) - 1):
        if argv[i] == "-m" and argv[i + 1] == "halo_harness":
            return argv[i + 2:]
    return argv[1:]


def _git_mounts(cwd) -> list:
    """The repo's git folder at its own path, so git works in the worktree (POSIX hosts only)."""
    if os.name == "nt":
        return []
    try:
        text = (Path(cwd) / ".git").read_text(encoding="utf-8").strip()
    except OSError:
        return []
    if not text.startswith("gitdir:"):
        return []
    common = Path(text[len("gitdir:"):].strip()).parent.parent
    return ["-v", f"{common}:{common}"] if common.name == ".git" else []


def wrap(argv: list, cwd, env: dict, spec: dict, *, run_dir, lane_n: int, keys=(), which=shutil.which) -> "tuple[list, dict]":
    """`(argv, env)` for the container; `keys` are the broker's names (their values are already in `env`)."""
    exe = engine(which)
    if not exe:
        raise Stop(NO_ENGINE)
    from halo_harness.isolation.seed import state_dir_for
    from halo_harness.orchestra import RUN_ENV
    from halo_harness.orchestra.workers import LANE_ENV
    run_dir = Path(run_dir).resolve()
    out = [exe, "run", "--rm", "--network", str(spec.get("network") or "host"),
           "-v", f"{Path(cwd).resolve()}:{WORK}", "-w", WORK, "-v", f"{run_dir}:{RUN}",
           "-v", f"{state_dir_for(run_dir, lane_n).resolve()}:{STATE}", *_git_mounts(cwd)]
    for mount in spec.get("mounts") or []:
        out += ["-v", str(mount)]
    out += ["-e", f"{RUN_ENV}={RUN}", "-e", f"{LANE_ENV}={int(lane_n)}", "-e", "PYTHONIOENCODING=utf-8"]
    names = {*(spec.get("env") or []), *keys, *CONTROL_KEYS}
    for name in sorted(n for n in names if n in env and n not in (RUN_ENV, LANE_ENV, "PYTHONIOENCODING")):
        out += ["-e", name]
    out += [str(spec.get("image") or default_image()), "halo", *worker_args(argv)]
    return out, dict(env)


def build_argv(image: Optional[str] = None, which=shutil.which) -> list:
    """`docker build` for the shipped Dockerfile at this harness's version."""
    from halo_harness import __version__
    exe = engine(which)
    if not exe:
        raise Stop("isolation: no docker or podman on this host to build the image")
    path = dockerfile_path()
    return [exe, "build", "-t", image or default_image(), "--build-arg", f"HALO_VERSION={__version__}",
            "-f", str(path), str(path.parent)]
