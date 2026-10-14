"""halo_harness.remote.fleet_identity -- who this harness is, what a session
works on, and the fleet's config switches (Halo 3.0.5.0 "Fleet" round R1).

* `harness()` -> `{id, name, host, user, version, os}`. `id` is a stable
  per-home id kept in `~/.halo/fleet-id` (made on first use, 0600); `name`
  is config `fleet.name`, default `user@host`.
* `project(cwd)` -> `{root, repo, branch, dirty}`: git-aware (the repo root,
  the origin's name or else the folder's, the branch, whether tracked files
  changed), the cwd with None fields outside a repo; cached PROJECT_TTL_S.
* `session_kind(default)` -> `orchestra-worker` (HALO_ORCHESTRA_RUN set),
  `paperclip` (a Paperclip heartbeat's PAPERCLIP_AGENT_ID set) or `default`.
* `parent_from_env()` / `parent_env(sid)`: the spawning session's id rides
  HALO_FLEET_PARENT into a child process.
* `fleet_enabled()` (`fleet.enabled`, default true: every session opens its
  control socket and registers), `private_configured()` (`fleet.private` or
  `--private`, which sets HALO_FLEET_PRIVATE for its own process) and
  `remote_enabled()` (`remote.enabled`, default false: the Signal bridge's
  switch and nothing else).
"""

from __future__ import annotations

import os
import platform
import re
import secrets
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

FLEET_ID_FILE = "fleet-id"
PARENT_ENV = "HALO_FLEET_PARENT"
PRIVATE_ENV = "HALO_FLEET_PRIVATE"
PROJECT_TTL_S = 30.0
GIT_TIMEOUT_S = 3.0
_ID_RE = re.compile(r"[0-9a-f]{16,64}")
_SID_RE = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
_cache: dict = {}
_lock = threading.Lock()


def truthy(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("1", "true", "yes", "on"):
            return True
        if v in ("0", "false", "no", "off", ""):
            return False
    return default


def _config(key: str, default):
    try:
        from halo_harness.theme import get_config_value
        return get_config_value(key, default)
    except Exception:
        return default


def fleet_enabled() -> bool:
    return truthy(_config("fleet.enabled", True), True)


def remote_enabled() -> bool:
    return truthy(_config("remote.enabled", False), False)


def private_configured() -> bool:
    return truthy(os.environ.get(PRIVATE_ENV), False) or truthy(_config("fleet.private", False), False)


def harness_id(home: Optional[Path] = None) -> str:
    """The per-home id: read `~/.halo/fleet-id` (or `<home>/fleet-id`, R2's
    hub), or create it exclusively (two processes starting at once agree on
    whichever file won)."""
    from halo_harness.config.paths import bridge_home
    path = (Path(home) if home is not None else bridge_home()) / FLEET_ID_FILE
    for _ in range(20):
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            text = None
        if text and _ID_RE.fullmatch(text):
            return text
        if text is None:
            new = secrets.token_hex(8)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                time.sleep(0.01)
                continue
            except OSError:
                return new
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(new + "\n")
            return new
        time.sleep(0.01)  # an empty or partial file: the writer is mid-write
    return secrets.token_hex(8)


def _user() -> str:
    for key in ("USER", "USERNAME", "LOGNAME"):
        if os.environ.get(key):
            return os.environ[key]
    try:
        import getpass
        return getpass.getuser()
    except Exception:
        return "user"


def _host() -> str:
    try:
        return socket.gethostname().split(".")[0] or "localhost"
    except OSError:
        return "localhost"


def fleet_name() -> str:
    name = str(_config("fleet.name", "") or "").strip()
    return (name or f"{_user()}@{_host()}")[:64]


def harness() -> dict:
    from halo_harness import __version__
    return {"id": harness_id(), "name": fleet_name(), "host": _host(), "user": _user(), "version": __version__,
            "os": (platform.system() or os.name).lower()}


def project_stub(cwd) -> dict:
    return {"root": str(cwd), "repo": None, "branch": None, "dirty": None}


def _git(cwd: str, *args: str) -> Optional[str]:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=GIT_TIMEOUT_S, stdin=subprocess.DEVNULL, env=env)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _git_project(cwd: str) -> dict:
    top = _git(cwd, "rev-parse", "--show-toplevel")
    if not top:
        return project_stub(cwd)
    root = str(Path(top))
    url = _git(root, "config", "--get", "remote.origin.url") or ""
    repo = re.sub(r"\.git$", "", re.split(r"[/:]", url.rstrip("/"))[-1]) if url else ""
    status = _git(root, "status", "--porcelain", "--untracked-files=no")
    return {"root": root, "repo": repo or Path(root).name, "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": None if status is None else bool(status)}


def project(cwd, *, refresh: bool = False) -> dict:
    key = str(cwd)
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
    if hit is not None and not refresh and now - hit[0] < PROJECT_TTL_S:
        return dict(hit[1])
    info = _git_project(key)
    with _lock:
        _cache[key] = (now, info)
    return dict(info)


def session_kind(default: str) -> str:
    if os.environ.get("HALO_ORCHESTRA_RUN"):
        return "orchestra-worker"
    if os.environ.get("PAPERCLIP_AGENT_ID"):
        return "paperclip"
    return default


def parent_from_env() -> Optional[str]:
    sid = os.environ.get(PARENT_ENV) or ""
    return sid if _SID_RE.fullmatch(sid) else None


def parent_env(session_id: Optional[str]) -> dict:
    """`{HALO_FLEET_PARENT: sid}` for a child process this session starts ({} without one)."""
    return {PARENT_ENV: session_id} if session_id and _SID_RE.fullmatch(session_id) else {}
