"""halo_harness.remote.session_start -- a session started for a transport (Halo 3.3.13.0 R3; docs/REMOTE.md
"Transports"). A text from a phone with no session open starts one. A pack's service runs without Halo's provider
keys (supervise/services.py), so it asks the supervisor, which holds them, to start the session:

    request(cwd, model="", by="", state_dir=None) -> id      <state>/remote/session-requests/<id>.json (0600)
    serve(state_dir=None, spawn=None) -> [answer]            the supervisor: each request becomes `halo --headless
                                                             --session-for remote` (detached, its log under
                                                             <state>/run/headless/), the answer written beside it
    wait(rid, timeout_s=45, state_dir=None) -> (entry, line) the requester: the answer, then the session's registry row
                                                             once its control socket answers (None and one line when not)
    start(cwd, model="", by="", timeout_s=45) -> (entry, line)   request + wait; with no supervisor running (a transport
                                                             run by hand from a terminal) the session starts here

A request older than STALE_S is dropped unserved. Nothing here runs a model: the session does, when it is asked.
"""

from __future__ import annotations

import json
import os
from halo_harness import subprocess_safe as subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

STALE_S = 120.0
FOLDER = "session-requests"


def _dir(state_dir=None) -> Path:
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    return Path(state_dir) / "remote" / FOLDER


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(path: Path, data: dict) -> None:
    from halo_harness.privateio import write_private_atomic
    path.parent.mkdir(parents=True, exist_ok=True)
    write_private_atomic(path, json.dumps(data, sort_keys=True))


def request(cwd, model: str = "", by: str = "", state_dir=None) -> str:
    rid = uuid.uuid4().hex[:16]
    _write(_dir(state_dir) / f"{rid}.json", {"id": rid, "cwd": str(cwd), "model": str(model or ""),
                                              "by": str(by or "")[:40], "at": time.time()})
    return rid


def argv_for(sid: str, cwd: Path, model: str) -> list:
    argv = [sys.executable, "-u", "-m", "halo_harness", "--headless", "--session-for", "remote",
            "--session-id", sid, "--cwd", str(cwd)]
    return argv + (["--model", model] if model else [])


def spawn_session(cwd: Path, model: str, state_dir=None) -> dict:
    """Start one detached headless session (as Studio's New session does); its row."""
    from halo_harness.remote.session_identity import PARENT_ENV
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    sid = uuid.uuid4().hex
    log = Path(state_dir) / "run" / "headless" / f"{sid}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, PARENT_ENV: f"remote:{os.getpid()}"}
    kw: dict = {"stdin": subprocess.DEVNULL, "stderr": subprocess.STDOUT, "cwd": str(cwd), "env": env}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kw["start_new_session"] = True
    with open(log, "ab") as out:
        proc = subprocess.Popen(argv_for(sid, cwd, model), stdout=out, **kw)
    return {"session_id": sid, "pid": proc.pid, "cwd": str(cwd), "model": model, "log": str(log)}


def _default_model() -> str:
    from halo_harness.theme import get_config_value
    return str(get_config_value("model", "") or "")


def _check_cwd(raw) -> "tuple[Optional[Path], str]":
    p = Path(os.path.expanduser(str(raw or "~")))
    if not p.is_dir():
        return None, f"{raw} is not a folder on this machine"
    return p.resolve(), ""


def serve(state_dir=None, spawn: Optional[Callable] = None) -> list:
    """The supervisor's side: answer every waiting request; the answers written."""
    folder = _dir(state_dir)
    if not folder.is_dir():
        return []
    out = []
    now = time.time()
    for path in sorted(folder.glob("*.json")):
        if path.name.endswith(".answer.json"):
            if now - path.stat().st_mtime > STALE_S:
                path.unlink(missing_ok=True)
            continue
        req = _read(path)
        path.unlink(missing_ok=True)
        if not req.get("id") or now - float(req.get("at") or 0) > STALE_S:
            continue
        cwd, why = _check_cwd(req.get("cwd"))
        model = str(req.get("model") or "") or _default_model()
        ans: dict = {"id": req["id"], "model": model}
        if cwd is None:
            ans["error"] = why
        else:
            try:
                ans.update((spawn or spawn_session)(cwd, model, state_dir))
            except OSError as e:
                ans["error"] = f"the session could not start: {type(e).__name__}: {e}"
        _write(folder / f"{req['id']}.answer.json", ans)
        out.append(ans)
    return out


def wait(rid: str, timeout_s: float = 45.0, state_dir=None, *, live: Optional[Callable] = None) -> "tuple[Optional[dict], str]":
    from halo_harness.remote import registry
    live = live or registry.entry_for
    end = time.monotonic() + timeout_s
    path = _dir(state_dir) / f"{rid}.answer.json"
    ans: dict = {}
    while time.monotonic() < end:
        ans = ans or _read(path)
        if ans.get("error"):
            path.unlink(missing_ok=True)
            return None, str(ans["error"])
        if ans.get("session_id"):
            entry = live(ans["session_id"])
            if entry is not None:
                path.unlink(missing_ok=True)
                return entry, ""
        time.sleep(0.25)
    if not ans:
        return None, "the supervisor did not answer: is `halo supervise` running?"
    return None, f"the session started but did not answer in {int(timeout_s)} s (its log: {ans.get('log')})"


def start(cwd, model: str = "", by: str = "", timeout_s: float = 45.0, state_dir=None) -> "tuple[Optional[dict], str]":
    from halo_harness.supervise import pulse
    if os.environ.get("HALO_SUPERVISOR") or pulse.read(state_dir)["running"]:
        return wait(request(cwd, model, by, state_dir), timeout_s, state_dir)
    cwd_p, why = _check_cwd(cwd)
    if cwd_p is None:
        return None, why
    row = spawn_session(cwd_p, model or _default_model(), state_dir)
    from halo_harness.remote import registry
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        entry = registry.entry_for(row["session_id"])
        if entry is not None:
            return entry, ""
        time.sleep(0.25)
    return None, f"the session did not answer in {int(timeout_s)} s (its log: {row['log']})"
