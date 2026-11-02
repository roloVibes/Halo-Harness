"""halo_harness.freetoken.launch -- `halo local serve --runtime freetoken --model <checkpoint dir> [--port P] [--keep]
[--lan]` (Halo 3.3.9.1; docs/MODELS-freetoken.md "Serve"): FreeToken's `ft serve` as a managed subprocess, like a
llama-server `halo local serve` starts.

    serve(model, *, port=None, keep=False, lan=False, state_dir=None, wait_s=None) -> (code, lines, row | None)
        code 0 serving (or still loading in the background, or already serving that model), 1 not started (no such
        checkpoint, another model runs, a name clash, it exited), 2 a requirement is missing (the one line)
    argv(prefix, path, *, name, port, lan) -> the command line     entry() -> the `freetoken` entry | None
    forget() -> the entry Halo wrote is removed (`halo local stop freetoken`)

The command (docs/cli.md, from the source, unverified against a live run): `ft serve --model <dir> --served-model-name
<name> --host 127.0.0.1 --port <free loopback port> --moe-collect-stats` -- `--moe-collect-stats` puts the expert
cache's hit rate on each decode log line, which the steward reads (ft-expert-thrash). `--lan` binds 0.0.0.0 so peers
reach it as `hf:local/<model>@<this host>` (freetoken/peer.py), behind a generated key handed to `ft serve` in its
environment as FREETOKEN_API_KEY, never on its command line. Its stdout and stderr go to `<state>/local/servers/
freetoken.log` after Halo's `--- halo starts:` line; it is the registry row `freetoken` (kind and runtime `freetoken`)
and the `huggingface.local_servers` entry {name: freetoken, url, log, runtime, model, pid, freetoken: true}.
`/health` answers `{"status": "loading", ...}` while the weights load and `"ok"` once ready (server/control_api.py,
from the source, unverified); the wait is WAIT_S, after which the load goes on in the background (said, never a
failure). The first request after an install compiles FreeToken's CUDA kernels for minutes: said here, and the
session's wait allows it (freetoken/waits.py).
"""

from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from halo_harness.freetoken import API_KEY_ENV, CUDA_LINE, KEY_ENV, NAME, RUNTIME

POLL_S = 0.2
WAIT_S = 120.0


def _servers() -> list:
    from halo_harness.theme import get_config_value
    raw = get_config_value("huggingface.local_servers", default=None)
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def entry() -> Optional[dict]:
    return next((e for e in _servers() if str(e.get("name") or "").lower() == NAME), None)


def forget() -> bool:
    from halo_harness.theme import set_config_value
    rows = _servers()
    kept = [x for x in rows if not (str(x.get("name") or "").lower() == NAME and x.get("freetoken") is True)]
    if len(kept) != len(rows):
        set_config_value("huggingface.local_servers", kept)
    return len(kept) != len(rows)


def key(*, make: bool = False) -> Optional[str]:
    if os.environ.get(KEY_ENV):
        return os.environ[KEY_ENV]
    try:
        from halo_harness.providers.config import load_provider_env_files
        load_provider_env_files()
    except Exception:
        pass
    if os.environ.get(KEY_ENV) or not make:
        return os.environ.get(KEY_ENV) or None
    import secrets
    from halo_harness.init_cli import _env_file_path, _write_env_var
    k = secrets.token_urlsafe(24)
    _write_env_var(_env_file_path(), KEY_ENV, k)
    os.environ[KEY_ENV] = k
    return k


def argv(prefix: list, path, *, name: str, port: int, lan: bool = False) -> list:
    return list(prefix) + ["serve", "--model", str(path), "--served-model-name", name, "--host",
                           "0.0.0.0" if lan else "127.0.0.1", "--port", str(port), "--moe-collect-stats"]


def _checkpoint(model: str) -> "tuple[Optional[Path], str]":
    p = Path(str(model)).expanduser()
    if p.is_dir():
        return p.resolve(), p.name
    try:
        from halo_harness.local_hf_serve_cli import _resolve
        raw = _resolve(model)
    except Exception:
        raw = None
    if raw and Path(raw["path"]).is_dir():
        return Path(raw["path"]), str(raw.get("model") or Path(raw["path"]).name)
    return None, ""


def _state(state_dir):
    if state_dir is not None:
        return state_dir
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def serve(model: str, *, port: Optional[int] = None, keep: bool = False, lan: bool = False, state_dir=None,
          wait_s: Optional[float] = None) -> "tuple[int, list, Optional[dict]]":
    from halo_harness.freetoken.requirements import binary, check
    state_dir = _state(state_dir)
    path, name = _checkpoint(model)
    if path is None:
        return 1, [f"no checkpoint folder at or named {model!r}: point --model at the folder that holds its config.json "
                   "(halo local download <repo> fetches one; halo local ls lists them)"], None
    prefix, src = binary()
    if src != "huggingface.freetoken_bin":  # a configured program is taken as stated (and is the tests' seam)
        chk = check()
        if not chk["ok"]:
            return 2, [chk["line"]], None
        prefix = chk["ft"]
    from halo_harness.bg_run import pid_alive
    from halo_harness.providers.local_server import _entry
    running = _entry(state_dir, NAME)
    if running is not None and pid_alive(running.get("pid")):
        say = f"freetoken is running: {running.get('model')} on http://127.0.0.1:{running.get('port')}"
        same = running.get("model") == name
        return (0, [say + ": already serving it"], running) if same else (1, [say + " -- halo local stop freetoken first"], None)
    clash = entry()
    if clash is not None and clash.get("freetoken") is not True:
        return 1, [f"huggingface.local_servers has an entry named {NAME!r} that Halo did not write: rename it first"], None
    return _start(prefix, path, name, port=port, keep=keep, lan=lan, state_dir=state_dir, wait_s=wait_s, src=src)


def _start(prefix, path: Path, name: str, *, port, keep, lan, state_dir, wait_s, src):
    from halo_harness.bg_run import process_start_time
    from halo_harness.providers import local_runtime as R
    from halo_harness.providers import local_server_cmd as C
    from halo_harness.providers.local_server import servers_dir
    port = int(port) if port else R.find_free_port()
    url = f"http://127.0.0.1:{port}"
    log = servers_dir(state_dir) / f"{NAME}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = argv(prefix, path, name=name, port=port, lan=lan)
    env = {k: v for k, v in os.environ.items() if k != API_KEY_ENV}
    if lan:
        env[API_KEY_ENV] = key(make=True) or ""
    lines = [f"ft from {src}" + (": bound to every address, behind Halo's key (FREETOKEN_API_KEY)" if lan else ""),
             "  " + " ".join(cmd)]
    with open(log, "ab") as out:
        out.write(f"--- halo starts: {' '.join(cmd)}\n".encode("utf-8"))
        out.flush()
        try:
            proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env)
        except OSError as e:
            return 1, lines + [f"ft did not start: {e}"], None
    R._register_popen(proc)
    owner_pid, owner_start = R._owner_fingerprint()
    reg = {"id": NAME, "kind": RUNTIME, "runtime": RUNTIME, "model": name, "model_path": str(path), "pid": proc.pid,
           "port": port, "base_url": f"{url}/v1", "started": datetime.now(timezone.utc).isoformat(), "keep": bool(keep),
           "owner_pid": owner_pid, "owner_start": owner_start, "proc_start": process_start_time(proc.pid),
           "cmdline": list(cmd), "ready": False, "flags": {"lan": bool(lan), "moe_collect_stats": True},
           "sources": {"binary": src}, "log": str(log), "halo": True}
    with R._registry_lock(state_dir):
        R.save_registry(state_dir, [e for e in R.load_registry(state_dir) if e.get("id") != NAME and e.get("port") != port]
                        + [reg])
    end, state, body = time.monotonic() + (wait_s if wait_s is not None else WAIT_S), "", {}
    while True:
        code, body = C.get(f"{url}/health", timeout=1.0)
        state = (body.get("status") if isinstance(body, dict) else "") if code == 200 else ""
        if state == "ok":
            break
        if proc.poll() is not None:
            R.drop_registry_entries(state_dir, [(name, proc.pid)])
            R._forget_popen(proc.pid)
            tail = [x for x in C.tail_lines(log, 8) if x.strip() and not x.startswith("--- halo starts:")]
            cuda = any("nvcc" in x or "CUDA" in x for x in tail)
            return (2 if cuda else 1), lines + [f"ft serve exited ({proc.returncode}) before /health said ok:"] + [
                f"  {x}" for x in tail] + ([f"  needs {CUDA_LINE}"] if cuda else []), None
        if time.monotonic() >= end:
            break
        time.sleep(POLL_S)
    ready = state == "ok"
    _mark(state_dir, ready)
    reg["ready"] = ready
    _write(reg, lan)
    prog = (body.get("progress") or {}) if isinstance(body, dict) else {}
    done = f" ({prog.get('done_bytes', 0) / 2 ** 30:.1f} of {prog.get('total_bytes', 0) / 2 ** 30:.1f} GiB)" if prog.get(
        "total_bytes") else ""
    lines.append(f"serving {name} (FreeToken) on {url} -- use it as hf:local/{name}@{NAME}" if ready else
                 f"{name} is still loading{done}: it goes on in the background (halo local log {NAME} shows it)")
    lines.append("  the first request after an install compiles FreeToken's CUDA kernels: minutes, once; the session "
                 "waits for it")
    lines.append(f"  halo local log {NAME}   halo local stop {NAME}")
    if not keep:
        lines.append("  it stops when the last Halo process on this home exits (--keep keeps it running)")
    return 0, lines, reg


def _mark(state_dir, ready: bool) -> None:
    from halo_harness.providers import local_runtime as R
    with R._registry_lock(state_dir):
        rows = R.load_registry(state_dir)
        for e in rows:
            if e.get("id") == NAME:
                e["ready"] = ready
        R.save_registry(state_dir, rows)


def _write(row: dict, lan: bool) -> None:
    from halo_harness.theme import set_config_value
    e = {"name": NAME, "url": row["base_url"], "log": row["log"], "runtime": RUNTIME, "model": row["model"],
         "pid": row["pid"], "freetoken": True, "lan": bool(lan), **({"api_key_env": KEY_ENV} if lan else {})}
    set_config_value("huggingface.local_servers", [x for x in _servers() if str(x.get("name") or "").lower() != NAME] + [e])
