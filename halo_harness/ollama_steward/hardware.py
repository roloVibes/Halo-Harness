"""halo_harness.ollama_steward.hardware -- Halo 3.3.4.0 R1: the hardware
card of one Ollama host, read without touching the server's settings or
its models.

    hardware_card(host) -> {gpus: [{id, name, library, total_bytes,
        available_bytes}], unified, ram_bytes, server: {version, max_loaded,
        parallel, keep_alive, kv_cache_type, flash_attention, gpu_overhead,
        source}, loaded: [{model, size, size_vram, expires}],
        other_users: [{name, bytes}], read_at, sources: [...]}

Every field is None when unknown. The readers run in this order, each one
optional (`hardware_readers.py`): (a) the local server log's newest
startup block, (b) `/api/version` and `/api/ps`, (c) the ssh GPU read of a
remote host with `ssh:`, (d) `nvidia-smi` / `system_profiler` where local.
A fact the first reader gives stays; a later reader fills what is still
None, except a live GPU reading ((c) or (d)), whose free memory replaces
the startup log's (the log's figure is from when the server started).
`format_card` turns the card into the lines `halo ollama hardware` prints.
"""

from __future__ import annotations

import datetime as _dt
from typing import Callable, Optional

from halo_harness.ollama_steward import hardware_readers as hr
from halo_harness.ollama_steward import hardware_sources as hs

_SERVER_KEYS = ("version", "max_loaded", "parallel", "keep_alive", "kv_cache_type", "flash_attention",
                "gpu_overhead", "source")


def _empty_card() -> dict:
    return {"gpus": None, "unified": None, "ram_bytes": None,
            "server": {k: None for k in _SERVER_KEYS}, "loaded": None, "other_users": None,
            "read_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"), "sources": []}


def _note(card: dict, reader: str, ok: bool, detail: str) -> None:
    card["sources"].append({"reader": reader, "ok": ok, "detail": detail})


def _merge_gpus(card: dict, gpus: "list[dict]", *, live: bool) -> None:
    if not gpus:
        return
    if not card["gpus"]:
        card["gpus"] = [dict(g) for g in gpus]
        return
    for i, new in enumerate(gpus):
        if i >= len(card["gpus"]):
            break
        old = card["gpus"][i]
        for key, value in new.items():
            if old.get(key) is None or (live and key == "available_bytes" and value is not None):
                old[key] = value


def _apply_log(card: dict, startup: dict) -> None:
    gpus = [d for d in startup["devices"] if (d.get("library") or "").lower() != "cpu"]
    for d in gpus:
        d.pop("type", None)
    _merge_gpus(card, gpus, live=False)
    if startup["devices"]:
        card["unified"] = any((d.get("library") or "") == "Metal" for d in startup["devices"]) if gpus else False
    cpu = [d for d in startup["devices"] if (d.get("library") or "").lower() == "cpu"]
    card["ram_bytes"] = startup.get("system_total") or (cpu[0]["total_bytes"] if cpu else None)
    settings = hs.server_settings(startup["env"], startup.get("launch"), len(gpus))
    server = card["server"]
    server.update({k: v for k, v in settings.items() if k not in ("context_length",)})
    server["version"] = startup.get("version")
    server["source"] = "server.log"


def _apply_live(card: dict, found: dict) -> None:
    _merge_gpus(card, found.get("gpus") or [], live=True)
    if found.get("unified") is not None:
        card["unified"] = found["unified"]
    elif card["unified"] is None and found.get("gpus"):
        card["unified"] = False
    if card["ram_bytes"] is None and found.get("ram_bytes"):
        card["ram_bytes"] = found["ram_bytes"]
    apps = found.get("apps")
    if apps is not None:
        card["other_users"] = hs.other_users(apps)


def _unattributed(card: dict) -> None:
    """When the driver gives no per-process numbers (Windows WDDM), what the
    card holds beyond Ollama's own loaded models is still known."""
    users, gpus, loaded = card["other_users"], card["gpus"] or [], card["loaded"]
    if users is None or any(u["bytes"] is not None for u in users) or not gpus or loaded is None:
        return
    total = sum(g["total_bytes"] or 0 for g in gpus)
    free = sum(g["available_bytes"] or 0 for g in gpus)
    ollama = sum(m["size_vram"] or 0 for m in loaded if isinstance(m.get("size_vram"), int))
    rest = total - free - ollama
    if all(g.get("total_bytes") and g.get("available_bytes") is not None for g in gpus) and rest > 0:
        users.append({"name": "not Ollama (in use minus Ollama's models)", "bytes": rest})


def hardware_card(host=None, *, log_path=None, api: Optional[Callable] = None, runner: Optional[Callable] = None,
                  ssh_runner: Optional[Callable] = None, platform: Optional[str] = None) -> dict:
    """The card for `host` (an `OllamaHost`; None = the default host).
    `log_path`, `api`, `runner` and `ssh_runner` are the seams tests use."""
    from halo_harness.providers.ollama_hw import is_local_host
    if host is None:
        from halo_harness.providers.ollama import resolve_ollama_host
        host = resolve_ollama_host(None)
    card = _empty_card()
    local = host is not None and is_local_host(host)
    if local or log_path is not None:
        startup, why = hr.read_server_log(path=log_path, platform=platform, runner=runner)
        if startup is not None:
            _apply_log(card, startup)
            _note(card, "server.log", True, startup["where"])
        else:
            _note(card, "server.log", False, why)
    else:
        _note(card, "server.log", False, "the host is not this machine")
    if host is not None:
        found, why = hr.read_api(host, api=api)
        if found is not None:
            if found.get("version"):
                card["server"]["version"] = found["version"]
                card["server"]["source"] = card["server"]["source"] or "/api/version"
            card["loaded"] = found.get("loaded")
            _note(card, "/api/version and /api/ps", True, getattr(host, "url", ""))
        else:
            _note(card, "/api/version and /api/ps", False, why)
    if host is not None and not local:
        found, why = hr.read_remote_gpus(host, ssh_runner=ssh_runner)
        reader = "ssh GPU read"
    else:
        found, why = hr.read_local_gpus(runner=runner, platform=platform)
        reader = "nvidia-smi / system_profiler"
    if found is not None:
        _apply_live(card, found)
        _note(card, reader, True, "live")
    else:
        _note(card, reader, False, why)
    _unattributed(card)
    return card


def _gib(n) -> str:
    return f"{n / 2 ** 30:.1f} GiB" if isinstance(n, (int, float)) else "?"


def format_card(card: dict, *, host_name: str = "") -> "list[str]":
    """The card as plain lines (`halo ollama hardware`)."""
    lines = [f"Hardware of '{host_name}' (read {card['read_at']}):"] if host_name else []
    for g in card["gpus"] or []:
        est = " (estimated)" if g.get("estimated") else ""
        free = f", {_gib(g['available_bytes'])} free{est}" if g.get("available_bytes") is not None else ""
        lib = f" [{g['library']}]" if g.get("library") else ""
        lines.append(f"GPU {g.get('id') or 0}: {g.get('name') or 'unnamed'}{lib} {_gib(g.get('total_bytes'))}{free}")
    if card["unified"]:
        lines.append("memory: unified (the GPU shares the system RAM)")
    if card["ram_bytes"]:
        lines.append(f"system RAM: {_gib(card['ram_bytes'])}")
    s = card["server"]
    if any(s.get(k) is not None for k in _SERVER_KEYS if k != "source"):
        parts = []
        if s.get("max_loaded") is not None:
            parts.append(f"keeps {s['max_loaded']} model{'s' if s['max_loaded'] != 1 else ''}"
                         + (" (automatic)" if s.get("max_loaded_auto") else ""))
        for key, label in (("parallel", "parallel"), ("keep_alive", "keep-alive"), ("kv_cache_type", "KV cache"),
                           ("flash_attention", "flash attention")):
            if s.get(key) is not None:
                parts.append(f"{label} {s[key]}")
        if s.get("gpu_overhead"):
            parts.append(f"GPU overhead {_gib(s['gpu_overhead'])}")
        lines.append(f"server {s.get('version') or '?'}: " + (", ".join(parts) or "settings not read"))
    if card["loaded"] is not None:
        rows = []
        for m in card["loaded"]:
            size, vram = m.get("size"), m.get("size_vram")
            where = ("all on the GPU" if isinstance(size, int) and vram == size
                     else f"{_gib(size - vram)} on the CPU" if isinstance(size, int) and isinstance(vram, int) else "")
            rows.append(f"{m.get('model')} {_gib(size)} {where}".rstrip())
        lines.append("loaded: " + ("; ".join(rows) or "nothing"))
    if card["other_users"]:
        lines.append("other: " + "; ".join(f"{u['name']}" + (f" {_gib(u['bytes'])}" if u["bytes"] else "")
                                           for u in card["other_users"]))
    for src in card["sources"]:
        if not src["ok"]:
            lines.append(f"not read: {src['reader']} ({src['detail']})")
    return lines
