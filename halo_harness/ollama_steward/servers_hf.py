"""halo_harness.ollama_steward.servers_hf -- Halo 3.3.8.0 R2: the local servers the steward reads beside the Ollama
hosts (llama-server, LM Studio, mlx_lm.server; 3.3.9.0 R1: Halo's speech servers `stt` / `tts`, runtime voice-stt /
voice-tts; 3.3.9.1: FreeToken, runtime freetoken; 3.3.9.2: Strata, runtime strata), one vocabulary for all of them.

A **server** is one of:

- a `huggingface.local_servers` entry (`source: "manual"`, its `name`; `log` and `runtime` on the entry when set),
- a server Halo started (`halo local serve`, `source: "halo"`, its registry id such as `llama-8080`: the registry row
  of `<state>/run/local-servers.json` names its log, `<state>/local/servers/<id>.log`, and the command Halo ran),
- one the loopback probe found (`source: "auto"`, `auto:<port>`; read from the probe's cache when its sweep is under
  AUTO_S old, never probed here).

    Server(name, url, runtime, source, log, launch, model, id, pid)
    roster(state_dir=None) -> [Server]        manual first, then Halo's, then the probe's (one row per url)
    by_name(name, state_dir=None) / for_url(url, state_dir=None) -> Server | None
    name_for_url(url, state_dir=None) -> the server's name for a ledger line's url, or None
    runtime_word(raw) -> "llama-server" | "lmstudio" | "mlx" | "voice-stt" | "voice-tts" | "freetoken" | "strata" | None
    is_local(server) -> its url is this machine's

The roster is cached for CACHE_S and read again when the registry or config.json changed (a ledger rollup asks it
per line). Nothing here sends a request.
"""

from __future__ import annotations

import os
import time
import urllib.parse
from dataclasses import dataclass
from typing import Optional

CACHE_S = 1.0
AUTO_S = 300.0
LMSTUDIO_PORT = 1234
RUNTIMES = ("llama-server", "lmstudio", "mlx", "voice-stt", "voice-tts", "freetoken", "strata")  # 3.3.9.1; 3.3.9.2
_CACHE: dict = {}


@dataclass(frozen=True)
class Server:
    name: str
    url: str
    runtime: Optional[str] = None
    source: str = "manual"
    log: Optional[str] = None
    launch: Optional[str] = None
    model: Optional[str] = None
    id: Optional[str] = None
    pid: Optional[int] = None


def runtime_word(raw) -> Optional[str]:
    r = str(raw or "").strip().lower().replace("_", "-").replace(" ", "")
    if r in ("llama-server", "llama", "llama.cpp", "llamacpp", "llama-cpp"):
        return "llama-server"
    if r in ("lmstudio", "lm-studio"):
        return "lmstudio"
    if r in ("mlx", "mlx-lm", "mlx-lm.server", "mlxlm"):
        return "mlx"
    return r if r in ("voice-stt", "voice-tts", "freetoken", "strata") else None


def base(url) -> str:
    u = str(url or "").rstrip("/")
    return u[:-3] if u.endswith("/v1") else u


def port_of(url) -> Optional[int]:
    try:
        p = urllib.parse.urlparse(base(url))
        return p.port or (443 if p.scheme == "https" else 80)
    except ValueError:
        return None


def _hostname(url) -> str:
    try:
        return (urllib.parse.urlparse(base(url)).hostname or "").lower()
    except ValueError:
        return ""


def _same(a, b) -> bool:
    if base(a) == base(b):
        return True
    loop = ("127.0.0.1", "localhost", "::1")
    return _hostname(a) in loop and _hostname(b) in loop and port_of(a) == port_of(b)


def is_local(server) -> bool:
    try:
        from halo_harness.fleet.ollama_share import served_here
        return bool(served_here(base(getattr(server, "url", server))))
    except Exception:
        return _hostname(getattr(server, "url", server)) in ("127.0.0.1", "localhost", "::1")


def _state(state_dir):
    if state_dir is not None:
        return state_dir
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def _manual() -> list:
    try:
        from halo_harness.providers.huggingface import resolve_huggingface_local_servers
        entries = resolve_huggingface_local_servers()
    except Exception:
        return []
    out = []
    for e in entries:
        rt = runtime_word(getattr(e, "runtime", None))
        if rt is None and port_of(e.url) == LMSTUDIO_PORT:
            rt = "lmstudio"
        out.append(Server(name=e.name, url=base(e.url), runtime=rt, source="manual",
                          log=os.path.expanduser(e.log) if getattr(e, "log", None) else None))
    return out


def _registry(state_dir) -> list:
    try:
        from halo_harness.providers.local_runtime import load_registry
        rows = load_registry(state_dir)
    except Exception:
        return []
    if any(e.get("kind") == "strata" and not e.get("settled") for e in rows):  # 3.3.9.2: what `strata launch` said
        try:
            from halo_harness.strata.control import settle
            settle(state_dir, rows)
        except Exception:
            pass
    out = []
    for e in rows:
        port = e.get("port")
        if not isinstance(port, int):
            continue
        rt = runtime_word(e.get("kind") or e.get("runtime"))
        cmd = e.get("cmdline")
        out.append(Server(name=str(e.get("id") or f"{'mlx' if rt == 'mlx' else 'llama'}-{port}"),
                          url=f"http://127.0.0.1:{port}", runtime=rt, source="halo", log=e.get("log") or None,
                          launch=" ".join(str(x) for x in cmd) if isinstance(cmd, list) and cmd else None,
                          model=e.get("model"), id=e.get("id"), pid=e.get("pid") if isinstance(e.get("pid"), int) else None))
    return out


def _auto() -> list:
    try:
        from halo_harness.providers import huggingface_local_probe as P
        hit = P._auto_detect_cache  # (monotonic ts, ports, results): a sweep older than AUTO_S says nothing now
        found = list(hit[2]) if hit and time.monotonic() - hit[0] < AUTO_S else []
    except Exception:
        return []
    out = []
    for d in found:
        port = port_of(d.base_url)
        rt = "lmstudio" if port == LMSTUDIO_PORT else runtime_word(getattr(d, "runtime_label", None))
        out.append(Server(name=f"auto:{port}", url=base(d.base_url), runtime=rt, source="auto",
                          model=(d.model_ids or (None,))[0]))
    return out


def _mtime(path) -> int:
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return 0


def roster(state_dir=None) -> list:
    """Every local server, one row per url: a manual entry keeps its name and takes the log and the launch command
    of the server Halo started on the same port."""
    sd = _state(state_dir)
    key = str(sd)
    hit = _CACHE.get(key)
    now = time.monotonic()
    if hit and now - hit[0] < CACHE_S:
        return hit[2]
    from halo_harness.providers.local_runtime import registry_path
    from halo_harness.providers import huggingface_local_probe as P
    sweep = P._auto_detect_cache[0] if P._auto_detect_cache else None  # a new sweep is a new roster too
    stamp = (_mtime(registry_path(sd)), _mtime(os.path.join(str(sd), "config.json")), sweep)
    if hit and hit[1] == stamp:
        _CACHE[key] = (now, stamp, hit[2])
        return hit[2]
    out: list = []
    halo = _registry(sd)
    for m in _manual():
        twin = next((h for h in halo if _same(h.url, m.url)), None)
        if twin is not None:
            m = Server(name=m.name, url=m.url, runtime=m.runtime or twin.runtime, source="manual",
                       log=m.log or twin.log, launch=twin.launch, model=twin.model, id=twin.id, pid=twin.pid)
        out.append(m)
    for s in halo + _auto():
        if not any(_same(s.url, x.url) for x in out):
            out.append(s)
    _CACHE[key] = (now, stamp, out)
    return out


def by_name(name, state_dir=None) -> Optional[Server]:
    want = str(name or "").strip().lower()
    return next((s for s in roster(state_dir) if want and s.name.lower() == want), None)


def for_url(url, state_dir=None) -> Optional[Server]:
    return next((s for s in roster(state_dir) if url and _same(s.url, url)), None)


def name_for_url(url, state_dir=None) -> Optional[str]:
    """The server's name for a ledger line's url; a loopback OpenAI-dialect url no roster row names is `auto:<port>`."""
    if not url:
        return None
    s = for_url(url, state_dir)
    if s is not None:
        return s.name
    u = str(url or "").rstrip("/")
    if u.endswith("/v1") and _hostname(u) in ("127.0.0.1", "localhost", "::1") and port_of(u) not in (None, 11434):
        return f"auto:{port_of(u)}"
    return None


def reset() -> None:
    _CACHE.clear()
