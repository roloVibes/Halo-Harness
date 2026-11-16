"""halo_harness.isolation.container -- `isolation: container` (Halo 3.1.8.0 R5).

`wrap(argv, cwd, env, spec, run_dir=, lane_n=)` turns a worker's `halo -p`
argv into

    docker run --rm --network <host|none>
      --name halo-<owner>-<n>-<6 hex> --label halo.owner=<owner>   (3.6.0.1: the owner = this Halo's marker id)
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
import threading
from pathlib import Path
from typing import Optional

from halo_harness.isolation import Stop

WORK, RUN, STATE = "/work", "/run", "/root/.halo"
IMAGE_REPO = "halo-harness-worker"
SOURCE = "https://github.com/roloVibes/Halo-Harness.git"
CONTROL_KEYS = ("HALO_TOOLS_CAPS", "HALO_TOOLS_CAPS_BY", "HALO_OPT_INS", "HALO_SECRET_KEYS", "HALO_SECRET_PASS")
NO_ENGINE = "isolation: container asked, no docker or podman on this host"
LABEL = "halo.owner"  # 3.6.0.1: `docker ps --filter label=halo.owner` lists Halo's worker containers


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
    return ["-v", f"{common}:{common}:ro"] if common.name == ".git" else []


def wrap(argv: list, cwd, env: dict, spec: dict, *, run_dir, lane_n: int, keys=(), which=shutil.which) -> "tuple[list, dict]":
    """`(argv, env)` for the container; `keys` are the broker's names (their values are already in `env`)."""
    exe = engine(which)
    if not exe:
        raise Stop(NO_ENGINE)
    from halo_harness.isolation.seed import state_dir_for
    from halo_harness.orchestra import RUN_ENV
    from halo_harness.orchestra.workers import LANE_ENV
    run_dir = Path(run_dir).resolve()
    from halo_harness import closing
    owner = closing.my_ident()  # 3.6.0.1: what the reaper is handed and the start sweep checks (never marker())
    out = [exe, "run", "--rm", "--network", str(spec.get("network") or "host"),
           "--name", f"halo-{owner}-{int(lane_n)}-{os.urandom(3).hex()}", "--label", f"{LABEL}={owner}",
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


# -- 3.6.0.1: a started container is named, recorded and removed through its engine ---------------------------------
# The container's process belongs to the engine's daemon, not to the `docker run` client: ending the client (a close,
# a timeout, a hard kill) does not end it. So each lane's container has a name, a record under
# `<state home>/containers/<name>.json` {name, engine, owner, since} while it runs, and `<engine> rm -f` ends it from:
# the lane itself (past its time), this Halo's close (on_close), the POSIX reaper after a hard kill (owner = its mark),
# and the next start's sweep (owner provably gone). A record goes only when its container is known gone. Stdlib only:
# the reaper imports this with `python -I -S`.

def name_of(argv) -> Optional[str]:
    """The `--name` of a container argv `wrap` built; None for any other argv."""
    argv = list(argv or [])
    if len(argv) > 6 and argv[1:3] == ["run", "--rm"] and argv[5] == "--name":
        return str(argv[6])
    return None


def records_dir(state_dir=None) -> Path:
    from halo_harness.children import _state
    return _state(state_dir) / "containers"


def write_record(name: str, exe: str, owner: str, state_dir=None) -> None:
    import json
    import time
    d = records_dir(state_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.json").write_text(json.dumps({"name": name, "engine": exe, "owner": owner, "since": time.time()}),
                                    encoding="utf-8")


def drop_record(name: str, state_dir=None) -> None:
    try:
        (records_dir(state_dir) / f"{name}.json").unlink()
    except OSError:
        pass


def records(state_dir=None) -> list:
    import json
    out = []
    try:
        paths = sorted(records_dir(state_dir).glob("halo-*.json"))
    except OSError:
        return []
    for p in paths:
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(rec, dict) and rec.get("name") == p.stem and rec.get("engine") and rec.get("owner"):
            out.append(rec)
    return out


def remove(exe: str, names: list, timeout: float, *, strict: bool = False) -> list:
    """`<engine> rm -f <names...>` (docker and podman alike): the names the engine answered gone (removed, or there
    was no such container). A failed or timed-out call answers none of them, and so does a missing engine program
    (nothing was asked: the container may still run in the engine's daemon). `strict` (a close): 'no such container'
    is not gone -- a close in a lane's first moments meets it before the engine has created the container, which
    would then start with no record (3.6.0.1). Docker 23 and newer exit 0 on that answer, podman and older Docker 1."""
    import subprocess
    names = [str(n) for n in names]
    if not names:
        return []
    try:
        proc = subprocess.run([exe, "rm", "-f", *names], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=max(0.5, float(timeout)))
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    lines = [ln.lower() for ln in (proc.stderr or "").splitlines() if "no such container" in ln.lower()]
    nosuch = [n for n in names if any(n.lower() in ln for ln in lines)]
    if strict:
        return [n for n in names if n not in nosuch] if proc.returncode == 0 else []
    return names if proc.returncode == 0 else nosuch


def remove_where(keep, state_dir=None, timeout: float = 10.0, failed=None) -> list:
    """Remove every recorded container whose record `keep(record)` says False, one engine call per engine; their
    records go when the engine says they are gone. Answers the records removed. No records: no engine call.
    `failed(record)` is called for each one tried and not known gone."""
    by_engine: dict = {}
    for rec in records(state_dir):
        if not keep(rec):
            by_engine.setdefault(rec["engine"], []).append(rec)
    done = []
    for exe, recs in by_engine.items():
        gone = set(remove(exe, [r["name"] for r in recs], timeout))
        for r in recs:
            if r["name"] in gone:
                drop_record(r["name"], state_dir)
                done.append(r)
            elif failed is not None:
                failed(r)
    return done


RETRY_S = 600.0  # 3.6.0.1: a record the engine could not remove is tried again by a start after 10 minutes, not each
TRY_S = 3.0      # and one try holds a start this long at most (a stopped or hung daemon)


def _now() -> float:
    import time
    return time.time()


def _tried_lately(rec: dict, now: float) -> bool:
    tried = rec.get("tried")
    return isinstance(tried, (int, float)) and 0 <= now - float(tried) < RETRY_S


def _note_tried(rec: dict, now: float, state_dir=None) -> None:
    import json
    try:
        (records_dir(state_dir) / f"{rec['name']}.json").write_text(json.dumps(dict(rec, tried=now)),
                                                                     encoding="utf-8")
    except OSError:
        pass


def sweep_records(state_dir=None, say=None) -> list:
    """The start sweep's part (closing.sweep): containers whose owner is provably gone (closing.owner_provably_gone:
    an owner whose start time cannot be read is never gone), one line each. A record the engine could not remove
    (its daemon stopped or hung, its program missing) notes the try, and the starts of the next 10 minutes leave
    it alone: a stopped Docker costs one bounded call per 10 minutes, never one per start."""
    from halo_harness import closing
    if not records(state_dir):
        return []
    now = _now()
    done = remove_where(lambda r: not closing.owner_provably_gone(r["owner"]) or _tried_lately(r, now),
                        state_dir, timeout=TRY_S, failed=lambda r: _note_tried(r, now, state_dir))
    lines = [f"halo: removed a worker container left from {closing._when(r)} ({r['name']})" for r in done]
    for line in lines:
        try:
            (say or closing._say)(line)
        except Exception:
            pass
    return lines


_LIVE: dict = {}  # name -> (engine, state dir): the containers this process's lanes run now
_LIVE_LOCK = threading.Lock()


def started(name: str, exe: str, state_dir=None) -> None:
    """A lane is about to start container `name`: record it, and have this process's close remove it."""
    from halo_harness import closing
    write_record(name, exe, closing.my_ident(), state_dir)
    with _LIVE_LOCK:
        _LIVE[name] = (exe, state_dir)
        if _remove_live not in closing._STATE["callbacks"]:  # by membership: reset_for_tests empties the list
            closing.on_close(_remove_live)


def finished(name: str, *, ended_by_itself: bool, timeout: float = 30.0) -> None:
    """The lane's runner came back. A container that ended by itself is gone (--rm); any other is removed first."""
    with _LIVE_LOCK:
        item = _LIVE.pop(name, None)
    if item is None:  # this process's close removed it already
        return
    exe, state_dir = item
    from halo_harness import closing
    if ended_by_itself or remove(exe, [name], timeout, strict=closing.stop_asked()):
        drop_record(name, state_dir)


def _remove_live() -> None:
    """closing.close(): every container this process's lanes still run, in one `rm -f` per engine. A record goes
    only when the engine removed it (strict): 'no such container' at close, on exit 0 (Docker 23+) or 1, may be one
    the engine is still creating, and the next
    start's sweep finishes it (one call, then the record goes)."""
    from halo_harness import closing
    with _LIVE_LOCK:
        live = dict(_LIVE)
        _LIVE.clear()
    by_engine: dict = {}
    for name, (exe, state_dir) in live.items():
        by_engine.setdefault((exe, state_dir), []).append(name)
    for (exe, state_dir), names in by_engine.items():
        for name in remove(exe, names, closing.time_left(10.0), strict=True):
            drop_record(name, state_dir)


def build_argv(image: Optional[str] = None, which=shutil.which) -> list:
    """`docker build` for the shipped Dockerfile at this harness's version."""
    from halo_harness import __version__
    exe = engine(which)
    if not exe:
        raise Stop("isolation: no docker or podman on this host to build the image")
    path = dockerfile_path()
    return [exe, "build", "-t", image or default_image(), "--build-arg", f"HALO_VERSION={__version__}",
            "-f", str(path), str(path.parent)]
