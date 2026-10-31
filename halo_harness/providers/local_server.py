"""halo_harness.providers.local_server -- Halo 3.3.5.0 R5: a local server Halo starts for a model file on disk, its
health, its log, and stopping it (the command line is providers/local_server_cmd.py).

    start(model_path, *, runtime, port=0, window, ngl, parallel, kv_type, flash_attn, log_dir, ...) -> ServerInfo
    stop(id_or_port, *, state_dir)    terminate, then kill after STOP_GRACE_S
    tail(id, n, *, state_dir)         the last lines of <state>/local/servers/<id>.log
    status(id, *, state_dir)          /health (and /slots when llama-server answers it)
    servers(state_dir)                every server in the registry, each with whether its process lives
    exit_sweep(state_dir)             at a Halo process's exit: its own servers, and those whose starter is gone
                                      while no other Halo process runs on this home -- unless `keep`

The server's stdout and stderr go to its log; `/health` is polled until it answers ok, up to `wait_s` (the default
scales with the file's size, providers/local_runtime._startup_timeout_for_size), past which the answer says "still
loading" and the server keeps going. Each server is a row of the managed-servers registry the probe already reads
(<state>/run/local-servers.json, providers/local_runtime.py), so the catalog lists it as `hf:local/<model>` and
Local -> Hosts shows it: {id, kind, model, model_path, runtime, pid, port, base_url, flags, sources, log, keep, ready,
started, halo: true, owner_pid, ...}. A server Halo did not start has no row: it is listed from the probe and is
stopped where it was started.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

POLL_S = 0.25
FMT = {"llama-server": "llama-server", "mlx": "mlx_lm"}


@dataclass
class ServerInfo:
    id: str
    model: str
    kind: str
    port: int
    url: str
    pid: Optional[int] = None
    ready: bool = False
    ok: bool = True
    say: str = ""
    flags: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)
    argv: list = field(default_factory=list)
    log: str = ""
    keep: bool = False
    model_path: str = ""


def servers_dir(state_dir) -> Path:
    return Path(state_dir) / "local" / "servers"


def _entry(state_dir, key) -> Optional[dict]:
    from halo_harness.providers.local_runtime import load_registry
    k = str(key).strip()
    rows = load_registry(state_dir)
    return next((e for e in rows if e.get("id") == k), None) or next(
        (e for e in rows if k.isdigit() and int(k) == e.get("port")), None) or next((e for e in rows if e.get("model") == k), None)


def start(model_path, *, runtime: str, port: int = 0, window: int, ngl: int, parallel: int = 1, kv_type=None,
          flash_attn: bool = False, log_dir=None, num_predict=None, model: str = "", keep: bool = False, state_dir=None,
          wait_s: Optional[float] = None, sources: Optional[dict] = None, prefix: Optional[list] = None) -> ServerInfo:
    from halo_harness.bg_run import process_start_time
    from halo_harness.providers import local_runtime as R
    from halo_harness.providers import local_server_cmd as C
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    path = Path(model_path)
    model = model or (path.stem if path.suffix.lower() == ".gguf" else path.name)
    port = int(port) if port else R.find_free_port()
    sid = f"{'mlx' if runtime == 'mlx' else 'llama'}-{port}"
    info = ServerInfo(id=sid, model=model, kind=runtime, port=port, url=f"http://127.0.0.1:{port}", keep=bool(keep),
                      model_path=str(path), sources=dict(sources or {}))
    if prefix is None:
        prefix, why = C.binary(runtime, state_dir=state_dir)
        info.sources["binary"] = why
        if prefix is None:
            info.ok, info.say = False, why
            return info
    flags = {"window": int(window), "ngl": int(ngl), "parallel": int(parallel or 1), "kv_type": kv_type,
             "flash_attn": bool(flash_attn), "num_predict": num_predict}
    info.flags = flags
    info.argv = (C.mlx_argv(prefix, path=path, port=port) if runtime == "mlx"
                 else C.llama_argv(prefix, path=path, model=model, port=port, flags=flags))
    log = Path(log_dir or servers_dir(state_dir)) / f"{sid}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    info.log = str(log)
    with open(log, "ab") as out:
        out.write(f"--- halo starts: {' '.join(info.argv)}\n".encode("utf-8"))
        out.flush()
        try:
            proc = subprocess.Popen(info.argv, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        except OSError as e:
            info.ok, info.say = False, f"{runtime} did not start: {e}"
            return info
    R._register_popen(proc)
    info.pid = proc.pid
    owner_pid, owner_start = R._owner_fingerprint()
    entry = {"model": model, "runtime": FMT.get(runtime, runtime), "pid": proc.pid, "port": port,
             "base_url": f"{info.url}/v1", "started": datetime.now(timezone.utc).isoformat(), "keep": bool(keep),
             "owner_pid": owner_pid, "owner_start": owner_start, "proc_start": process_start_time(proc.pid),
             "cmdline": list(info.argv), "ready": False, "id": sid, "kind": runtime, "model_path": str(path),
             "flags": flags, "sources": info.sources, "log": str(log), "halo": True}
    with R._registry_lock(state_dir):  # keyed by id: two servers of one model are two rows
        R.save_registry(state_dir, [e for e in R.load_registry(state_dir) if e.get("id") != sid and e.get("port") != port] + [entry])
    size = path.stat().st_size if path.is_file() else None
    cap = wait_s if wait_s is not None else R._startup_timeout_for_size(size)
    end = time.monotonic() + cap
    while True:
        code, _body = C.get(f"{info.url}/health", timeout=1.0)
        if code == 200:
            info.ready = True
            break
        if proc.poll() is not None:
            R.drop_registry_entries(state_dir, [(model, proc.pid)])
            R._forget_popen(proc.pid)
            info.ok = False
            info.say = f"{runtime} exited ({proc.returncode}) before it answered /health: " + " | ".join(C.tail_lines(log, 6))
            return info
        if time.monotonic() >= end:
            break
        time.sleep(POLL_S)
    _mark(state_dir, sid, ready=info.ready)
    info.say = (f"serving {model} on {info.url} -- use it as hf:local/{model}" if info.ready else
                f"still loading after {cap:.0f} s: it goes on in the background (halo local log {sid} shows its progress)")
    return info


def _mark(state_dir, sid: str, **fields) -> None:
    from halo_harness.providers import local_runtime as R
    with R._registry_lock(state_dir):
        rows = R.load_registry(state_dir)
        for e in rows:
            if e.get("id") == sid:
                e.update(fields)
        R.save_registry(state_dir, rows)


def stop(key, *, state_dir) -> dict:
    from halo_harness.providers import local_runtime as R
    from halo_harness.providers import local_server_cmd as C
    e = _entry(state_dir, key)
    if e is None or not e.get("halo"):
        return {"ok": False, "ours": e is not None, "say": f"no server Halo started is {key!r}: a server Halo did not "
                "start is stopped where it was started (halo local servers lists Halo's)"}
    how = C.halt(e["pid"]) if R._entry_process_matches(e) else "its pid belongs to another process now: nothing signalled"
    R.drop_registry_entries(state_dir, [(e.get("model"), e.get("pid"))])
    return {"ok": True, "id": e["id"], "say": f"stopped {e['kind']} {e['id']} ({e['model']} on port {e['port']}): {how}"}


def tail(key, n: int = 40, *, state_dir) -> dict:
    from halo_harness.providers import local_server_cmd as C
    e = _entry(state_dir, key)
    path = Path(e["log"]) if e and e.get("log") else servers_dir(state_dir) / f"{key}.log"
    lines = C.tail_lines(path, n)
    return {"ok": bool(lines) or path.is_file(), "path": str(path), "lines": lines,
            "say": "" if path.is_file() else f"no log for {key!r} under {servers_dir(state_dir)}"}


def status(key, *, state_dir) -> dict:
    e = _entry(state_dir, key)
    if e is None:
        return {"ok": False, "say": f"no server Halo started is {key!r}"}
    from halo_harness.providers.local_server_cmd import get
    url = f"http://127.0.0.1:{e['port']}"
    code, health = get(f"{url}/health")
    out = {"ok": True, "id": e.get("id"), "health": health if code else None, "status": code, "ready": code == 200,
           "say": "ready" if code == 200 else ("still loading" if code == 503 else f"not answering ({health})")}
    if code == 200 and e.get("kind") == "llama-server":
        scode, slots = get(f"{url}/slots")
        out["slots"] = slots if scode == 200 else None
        if not e.get("ready"):
            _mark(state_dir, e["id"], ready=True)
    return out


def servers(state_dir) -> list:
    from halo_harness.bg_run import pid_alive
    from halo_harness.providers.local_runtime import load_registry
    return [{**e, "alive": pid_alive(e.get("pid"))} for e in load_registry(state_dir) if e.get("halo")]


def view(info: ServerInfo) -> dict:
    return asdict(info)


def _others_alive(state_dir) -> bool:
    from halo_harness.bg_run import pid_alive
    try:
        from halo_harness.remote.registry import list_live
        if any(r.get("pid") not in (None, os.getpid()) for r in list_live()):
            return True
        from halo_harness.studio.launch import read_info
        info = read_info(Path(state_dir)) or {}
        return info.get("pid") not in (None, os.getpid()) and pid_alive(info.get("pid"))
    except Exception:
        return False


def exit_sweep(state_dir=None) -> list:
    """Stop this process's servers, and the ones whose starter has exited when no other Halo runs here (not `keep`)."""
    from halo_harness.bg_run import pid_alive
    from halo_harness.providers.local_runtime import _entry_owned_by_this_process
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    try:
        rows = [e for e in servers(state_dir) if not e.get("keep")]
        others = None
        out = []
        for e in rows:
            mine = _entry_owned_by_this_process(e)
            if not mine:
                others = _others_alive(state_dir) if others is None else others
                if others or pid_alive(e.get("owner_pid")):
                    continue
            out.append(stop(e["id"], state_dir=state_dir))
        return out
    except Exception:
        return []
