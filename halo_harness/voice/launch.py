"""halo_harness.voice.launch -- `halo local serve --stt | --tts <model>` (Halo 3.3.9.0 R1; docs/VOICE.md "Serve"):
Halo's own speech server as a managed subprocess, exactly like a llama-server `halo local serve` starts.

    serve(kind, model, *, device=None, port=None, keep=False, state_dir=None, wait_s=None) -> (code, lines, row|None)
        code 0 serving (or already serving that model), 1 not started (not present, another model runs, a clash, the
        load failed), 2 nothing to run (a declared model with no engine, the extra not installed: the install line)
    entry(kind) -> the `huggingface.local_servers` entry named `stt` / `tts` | None      forget(kind) -> it is removed

The server runs `huggingface.voice_server_cmd` (the test seam: tests/helpers/fake_voice_server.py), else
`<python> -m halo_harness.voice.server`, on a free loopback port, its stdout and stderr in
`<state>/local/servers/<kind>.log` after Halo's `--- halo starts:` line. It is the managed-servers registry row `stt`
/ `tts` (kind and runtime `voice-stt` / `voice-tts`, its device and log), and the `huggingface.local_servers` entry of
the same name {name, url, log, runtime, model, device, pid, voice: true} the steward reads. `halo local stop stt`,
`halo local log stt`, `halo local servers` work unchanged; a second serve while one runs says the running one.
"""

from __future__ import annotations

from halo_harness import subprocess_safe as subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from halo_harness.voice import INSTALL_LINE, runtime_for

POLL_S = 0.2
WAIT_S = 120.0


def _servers() -> list:
    from halo_harness.theme import get_config_value
    raw = get_config_value("huggingface.local_servers", default=None)
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def entry(kind: str) -> Optional[dict]:
    return next((e for e in _servers() if str(e.get("name") or "").lower() == kind), None)


def _write(kind: str, row: dict) -> None:
    from halo_harness.theme import set_config_value
    e = {"name": kind, "url": row["base_url"], "log": row["log"], "runtime": row["runtime"], "model": row["model"],
         "device": row["device"], "pid": row["pid"], "voice": True}
    set_config_value("huggingface.local_servers", [x for x in _servers() if str(x.get("name") or "").lower() != kind] + [e])


def forget(kind: str) -> bool:
    from halo_harness.theme import set_config_value
    rows = _servers()
    kept = [x for x in rows if not (str(x.get("name") or "").lower() == kind and x.get("voice") is True)]
    if len(kept) != len(rows):
        set_config_value("huggingface.local_servers", kept)
    return len(kept) != len(rows)


def server_cmd() -> "tuple[list, bool]":
    """(the program and its first arguments, whether it is the configured seam)."""
    from halo_harness.theme import get_config_value
    raw = get_config_value("huggingface.voice_server_cmd", default=None)
    if isinstance(raw, list) and raw and all(isinstance(x, str) for x in raw):
        return list(raw), True
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()], True
    return [sys.executable, "-m", "halo_harness.voice.server"], False


def _state(state_dir):
    if state_dir is not None:
        return state_dir
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def serve(kind: str, model: str, *, device: Optional[str] = None, port: Optional[int] = None, keep: bool = False,
          state_dir=None, wait_s: Optional[float] = None) -> "tuple[int, list, Optional[dict]]":
    from halo_harness.voice import catalog
    from halo_harness.voice.install import present
    state_dir = _state(state_dir)
    row = catalog.get(model)
    if row is None or row.kind != kind:
        names = ", ".join(r.name for r in catalog.of_kind(kind))
        return 1, [f"{model} is not a {kind.upper()} model of the speech catalog: {names} (halo voice models)"], None
    if not row.built:
        return 2, [catalog.no_engine_line(row)], None
    from halo_harness.providers.local_server import _entry
    from halo_harness.bg_run import pid_alive
    running = _entry(state_dir, kind)
    if running is not None and pid_alive(running.get("pid")):
        same = running.get("model") == row.name
        say = (f"{kind} is running: {running.get('model')} on http://127.0.0.1:{running.get('port')} "
               f"({running.get('device')})")
        return (0, [say + ": already serving it"], running) if same else (1, [say + f" -- halo local stop {kind} first"], None)
    clash = entry(kind)
    if clash is not None and clash.get("voice") is not True:
        return 1, [f"huggingface.local_servers has an entry named {kind!r} that the speech server did not write: rename "
                   "it first"], None
    prefix, seam = server_cmd()
    if not seam:
        from halo_harness.voice.engines import missing
        if missing(row.engine):
            return 2, [f"the speech engines are not installed: {INSTALL_LINE}"], None
    path = present(row)
    if path is None:
        return 1, [f"{row.name} is not present -- halo voice download {row.name} ({row.download_gb:g} GB)"], None
    from halo_harness.voice.device import choose
    dev = choose(row, device)
    return _start(kind, row, path, dev, prefix, port=port, keep=keep, state_dir=state_dir, wait_s=wait_s)


def _start(kind, row, path: Path, dev: dict, prefix: list, *, port, keep, state_dir, wait_s):
    from halo_harness.bg_run import process_start_time
    from halo_harness.providers import local_runtime as R
    from halo_harness.providers import local_server_cmd as C
    from halo_harness.providers.local_server import servers_dir
    port = int(port) if port else R.find_free_port()
    url = f"http://127.0.0.1:{port}"
    log = servers_dir(state_dir) / f"{kind}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    argv = prefix + ["--kind", kind, "--model", row.name, "--path", str(path), "--device", dev["device"], "--port",
                     str(port), "--log", str(log)] + (["--gpu-free-mib", str(dev["cuda_free_mib"])]
                                                      if isinstance(dev.get("cuda_free_mib"), int) else [])
    lines = [dev["line"], "  " + " ".join(argv)]
    with open(log, "ab") as out:
        out.write(f"--- halo starts: {' '.join(argv)}\n".encode("utf-8"))
        out.flush()
        try:  # 3.3.14.0 R2 (REVIEW #22): a tool child's environment, Halo's provider keys left out
            from halo_harness.engines.launch_env import child_env
            proc = subprocess.Popen(argv, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    env=child_env())
        except OSError as e:
            return 1, lines + [f"the speech server did not start: {e}"], None
    R._register_popen(proc)
    owner_pid, owner_start = R._owner_fingerprint()
    rt = runtime_for(kind)
    reg = {"id": kind, "kind": rt, "runtime": rt, "model": row.name, "model_path": str(path), "pid": proc.pid,
           "port": port, "base_url": f"{url}/v1", "started": datetime.now(timezone.utc).isoformat(), "keep": bool(keep),
           "owner_pid": owner_pid, "owner_start": owner_start, "proc_start": process_start_time(proc.pid),
           "cmdline": list(argv), "ready": False, "flags": {"device": dev["device"]}, "sources": {"device": dev["line"]},
           "log": str(log), "halo": True, "device": dev["device"]}
    with R._registry_lock(state_dir):
        R.save_registry(state_dir, [e for e in R.load_registry(state_dir) if e.get("id") != kind and e.get("port") != port]
                        + [reg])
    end = time.monotonic() + (wait_s if wait_s is not None else WAIT_S)
    while True:
        code, _body = C.get(f"{url}/health", timeout=1.0)
        if code == 200:
            break
        if proc.poll() is not None:
            R.drop_registry_entries(state_dir, [(row.name, proc.pid)])
            R._forget_popen(proc.pid)
            tail = [x for x in C.tail_lines(log, 8) if x.strip() and not x.startswith("--- halo starts:")]
            return (2 if any(INSTALL_LINE in x for x in tail) else 1), lines + [
                f"the speech server exited ({proc.returncode}) before it answered /health:"] + [f"  {x}" for x in tail], None
        if time.monotonic() >= end:
            break
        time.sleep(POLL_S)
    ready = code == 200
    with R._registry_lock(state_dir):
        rows = R.load_registry(state_dir)
        for e in rows:
            if e.get("id") == kind:
                e["ready"] = ready
        R.save_registry(state_dir, rows)
    reg["ready"] = ready
    _write(kind, reg)
    route = "/v1/audio/transcriptions" if kind == "stt" else "/v1/audio/speech"
    lines.append(f"serving {row.name} ({kind}) on {url}: POST {url}{route}" if ready else
                 f"{row.name} is still loading: it goes on in the background (halo local log {kind} shows it)")
    lines.append(f"  halo local log {kind}   halo local stop {kind}")
    if not keep:
        lines.append("  it stops when the last Halo process on this home exits (--keep keeps it running)")
    return 0, lines, reg
