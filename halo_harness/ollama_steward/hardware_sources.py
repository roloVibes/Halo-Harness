"""halo_harness.ollama_steward.hardware_sources -- Halo 3.3.4.0 R1: the
parsers behind the hardware card. Text in, plain values out, no I/O (the
readers in `hardware_readers.py` fetch the text). Every format here is
the one the steward's knowledge cites: the server log's startup lines
(`knowledge/log-vocabulary.md`), `nvidia-smi --format=csv,noheader,
nounits`, `system_profiler SPDisplaysDataType` and `/api/ps`. Anything
that does not parse is None, never a guess.
"""

from __future__ import annotations

import re
from typing import Optional

_UNITS = {"B": 1, "KiB": 2 ** 10, "MiB": 2 ** 20, "GiB": 2 ** 30, "TiB": 2 ** 40,
          "KB": 10 ** 3, "MB": 10 ** 6, "GB": 10 ** 9, "TB": 10 ** 12}
_SIZE_RE = re.compile(r"^\s*([\d.]+)\s*([KMGT]i?B|B)\s*$")
_FIELD_RE = re.compile(r'([A-Za-z_][\w.]*)=("(?:[^"\\]|\\.)*"|\S+)')
_ENV_RE = re.compile(r"(?:^|(?<=\s))([A-Za-z_][A-Za-z0-9_]*):(\[[^\]]*\]|\S*)")
_OWN_PROCESSES = ("ollama", "llama-server")


def parse_size(text) -> Optional[int]:
    """"22.5 GiB" / "457.0 MiB" / "0 B" (Ollama's HumanBytes2) -> bytes."""
    m = _SIZE_RE.match(str(text or ""))
    if not m:
        return None
    try:
        return int(float(m.group(1)) * _UNITS[m.group(2)])
    except (KeyError, ValueError):
        return None


def slog_fields(line: str) -> dict:
    """The `key=value` / `key="quoted value"` pairs of one Go slog line."""
    out = {}
    for key, value in _FIELD_RE.findall(line or ""):
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            value = re.sub(r"\\(.)", r"\1", value[1:-1])
        out[key] = value
    return out


def parse_env_map(value: str) -> dict:
    """`map[NAME:value NAME2: ...]` (the "server config" line) -> {NAME:
    value}; an empty value stays "" (unset, the default applies)."""
    text = (value or "").strip()
    if text.startswith("map[") and text.endswith("]"):
        text = text[4:-1]
    return {k: v for k, v in _ENV_RE.findall(text)}


def parse_launch(cmd: str) -> dict:
    """The options of a "starting llama-server" command line that the card
    reports: the window, the slots, the cache type, flash attention and
    `-ngl` when Ollama passed it."""
    tokens = (cmd or "").split()
    flags = {"-c": "ctx", "-np": "parallel", "--cache-type-k": "cache_type", "--flash-attn": "flash_attention",
             "-ngl": "gpu_layers"}
    out = {}
    for i, tok in enumerate(tokens[:-1]):
        if tok in flags:
            out[flags[tok]] = tokens[i + 1]
    return out


def newest_startup(lines: "list[str]") -> "list[str]":
    """The lines of the newest server start: from the last "server config"
    line to the end ([] when the log has no startup block)."""
    for i in range(len(lines) - 1, -1, -1):
        if 'msg="server config"' in lines[i]:
            return lines[i:]
    return []


def parse_startup(text: str) -> Optional[dict]:
    """The newest startup block of a server log -> {env, version, devices,
    system_total, launch}; None when there is no startup block."""
    block = newest_startup((text or "").splitlines())
    if not block:
        return None
    out = {"env": {}, "version": None, "devices": [], "system_total": None, "launch": {}}
    for line in block:
        if 'msg="server config"' in line:
            out["env"] = parse_env_map(slog_fields(line).get("env", ""))
        elif 'msg="Listening on' in line:
            m = re.search(r"\(version ([^)\s]+)\)", line)
            out["version"] = m.group(1) if m else None
        elif 'msg="inference compute"' in line:
            f = slog_fields(line)
            out["devices"].append({"id": f.get("id"), "name": f.get("description") or f.get("name"),
                                   "library": f.get("library"), "type": f.get("type"),
                                   "total_bytes": parse_size(f.get("total")),
                                   "available_bytes": parse_size(f.get("available"))})
        elif 'msg="system memory"' in line:
            out["system_total"] = parse_size(slog_fields(line).get("total"))
        elif 'msg="starting llama-server"' in line:
            out["launch"] = parse_launch(slog_fields(line).get("cmd", ""))
    return out


def _int(value) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def go_duration(value) -> Optional[str]:
    """Go's "5m0s" / "30m0s" / "1h0m0s" -> "5m" / "30m" / "1h"; a value of
    100,000 hours or more (a negative keep-alive) -> "forever"."""
    text = str(value or "").strip()
    if not text:
        return None
    hours = re.match(r"^(\d+)h", text)
    if hours and int(hours.group(1)) >= 100_000:
        return "forever"
    short = re.sub(r"(?<=[hm])0s$", "", text)
    short = re.sub(r"(?<=h)0m$", "", short)
    return short or text


def server_settings(env: dict, launch: dict, gpu_count: int) -> dict:
    """The card's `server` block from the env dump and the newest launch
    line: the launch line's cache type and flash attention are the real
    ones; the env dump prints `false` for flash attention both when it is
    unset (automatic) and when it is off."""
    env = env or {}
    launch = launch or {}
    loaded = _int(env.get("OLLAMA_MAX_LOADED_MODELS"))
    parallel = _int(env.get("OLLAMA_NUM_PARALLEL"))
    kv = None
    if "OLLAMA_KV_CACHE_TYPE" in env:
        kv = env["OLLAMA_KV_CACHE_TYPE"] or "f16"
    kv = launch.get("cache_type") or kv
    fa = launch.get("flash_attention")
    if fa is None and "OLLAMA_FLASH_ATTENTION" in env:
        fa = "on" if env["OLLAMA_FLASH_ATTENTION"].lower() in ("true", "1") else "auto or off"
    return {"max_loaded": (3 * max(gpu_count, 1) if loaded == 0 else loaded),
            "max_loaded_auto": (loaded == 0) if loaded is not None else None,
            "parallel": (max(parallel, 1) if parallel is not None else None),
            "keep_alive": go_duration(env.get("OLLAMA_KEEP_ALIVE")),
            "kv_cache_type": kv, "flash_attention": fa,
            "gpu_overhead": _int(env.get("OLLAMA_GPU_OVERHEAD")),
            "context_length": _int(env.get("OLLAMA_CONTEXT_LENGTH"))}


def parse_nvidia_gpus(text: str) -> "list[dict]":
    """`nvidia-smi --query-gpu=index,name,memory.total,memory.free
    --format=csv,noheader,nounits` (MiB) -> one dict per card."""
    cards = []
    for line in (text or "").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        total, free = _int(parts[2]), _int(parts[3])
        if total is None or free is None:
            continue
        cards.append({"id": parts[0], "name": parts[1] or None, "library": "CUDA",
                      "total_bytes": total * 2 ** 20, "available_bytes": free * 2 ** 20})
    return cards


def _process_name(raw: str) -> Optional[str]:
    raw = (raw or "").strip()
    if not raw or raw.startswith("["):
        return None
    base = re.split(r"[\\/]", raw)[-1]
    return re.sub(r"\.exe$", "", base, flags=re.IGNORECASE) or None


def parse_compute_apps(text: str) -> "list[dict]":
    """`nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory
    --format=csv,noheader,nounits` -> [{pid, name, bytes}]; `[N/A]` (every
    process under Windows WDDM) is bytes None, a hidden process name None."""
    apps = []
    for line in (text or "").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        mib = _int(parts[-1])
        apps.append({"pid": _int(parts[0]), "name": _process_name(",".join(parts[1:-1])),
                     "bytes": mib * 2 ** 20 if mib is not None else None})
    return apps


def other_users(apps: "list[dict]") -> "list[dict]":
    """Every GPU process that is not Ollama's own, grouped by name; bytes is
    the sum, or None when the driver does not say."""
    grouped: "dict[str, Optional[int]]" = {}
    for app in apps or []:
        name = app.get("name") or "a process this user cannot see"
        if any(own in name.lower() for own in _OWN_PROCESSES):
            continue
        b = app.get("bytes")
        if name not in grouped:
            grouped[name] = b
        elif grouped[name] is not None and b is not None:
            grouped[name] += b
        else:
            grouped[name] = None
    return [{"name": n, "bytes": b} for n, b in grouped.items()]


def parse_system_profiler(text: str) -> Optional[dict]:
    """`system_profiler SPDisplaysDataType` -> {name, cores} of the first
    GPU ("Chipset Model: Apple M3 Max", "Total Number of Cores: 40")."""
    m = re.search(r"Chipset Model:\s*(.+)", text or "")
    if not m:
        return None
    cores = re.search(r"Total Number of Cores:\s*(\d+)", text or "")
    return {"name": m.group(1).strip(), "cores": int(cores.group(1)) if cores else None}


def parse_ps(body) -> "list[dict]":
    """`/api/ps` -> [{model, size, size_vram, expires, context_length}]."""
    rows = []
    for e in ((body or {}).get("models") or []) if isinstance(body, dict) else []:
        if isinstance(e, dict):
            rows.append({"model": e.get("model") or e.get("name"), "size": e.get("size"),
                         "size_vram": e.get("size_vram"), "expires": e.get("expires_at"),
                         "context_length": e.get("context_length")})
    return rows
