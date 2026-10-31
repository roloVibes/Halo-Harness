"""halo_harness.host.state -- the host's files and config keys (Halo 3.3.7.0 R1; docs/HOST.md).

Files under `<state>/host/` (all 0600):

    serve.json    {pid, port, bind, tls, fingerprint, name, url, started, grants_file, watches}   while it runs
    codes.json    the one-time pairing codes (fleet/pairing.py's shape: a hash of each code, never the code)
    peers.json    {version, members: {<harness id>: {id, name, host, user, version, os, key_hex, paired_at, address,
                   grants: ["view"]}}, kicked: {...}}   the paired peers (fleet/pairing.py's file shape)
    audit.jsonl   {at, peer, path, ok, ms} one line per request (the offline promise's evidence); R2: an acting
                  request's line adds {op, params, evidence, dry, landed, fix, change_id?, job?}
    pending.jsonl R2: the requests queued under fleet.allow_control: ask (host/pending.py)
    fixes.jsonl   R2: each profile fix's before / after / verdict (host/verify.py)
    steward.json  R2: the duty steward's process {pid, model, peer, started} (host_steward_cli.py)
    cert.pem, key.pem   the host's self-signed certificate (fleet/tls.py), pinned by every peer
    stop          `halo host stop` writes it; the running host sees it within a second and stops

Config keys (docs/CONFIG.md): `host.port` (7431), `host.bind` ("0.0.0.0"), `host.enabled` (true), `host.tail_max`
(400); R2: `host.ask_ttl_s` (600), `host.cooldown_s` (120), `host.changes_per_hour` (10), `host.verify_calls` (5),
`host.verify_s` (600), `host.steward.enabled` (false), `host.steward.model`, `host.steward.every_s` (300). The grants
are `view` (every peer), `control`, `manage`, `admin` (host/grants.py).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from halo_harness.fleet import identity
from halo_harness.fleet.pairing import HubPairing

DEFAULT_PORT = 7431
DEFAULT_BIND = "0.0.0.0"
TAIL_MAX = 400
GRANTS = ("view", "control", "manage", "admin")
DEFAULT_GRANTS = ("view",)
SERVE_FILE, AUDIT_FILE, PEERS_FILE, STOP_FILE = "serve.json", "audit.jsonl", "peers.json", "stop"
AUDIT_KEEP_BYTES = 4 * 2 ** 20


def host_dir(home) -> Path:
    return Path(home) / "host"


def _cfg(key: str, default, home=None):
    return identity.config_value(key, default, Path(home) if home is not None else None)


def port(home=None) -> int:
    try:
        p = int(_cfg("host.port", DEFAULT_PORT, home))
    except (TypeError, ValueError):
        return DEFAULT_PORT
    return p if 0 <= p <= 65535 else DEFAULT_PORT


def bind(home=None) -> str:
    return str(_cfg("host.bind", DEFAULT_BIND, home) or DEFAULT_BIND).strip() or DEFAULT_BIND


def enabled(home=None) -> bool:
    return _cfg("host.enabled", True, home) is not False


def tail_max(home=None) -> int:
    try:
        n = int(_cfg("host.tail_max", TAIL_MAX, home))
    except (TypeError, ValueError):
        return TAIL_MAX
    return max(1, min(n, 2000))


class HostPairing(HubPairing):
    """fleet/pairing.py's codes and records, kept under `<state>/host/` (codes.json, peers.json)."""

    def __init__(self, home, clock=time.time) -> None:
        super().__init__(home, clock)
        self.dir = host_dir(home)
        self.codes_path = self.dir / "codes.json"
        self.members_path = self.dir / PEERS_FILE

    def grants_of(self, hid: str) -> tuple:
        rec = self.member(hid) or {}
        got = rec.get("grants")
        return tuple(g for g in got if g in GRANTS) if isinstance(got, list) else DEFAULT_GRANTS


# ---- serve.json ---------------------------------------------------------------------------------

def write_info(home, info: dict) -> None:
    from halo_harness.privateio import write_private_atomic
    host_dir(home).mkdir(parents=True, exist_ok=True)
    write_private_atomic(host_dir(home) / SERVE_FILE, json.dumps(info, indent=2))


def read_info(home=None, *, check_pid: bool = True) -> Optional[dict]:
    path = host_dir(home if home is not None else identity.home()) / SERVE_FILE
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(info, dict) or not isinstance(info.get("port"), int):
        return None
    if check_pid:
        from halo_harness.bg_run import pid_alive
        if info.get("pid") != os.getpid() and not pid_alive(info.get("pid")):
            return None
    return info


def drop_info(home, pid: int, port_: int) -> None:
    info = read_info(home, check_pid=False)
    if info and info.get("pid") == pid and info.get("port") == port_:
        try:
            (host_dir(home) / SERVE_FILE).unlink()
        except OSError:
            pass


def stop_path(home) -> Path:
    return host_dir(home) / STOP_FILE


def request_stop(home) -> None:
    host_dir(home).mkdir(parents=True, exist_ok=True)
    stop_path(home).write_text(str(time.time()), encoding="utf-8")


def clear_stop(home) -> None:
    try:
        stop_path(home).unlink()
    except OSError:
        pass


# ---- the audit ----------------------------------------------------------------------------------

def audit(home, peer: str, path: str, ok: bool, ms: float, *, now: Optional[float] = None,
          extra: Optional[dict] = None) -> None:
    """One line per request: {at, peer, path, ok, ms}; 3.3.7.0 R2: an acting request's line adds `extra` {op, params,
    evidence, dry, landed, fix, change_id, job}. The file is cut to its newer half past AUDIT_KEEP_BYTES."""
    p = host_dir(home) / AUDIT_FILE
    row = {"at": round(time.time() if now is None else now, 3), "peer": peer or "", "path": path.split("?", 1)[0],
           "ok": bool(ok), "ms": round(float(ms), 1), **{k: v for k, v in (extra or {}).items() if v is not None}}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        from halo_harness.filelock import file_lock
        with file_lock(p, timeout=1.0):
            if p.exists() and p.stat().st_size > AUDIT_KEEP_BYTES:
                data = p.read_bytes()
                p.write_bytes(data[len(data) // 2:].split(b"\n", 1)[-1])
            with open(p, "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(row) + "\n")
    except OSError:
        pass


def read_audit(home, *, limit: int = 200) -> list:
    try:
        lines = (host_dir(home) / AUDIT_FILE).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out = []
    for raw in lines[-limit:]:
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def audit_summary(home) -> dict:
    """{count, last: {at, peer, path, ok, ms} | None} over the kept audit (a line count, then the last line read)."""
    try:
        data = (host_dir(home) / AUDIT_FILE).read_bytes()
    except OSError:
        return {"count": 0, "last": None}
    rows = data.rstrip(b"\n").rsplit(b"\n", 1)
    try:
        last = json.loads(rows[-1].decode("utf-8", "replace")) if rows and rows[-1] else None
    except ValueError:
        last = None
    return {"count": data.count(b"\n"), "last": last if isinstance(last, dict) else None}


# ---- what it watches ----------------------------------------------------------------------------

def served_hosts() -> list:
    """The Ollama hosts this machine serves (ollama.hosts, or the synthesized default), as OllamaHost."""
    try:
        from halo_harness.fleet.ollama_share import served_here
        from halo_harness.providers.ollama import resolve_ollama_hosts
        return [h for h in resolve_ollama_hosts() if served_here(h.url)]
    except Exception:
        return []


def port_of(url: str) -> int:
    import urllib.parse
    try:
        return urllib.parse.urlparse(str(url or "")).port or 11434
    except ValueError:
        return 11434


def served_rows(addr: str, hosts=None) -> list:
    """[{name, port, addr}] for the join reply and the announce: what a peer matches its own host entries by."""
    return [{"name": h.name, "port": port_of(h.url), "addr": addr} for h in (served_hosts() if hosts is None else hosts)]
