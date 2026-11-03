"""halo_harness.studio.sessions_new_api -- Studio starts a session with no terminal (Halo 3.3.11.0 R2). Same
guard as every Studio route.

    GET  sessions/new        {model: the default (config `model`), cwd: Studio's, models: [{ref, label, provider,
                              price, context}]} -- the first screen's model picker (the Setup default-model block's
                              rows: studio/model.py model_rows, cached, so a read opens no connection)
    POST sessions/new {model?, cwd?} -> 202 {session_id, pid, cwd, model, log, resume}
                             `halo --headless --session-for studio` (halo_harness/headless_session.py) as a child
                             detached the way studio/launch.py detaches Studio (no console, its own process group /
                             session), so closing the tab or stopping Studio never ends it; the session id is chosen
                             here (`--session-id`), so the page opens Session on it before it registers. 422: a cwd
                             that is not a folder; 502: the child could not start.
    GET  sessions/started    {sessions: [{session_id, pid, cwd, model, started, log, live}]} -- the children this
                             home's Studio started that still run (a restarted Studio finds them here)

"End session" is `POST sessions/<sid>/command {cmd: shutdown}` (studio/sessions_api.py): the child ends its turn
at the next tool boundary, closes its socket and leaves the registry. The children are kept in
`~/.halo/studio-sessions.json` ({version, sessions: [{session_id, pid, cwd, model, started, log}]}, private,
written under the file lock); a row whose pid is gone is dropped the next time the file is read.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

FILENAME = "studio-sessions.json"
LOG_DIR = ("run", "headless")
MAX_ROWS = 50
_procs: dict = {}  # pid -> Popen: polled on every read, so a child that ended is never a zombie that looks alive


def sessions_file(state_dir) -> Path:
    return Path(state_dir) / FILENAME


def _load(path: Path) -> list:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = data.get("sessions") if isinstance(data, dict) else None
    return [r for r in rows or [] if isinstance(r, dict) and r.get("session_id") and isinstance(r.get("pid"), int)]


def _alive(row: dict) -> bool:
    from halo_harness.bg_run import pid_alive
    return pid_alive(row.get("pid"))


def started(state_dir) -> list:
    """The rows whose child still runs; the file loses the others."""
    from halo_harness.filelock import file_lock
    from halo_harness.privateio import write_private_atomic
    for proc in list(_procs.values()):
        if proc.poll() is not None:
            _procs.pop(proc.pid, None)
    path = sessions_file(state_dir)
    if not path.exists():
        return []
    with file_lock(path, timeout=10.0):
        rows = _load(path)
        alive = [r for r in rows if _alive(r)]
        if len(alive) != len(rows):
            write_private_atomic(path, json.dumps({"version": 1, "sessions": alive}, indent=2))
    return alive


def remember(state_dir, row: dict) -> None:
    from halo_harness.filelock import file_lock
    from halo_harness.privateio import write_private_atomic
    path = sessions_file(state_dir)
    with file_lock(path, timeout=10.0):
        rows = [r for r in _load(path) if r.get("session_id") != row["session_id"] and _alive(r)]
        rows = (rows + [row])[-MAX_ROWS:]
        write_private_atomic(path, json.dumps({"version": 1, "sessions": rows}, indent=2))


def argv_for(sid: str, cwd: Path, model: str) -> list:
    argv = [sys.executable, "-u", "-m", "halo_harness", "--headless", "--session-for", "studio",
            "--session-id", sid, "--cwd", str(cwd)]
    return argv + (["--model", model] if model else [])


def spawn(argv: list, log: Path, cwd: Path) -> subprocess.Popen:
    """Detached as studio/launch.py detaches Studio: no console, its own group (Windows) or session (POSIX)."""
    from halo_harness.remote.fleet_identity import PARENT_ENV
    log.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, PARENT_ENV: f"studio:{os.getpid()}"}
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stderr": subprocess.STDOUT, "cwd": str(cwd), "env": env}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    with open(log, "ab") as out:
        return subprocess.Popen(argv, stdout=out, **kwargs)


def _default_model() -> str:
    from halo_harness.theme import get_config_value
    return str(get_config_value("model", "") or "")


def _cwd_of(req, raw) -> "tuple[Optional[Path], str]":
    text = str(raw or "").strip()
    if not text:
        return Path(req.cwd), ""
    p = Path(os.path.expanduser(text))
    if not p.is_absolute():
        p = Path(req.cwd) / p
    if not p.is_dir():
        return None, f"cwd {text!r} is not a folder on this machine"
    return p.resolve(), ""


def get_new(req):
    from halo_harness.studio import model as M
    rows = []
    try:
        for r in M.model_rows(req.state_dir, req.cwd, cached=True):
            rows.append({k: r.get(k) for k in ("ref", "label", "provider", "price", "context")})
    except Exception:
        rows = []
    return 200, {"model": _default_model(), "cwd": str(req.cwd), "models": rows}


def post_new(req):
    body = req.body if isinstance(req.body, dict) else {}
    cwd, why = _cwd_of(req, body.get("cwd"))
    if cwd is None:
        return 422, {"error": why, "problems": [why]}
    model = " ".join(str(body.get("model") or "").split())[:200]
    if model.startswith("-"):
        return 422, {"error": f"model {model!r} is not a model ref", "problems": ["model"]}
    sid = uuid.uuid4().hex
    log = Path(req.state_dir).joinpath(*LOG_DIR, f"{sid}.log")
    try:
        proc = spawn(argv_for(sid, cwd, model), log, cwd)
    except OSError as e:
        return 502, {"error": f"the session could not start: {e}"}
    _procs[proc.pid] = proc
    row = {"session_id": sid, "pid": proc.pid, "cwd": str(cwd), "model": model or _default_model(),
           "started": time.time(), "log": str(log)}
    remember(req.state_dir, row)
    if getattr(req, "server", None) is not None:
        threading.Thread(target=_nudge_bridge, args=(req.server, sid), name=f"halo-studio-nudge-{sid[:8]}", daemon=True).start()
    return 202, {**row, "resume": f"halo --cwd \"{cwd}\" --resume {sid}"}


def _nudge_bridge(server, sid: str, timeout_s: float = 60.0) -> None:
    """The event bridge scans the registry every two seconds; a child that registers and answers its first turn inside
    that window streams its reply before Studio listens (Linux shard 1, run 41702427101: the child's status said the
    turn ran, the page never saw it). Scan the moment the child's row appears instead."""
    from halo_harness.remote import registry
    from halo_harness.studio.events import bridge_for
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if registry.entry_for(sid) is not None:
            try:
                bridge_for(server).scan()
            except Exception:
                pass
            return
        time.sleep(0.2)


def get_started(req):
    from halo_harness.remote import registry
    live = {r.get("session_id") for r in registry.list_live()}
    return 200, {"sessions": [{**r, "live": r["session_id"] in live} for r in started(req.state_dir)]}


ROUTES = [("GET", r"^sessions/new$", get_new), ("POST", r"^sessions/new$", post_new),
          ("GET", r"^sessions/started$", get_started)]
