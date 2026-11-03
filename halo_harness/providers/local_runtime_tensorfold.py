"""halo_harness.providers.local_runtime_tensorfold -- `halo local serve --runtime tensorfold --model <hf repo | checkpoint
dir> [--window N] [--parallel N] [--port P] [--keep] [--lan] [--yes]` (Halo 3.3.9.3; docs/MODELS-tensorfold.md "Serve"):
TensorFold's `tensorfold serve` as a managed subprocess, the way `halo local serve` runs llama-server.

    serve(model, *, port=None, keep=False, lan=False, window=None, parallel=None, state_dir=None, wait_s=None,
          confirm=None, fetcher=None, releases=None) -> (code, lines, row | None)
        code 0 serving (or still loading in the background, or already serving it), 1 not started (another model runs,
        a name clash, it exited), 2 the binary or the checkpoint is missing (one line with the route)
    argv(prefix, arg, *, name, port, window, key_file, lan=False, parallel=None) -> the command line
    entry() -> the `tensorfold` entry | None        forget(state_dir=None) -> the entry and the key file go

The command (README "Serve flags", from the source, unverified against a live run): `tensorfold serve <repo | dir>
--name <model> --host 127.0.0.1 --port <free loopback port> --context <N> --api-key-file <file>` -- the key Halo keeps in
the env file (HALO_SECRET_TENSORFOLD_API_KEY, never config.json) written to `<state>/local/servers/tensorfold.key`
(owner-only, 0600: TensorFold refuses a key file other users can read), so the key is never on the command line. With
keys on, `/health` answers only {"status": "ok"} and `/metrics` wants the key (docs/api.md "Health"): the steward
sends it. `--lan` binds 0.0.0.0 so peers reach it as `hf:local/<model>@<this host>` (tensorfold/peer.py). The server
opens its port once the checkpoint is loaded, so the wait polls `/health` for WAIT_S, after which the load goes on in
the background (the first load of a 70 GiB checkpoint takes minutes: said, never a timeout). TENSORFOLD_LOG_TIME=1 in
its environment stamps each `[tensorfold]` line with its UTC time (zig/src/server/log.zig). Its stdout and stderr go to
`<state>/local/servers/tensorfold.log` after Halo's `--- halo starts:` line; it is the registry row `tensorfold`.
"""

from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from halo_harness.tensorfold import KEY_ENV, NAME, RUNTIME

POLL_S = 0.2
WAIT_S = 120.0
DEFAULT_WINDOW = 32768


def _servers() -> list:
    from halo_harness.theme import get_config_value
    raw = get_config_value("huggingface.local_servers", default=None)
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def entry() -> Optional[dict]:
    return next((e for e in _servers() if str(e.get("name") or "").lower() == NAME), None)


def _state(state_dir):
    if state_dir is not None:
        return state_dir
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def key_file(state_dir=None) -> Path:
    from halo_harness.providers.local_server import servers_dir
    return servers_dir(_state(state_dir)) / f"{NAME}.key"


def forget(state_dir=None) -> bool:
    from halo_harness.theme import set_config_value
    try:
        key_file(state_dir).unlink()
    except OSError:
        pass
    rows = _servers()
    kept = [x for x in rows if not (str(x.get("name") or "").lower() == NAME and x.get("tensorfold") is True)]
    if len(kept) != len(rows):
        set_config_value("huggingface.local_servers", kept)
    return len(kept) != len(rows)


def key(*, make: bool = False) -> Optional[str]:
    """Halo's key for its TensorFold server: the env file's HALO_SECRET_TENSORFOLD_API_KEY, made once when `make`."""
    got = os.environ.get(KEY_ENV) or _peek()
    if got or not make:
        return got
    import secrets
    from halo_harness.init_cli import _env_file_path, _write_env_var
    k = secrets.token_urlsafe(24)
    _write_env_var(_env_file_path(), KEY_ENV, k)
    os.environ[KEY_ENV] = k
    return k


def _peek() -> Optional[str]:
    try:
        from halo_harness.providers.config import load_provider_env_files
        load_provider_env_files()
    except Exception:
        pass
    return os.environ.get(KEY_ENV) or None


def _write_key(path: Path, k: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink()
    except OSError:
        pass
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"halo: {k}\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def argv(prefix: list, arg: str, *, name: str, port: int, window: int, key_file: Path, lan: bool = False,
         parallel: Optional[int] = None) -> list:
    return list(prefix) + ["serve", str(arg), "--name", name, "--host", "0.0.0.0" if lan else "127.0.0.1", "--port",
                           str(port), "--context", str(int(window)), "--api-key-file", str(key_file)] + (
        ["--parallel", str(int(parallel))] if parallel else [])


def _binary(state_dir, confirm, fetcher, releases) -> "tuple[Optional[list], str, list]":
    from halo_harness.tensorfold import requirements as Q
    prefix, src = Q.binary(state_dir)
    if prefix is None and confirm is not None:
        from halo_harness.config.paths import background_net_disabled
        if releases is not None or not background_net_disabled():
            from halo_harness.providers.local_runtime_fetch_tf import ensure
            prefix, lines = ensure(state_dir, confirm=confirm, os_name=Q.os_word(), machine=Q.machine(),
                                   fetcher=fetcher, releases=releases)
            return prefix, "the release Halo fetched", lines
    if prefix is None:
        return None, "", [Q.missing_line(Q.os_word(), Q.machine(), found=False)]
    if Q.version(prefix) is None:
        return None, src, [Q.missing_line(Q.os_word(), Q.machine(), found=True)]
    return prefix, src, []


def serve(model: str, *, port: Optional[int] = None, keep: bool = False, lan: bool = False, window: Optional[int] = None,
          parallel: Optional[int] = None, state_dir=None, wait_s: Optional[float] = None, confirm=None, fetcher=None,
          releases=None) -> "tuple[int, list, Optional[dict]]":
    from halo_harness.tensorfold.source import missing_line, resolve
    state_dir = _state(state_dir)
    src = resolve(model)
    if src is None:
        p = Path(str(model)).expanduser()
        if p.is_absolute() or str(model).startswith((".", "~")) or p.exists():
            return 1, [f"no checkpoint folder at {model!r}: point --model at the folder that holds its config.json, or "
                       "name a Hugging Face repo (TensorFold serves it from the Hub cache)"], None
        return 2, [missing_line(str(model))], None
    prefix, how, lines = _binary(state_dir, confirm, fetcher, releases)
    if prefix is None:
        return 2, lines, None
    from halo_harness.bg_run import pid_alive
    from halo_harness.providers.local_server import _entry
    running = _entry(state_dir, NAME)
    if running is not None and pid_alive(running.get("pid")):
        say = f"tensorfold is running: {running.get('model')} on http://127.0.0.1:{running.get('port')}"
        same = running.get("model") == src["name"]
        return (0, lines + [say + ": already serving it"], running) if same else (
            1, lines + [say + " -- halo local stop tensorfold first"], None)
    clash = entry()
    if clash is not None and clash.get("tensorfold") is not True:
        return 1, [f"huggingface.local_servers has an entry named {NAME!r} that Halo did not write: rename it first"], None
    from halo_harness.tensorfold.catalog import match
    row = match(src["repo"] or src["name"])
    win, wsrc = (int(window), "--window") if window else ((row["context"], "TensorFold's table") if row and row.get(
        "context") else (DEFAULT_WINDOW, "Halo's default; --window sets it"))
    from halo_harness.local_sched.fit_tf import here_line
    lines = lines + ([here_line(row, win)] if row else [])
    return _start(prefix, src, win, wsrc, port=port, keep=keep, lan=lan, parallel=parallel, state_dir=state_dir,
                  wait_s=wait_s, how=how, lines=lines)


def _start(prefix, src: dict, window: int, wsrc: str, *, port, keep, lan, parallel, state_dir, wait_s, how, lines):
    from halo_harness.bg_run import process_start_time
    from halo_harness.providers import local_runtime as R
    from halo_harness.providers import local_server_cmd as C
    from halo_harness.providers.local_server import servers_dir
    port = int(port) if port else R.find_free_port()
    url, name = f"http://127.0.0.1:{port}", src["name"]
    log = servers_dir(state_dir) / f"{NAME}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    kf = key_file(state_dir)
    _write_key(kf, key(make=True) or "")
    cmd = argv(prefix, src["arg"], name=name, port=port, window=window, key_file=kf, lan=lan, parallel=parallel)
    env = {k: v for k, v in os.environ.items() if k not in ("TENSORFOLD_API_KEY", KEY_ENV)}
    env.update(TENSORFOLD_LOG_TIME="1", TENSORFOLD_NO_LIVE="1")
    lines = lines + [f"tensorfold from {how}: {name} from {src['where']}, window {window:,} ({wsrc})"
                     + ("; bound to every address" if lan else "") + ", behind Halo's key (a 0600 key file)",
                     "  " + " ".join(cmd)]
    with open(log, "ab") as out:
        out.write(f"--- halo starts: {' '.join(cmd)}\n".encode("utf-8"))
        out.flush()
        try:
            proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env)
        except OSError as e:
            return 1, lines + [f"tensorfold did not start: {e}"], None
    R._register_popen(proc)
    owner_pid, owner_start = R._owner_fingerprint()
    reg = {"id": NAME, "kind": RUNTIME, "runtime": RUNTIME, "model": name, "model_path": str(src["path"]),
           "repo": src["repo"], "pid": proc.pid, "port": port, "base_url": f"{url}/v1",
           "started": datetime.now(timezone.utc).isoformat(), "keep": bool(keep), "owner_pid": owner_pid,
           "owner_start": owner_start, "proc_start": process_start_time(proc.pid), "cmdline": list(cmd), "ready": False,
           "flags": {"lan": bool(lan), "window": window, "parallel": parallel}, "sources": {"binary": how, "window": wsrc},
           "log": str(log), "halo": True}
    with R._registry_lock(state_dir):
        R.save_registry(state_dir, [e for e in R.load_registry(state_dir) if e.get("id") != NAME and e.get("port") != port]
                        + [reg])
    end, ready = time.monotonic() + (wait_s if wait_s is not None else WAIT_S), False
    while True:
        code, _body = C.get(f"{url}/health", timeout=1.0)
        if code == 200:
            ready = True
            break
        if proc.poll() is not None:
            R.drop_registry_entries(state_dir, [(name, proc.pid)])
            R._forget_popen(proc.pid)
            tail = [x for x in C.tail_lines(log, 8) if x.strip() and not x.startswith("--- halo starts:")]
            driver = any("driver" in x.lower() or "libcuda" in x or "CUDA 13" in x for x in tail)
            return (2 if driver else 1), lines + [f"tensorfold serve exited ({proc.returncode}) before /health answered:"] + [
                f"  {x}" for x in tail], None
        if time.monotonic() >= end:
            break
        time.sleep(POLL_S)
    reg["ready"] = ready
    _mark(state_dir, ready)
    _write(reg, lan)
    lines.append(f"serving {name} (TensorFold) on {url} -- use it as hf:local/{name}@{NAME}" if ready else
                 f"{name} is still loading: TensorFold opens its port once the checkpoint is in memory (a large one takes "
                 f"minutes); it goes on in the background (halo local log {NAME} shows it)")
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
         "pid": row["pid"], "tensorfold": True, "lan": bool(lan), "api_key_env": KEY_ENV}
    set_config_value("huggingface.local_servers", [x for x in _servers() if str(x.get("name") or "").lower() != NAME] + [e])
