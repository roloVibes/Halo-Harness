"""halo_harness.engines.adapter -- one OpenAI-compatible adapter for every engine of the descriptor table: find its
program, recognise a running one, keep the `huggingface.local_servers` entry Halo writes for it, stop it.

    binary(engine) -> (argv prefix | None, where from)   `huggingface.engine_bins.<id>` (a path, or the program and its
        first arguments: the tests' fake), the old `huggingface.<id>_bin` (still read, `old_key` says so), else the
        descriptor's programs on PATH
    version(engine, prefix) -> "1.2.1" | None             facts() -> {os, arch, wsl}   os_word() -> "linux" | ...
    identify(base_url, rows, *, timeout=1.0) -> (engine id | None, {model id: window})   the auto-detect: owned_by on
        /v1/models, else the descriptor's /health keys (asked only when the rows carry no owned_by)
    health(url) -> {ok, ready, body}     alive(row) -> its pid lives or its port answers
    entry(engine) / forget(engine, state_dir=None) / write_entry(row, lan) / key(engine, make=False) / key_env(engine)
    stop_row(row, *, state_dir) -> {ok, id, say}   the descriptor's own stop (a supervised engine), else the process
    widen(conn, url) -> the session's wait for a first request the descriptor says is slow (FreeToken's kernel JIT)
    SEAMS: {"run", "which", "os", "machine", "wsl"} for tests. Nothing here downloads or installs an engine.
"""

from __future__ import annotations

import json
import os
import platform as _platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from halo_harness.engines.descriptors import TABLE, get

SEAMS: dict = {}


def run(argv: list, timeout: float = 20.0) -> "tuple[int, str]":
    if "run" in SEAMS:
        return SEAMS["run"](list(argv))
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def os_word() -> str:
    if "os" in SEAMS:
        return SEAMS["os"]()
    p = sys.platform
    return "linux" if p.startswith("linux") else "macos" if p == "darwin" else "windows" if p.startswith("win") else p


def facts() -> dict:
    arch = SEAMS["machine"]() if "machine" in SEAMS else (_platform.machine() or "").lower()
    wsl = SEAMS["wsl"]() if "wsl" in SEAMS else ("microsoft" in _platform.release().lower() and os_word() == "linux")
    return {"os": os_word(), "arch": arch, "wsl": bool(wsl)}


def old_key(engine: str) -> str:
    return f"huggingface.{engine}_bin"


def binary(engine: str) -> "tuple[Optional[list], str]":
    from halo_harness.theme import get_config_value
    bins = get_config_value("huggingface.engine_bins", default=None)
    for key, raw in ((f"huggingface.engine_bins.{engine}", (bins or {}).get(engine) if isinstance(bins, dict) else None),
                     (old_key(engine), get_config_value(old_key(engine), default=None))):
        if isinstance(raw, list) and raw and all(isinstance(x, str) for x in raw):
            return list(raw), key
        if isinstance(raw, str) and raw.strip():
            return [raw.strip()], key
    which = SEAMS.get("which") or shutil.which
    for name in get(engine)["programs"]:
        if found := which(name):
            return [found], f"{name} on PATH"
    return None, ""


def version(engine: str, prefix: Optional[list]) -> Optional[str]:
    if not prefix:
        return None
    rc, out = run(list(prefix) + ["--version"])
    m = re.search(get(engine)["version"], out, re.M) if rc == 0 else None
    return m.group(1) if m else None


def _window(row: dict, key: str) -> Optional[int]:
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    n = meta.get(key, row.get(key))
    return n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else None


def identify(base_url: str, rows: list, *, timeout: float = 1.0) -> "tuple[Optional[str], dict]":
    owners = {str(r.get("owned_by") or "") for r in rows if isinstance(r, dict)}
    for d in TABLE.values():
        if d["detect"].get("owned_by") in owners:
            return d["id"], {}
    bare = [r for r in rows if isinstance(r, dict) and not r.get("owned_by")]
    probes = [d for d in TABLE.values() if d["detect"].get("health")  # asked only when a row has the engine's shape
              and any(_window(r, d["detect"].get("window") or "") for r in bare)]
    if not bare or not probes:
        return None, {}
    from halo_harness.providers.huggingface_local_probe import _probe_get
    root = str(base_url or "").rstrip("/")
    got = _probe_get(root[:-3] if root.endswith("/v1") else root, "/health", api_key=None, timeout=timeout)
    for d in probes:
        want = d["detect"]["health"]
        if isinstance(got, dict) and all(str(got.get(k) or "").lower() == v for k, v in want.items()):
            key = d["detect"].get("window") or ""
            return d["id"], {str(r["id"]): w for r in bare if r.get("id") and (w := _window(r, key))}
    return None, {}


def health(url: str, timeout: float = 1.0) -> dict:
    from halo_harness.providers.local_server_cmd import get as http_get
    code, body = http_get(str(url).rstrip("/").removesuffix("/v1") + "/health", timeout=timeout)
    b = body if isinstance(body, dict) else {}
    ok = code == 200
    return {"ok": ok, "ready": ok and b.get("status") != "loading" and b.get("loaded", True) is not False, "body": b}


def alive(e: dict) -> bool:
    from halo_harness.bg_run import pid_alive
    if isinstance(e.get("pid"), int) and pid_alive(e["pid"]):
        return True
    return bool(e.get("port")) and health(f"http://127.0.0.1:{int(e['port'])}", timeout=0.5)["ok"]


def _servers() -> list:
    from halo_harness.theme import get_config_value
    raw = get_config_value("huggingface.local_servers", default=None)
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def ours(e: dict, engine: str) -> bool:
    """An entry Halo wrote for this engine (`engine: <id>`; before 3.3.13.0 `<id>: true`)."""
    return str(e.get("name") or "").lower() == engine and (e.get("engine") == engine or e.get(engine) is True)


def entry(engine: str) -> Optional[dict]:
    return next((e for e in _servers() if str(e.get("name") or "").lower() == engine), None)


def key_env(engine: str) -> str:
    return f"HALO_SECRET_{engine.upper()}_API_KEY"


def key_file(engine: str, state_dir) -> Path:
    from halo_harness.providers.local_server import servers_dir
    return servers_dir(state_dir) / f"{engine}.key"


def forget(engine: str, state_dir=None) -> bool:
    from halo_harness.theme import set_config_value
    if state_dir is not None:
        try:
            key_file(engine, state_dir).unlink()
        except OSError:
            pass
    rows = _servers()
    kept = [x for x in rows if not ours(x, engine)]
    if len(kept) != len(rows):
        set_config_value("huggingface.local_servers", kept)
    return len(kept) != len(rows)


def key(engine: str, *, make: bool = False) -> Optional[str]:
    """Halo's key for its server of this engine: the env file's HALO_SECRET_<ID>_API_KEY, made once when `make`."""
    name = key_env(engine)
    if not os.environ.get(name):
        try:
            from halo_harness.providers.config import load_provider_env_files
            load_provider_env_files()
        except Exception:
            pass
    if os.environ.get(name) or not make:
        return os.environ.get(name) or None
    import secrets
    from halo_harness.init_cli import _env_file_path, _write_env_var
    k = secrets.token_urlsafe(24)
    _write_env_var(_env_file_path(), name, k)
    os.environ[name] = k
    return k


def write_entry(row: dict, lan: bool) -> None:
    from halo_harness.theme import set_config_value
    engine = row["kind"]
    e = {"name": engine, "url": row["base_url"], "log": row["log"], "runtime": engine, "model": row["model"],
         "pid": row.get("pid"), "engine": engine, "lan": bool(lan), "api_key_env": key_env(engine)}
    set_config_value("huggingface.local_servers", [x for x in _servers() if str(x.get("name") or "").lower() != engine]
                     + [e])


def status_rows(engine: str, prefix) -> Optional[list]:
    """A supervised engine's own status command (Strata's `launch --status --output json`): its running rows."""
    cmd = (get(engine).get("start") or {}).get("status")
    if not prefix or not cmd:
        return None
    rc, out = run(list(prefix) + cmd)
    try:
        got = json.loads(out.strip().splitlines()[-1]) if rc == 0 and out.strip() else None
    except (ValueError, IndexError):
        got = None
    rows = got.get("running") if isinstance(got, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else None


def stop_row(e: dict, *, state_dir) -> dict:
    from halo_harness.providers import local_runtime as R
    from halo_harness.providers import local_server_cmd as C
    engine, start = e["kind"], get(e["kind"]).get("start") or {}
    if start.get("supervised"):
        prefix, _src = binary(engine)
        hit = next((r for r in status_rows(engine, prefix) or [] if str(r.get("port")) == str(e.get("port"))), None)
        if hit is not None:
            rc, out = run(list(prefix) + [str(a).format(**hit) for a in start["stop"]], timeout=200.0)
            how = (out.strip().splitlines() or [f"answered {rc}"])[-1]
        else:
            how = f"nothing {get(engine)['label']} runs serves port {e.get('port')} any more"
    else:
        how = C.halt(e["pid"]) if R._entry_process_matches(e) else "its pid belongs to another process now: nothing signalled"
    R.drop_registry_entries(state_dir, [(e.get("model"), e.get("pid"))])
    forget(engine, state_dir)
    return {"ok": True, "id": e.get("id"), "say": f"stopped {engine} {e.get('id')} ({e.get('model')} on port "
                                                  f"{e.get('port')}): {how}"}


def widen(conn, url) -> None:
    """A FreeToken-like engine's first request compiles for minutes: the connection's idle wait is the descriptor's."""
    try:
        from halo_harness.ollama_steward.servers_hf import for_url
        s = for_url(url) if url and getattr(conn, "sock", None) is not None else None
        wait = (get(s.runtime) or {}).get("first_wait_s") if s is not None else None
        if wait:
            conn.sock.settimeout(float(wait))
    except Exception:
        pass
