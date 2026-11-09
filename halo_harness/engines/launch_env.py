"""halo_harness.engines.launch_env -- what a managed server's child is given, how its program is found, and whether
an engine checks Halo's key (Halo 3.3.14.0 R2: REVIEW #22 LOCAL-2, #24 LOCAL-4, #43 LOCAL-9).

    child_env(add=None, drop=()) -> dict   os.environ through providers.config.tool_child_env (Halo's provider keys,
        the env file's keys and a broker's keys left out, as for a Bash child), minus `drop`, plus `add`: what the
        server itself needs (an engine's own key). engines/launch.py, voice/launch.py, providers/local_server.py and
        providers/local_runtime.py start their servers with it.
    on_path(name) -> (path | None, line)   the program in a PATH folder only, never the current folder (Windows before
        Python 3.12 searches the current folder first); a program only the current folder holds is not run and the
        line says so
    vet(hit, name) -> (path | None, line)  a `shutil.which` hit checked the same way (a hit in the current folder is
        looked up again over the PATH folders alone)
    key_refused(url, wait_s=10.0) -> (True | False, why)   one GET of `<url>/models` with no key on the engine's
        loopback port: True when the engine refuses it (401 / 403)
    write_key(path, key)   the 0600 key file an engine reads (`halo: <key>`)
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional


def child_env(add: Optional[dict] = None, drop=()) -> dict:
    from halo_harness.providers.config import tool_child_env
    gone = set(drop)
    env = {k: v for k, v in tool_child_env(dict(os.environ)).items() if k not in gone}
    env.update(add or {})
    return env


def _norm(p) -> str:
    try:
        return os.path.normcase(str(Path(p).resolve()))
    except (OSError, ValueError):
        return os.path.normcase(str(p))


def _exts(name: str) -> list:
    if os.name != "nt":
        return [""]
    known = [e for e in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if e]
    return [""] if any(name.lower().endswith(e.lower()) for e in known) else known


def _in(folder: str, name: str) -> Optional[str]:
    for ext in _exts(name):
        p = os.path.join(folder, name + ext)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def on_path(name: str) -> "tuple[Optional[str], str]":
    for folder in os.environ.get("PATH", os.defpath).split(os.pathsep):
        if folder.strip() in ("", "."):  # the current folder by another name
            continue
        hit = _in(folder.strip().strip('"'), name)
        if hit:
            return hit, ""
    here = _in(os.getcwd(), name)
    if here:
        return None, f"{Path(here).name} in the current folder is not run: Halo runs {name} from a PATH folder only"
    return None, ""


def vet(hit: Optional[str], name: str) -> "tuple[Optional[str], str]":
    """A `shutil.which` hit kept when its folder is a PATH folder; a hit in the current folder (Windows before Python
    3.12 looks there first) is looked up again over the PATH folders alone."""
    if not hit or _norm(Path(hit).parent) != _norm(os.getcwd()):
        return hit, ""
    return on_path(name)


def key_refused(url: str, wait_s: float = 10.0) -> "tuple[bool, str]":
    from halo_harness.providers.local_server_cmd import get as http_get
    end = time.monotonic() + max(0.0, wait_s)
    while True:
        code, _body = http_get(str(url).rstrip("/") + "/models", timeout=2.0)
        if code in (200, 401, 403) or time.monotonic() >= end:
            break
        time.sleep(0.2)
    if code in (401, 403):
        return True, f"it refused a request without the key ({code})"
    if code == 200:
        return False, "it answered a request without Halo's key (200)"
    return False, f"it did not answer the key check ({code or 'no answer'})"


def write_key(path: Path, k: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink()
    except OSError:
        pass
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"halo: {k}\n")
