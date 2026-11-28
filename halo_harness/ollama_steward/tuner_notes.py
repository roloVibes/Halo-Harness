"""halo_harness.ollama_steward.tuner_notes -- Halo 3.6.0.25 T: what a tuner model wrote about one local model, kept
apart from what Halo measured (`<state>/models/notes.json`, beside `models/best-at.json`, which is rebuilt and never
holds a text).

    put(state_dir, host, model, kind, value, *, by, digest) -> the kept note   kind: diagnosis | advice | guide
    read(state_dir, host, model, *, digest=None) -> {kind: note}   a note from another build of the tag is marked
                                                                   `older_build`, never dropped
    remove(state_dir, host, model, kind) -> bool
    advice(settings, *, trained, os_name) -> (kept, dropped)       the allow-list: only these server settings, each
                                                                   with its reason and its set / revert lines (never run)

Each note is {kind, by: "<model ref>", at, digest, ...}: shown as "written by <model>", never as Halo's measurement.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

KINDS = ("diagnosis", "advice", "guide")
_KEEP = re.compile(r"^(-1|0|\d{1,4}[smh])$")
_ORIGINS = re.compile(r"^[A-Za-z0-9:/*.,_-]{1,200}$")


def _allowed(key: str, value: str, trained: Optional[int]) -> bool:
    if key == "OLLAMA_KV_CACHE_TYPE":
        return value in ("f16", "q8_0", "q4_0")
    if key == "OLLAMA_FLASH_ATTENTION":
        return value in ("0", "1")
    if key in ("OLLAMA_NUM_PARALLEL", "OLLAMA_MAX_LOADED_MODELS"):
        return value.isdigit() and 1 <= int(value) <= 8
    if key == "OLLAMA_CONTEXT_LENGTH":
        return value.isdigit() and 2048 <= int(value) <= (trained or 1 << 20)
    if key == "OLLAMA_KEEP_ALIVE":
        return bool(_KEEP.match(value))
    if key == "OLLAMA_ORIGINS":
        return bool(_ORIGINS.match(value))
    return False


# The server settings a tuner may advise: the ones Halo's own advice knows (tune_options: the KV cache type, flash
# attention, the parallel count) plus the number of loaded models, a default window, keep-alive and origins.
ALLOWED = ("OLLAMA_KV_CACHE_TYPE", "OLLAMA_FLASH_ATTENTION", "OLLAMA_NUM_PARALLEL", "OLLAMA_MAX_LOADED_MODELS",
           "OLLAMA_CONTEXT_LENGTH", "OLLAMA_KEEP_ALIVE", "OLLAMA_ORIGINS")


def advice(settings, *, trained: Optional[int] = None, os_name: Optional[str] = None) -> "tuple[list, int]":
    from halo_harness.ollama_steward.tune_lines import server_block
    kept, dropped = [], 0
    for s in settings if isinstance(settings, list) else []:
        key = str((s or {}).get("key") or "").strip().upper() if isinstance(s, dict) else ""
        value = str((s or {}).get("value") if isinstance(s, dict) else "").strip()
        why = str((s or {}).get("why") or "").strip()[:300] if isinstance(s, dict) else ""
        if key not in ALLOWED or not _allowed(key, value, trained) or not why:
            dropped += 1
            continue
        kept.append({"key": key, "value": value, "why": why, "server": server_block("env", key, value, os_name)})
    return kept, dropped


def _path(state_dir) -> Path:
    return Path(state_dir) / "models" / "notes.json"


def _all(state_dir) -> dict:
    try:
        data = json.loads(_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _key(host: str, model: str) -> str:
    from halo_harness.providers.ollama import normalize_ollama_model_name
    return f"{host}|{normalize_ollama_model_name(model)}"


def _write(state_dir, data: dict) -> None:
    p = _path(state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)


def put(state_dir, host: str, model: str, kind: str, value: dict, *, by: str, digest: Optional[str]) -> dict:
    from halo_harness.filelock import file_lock
    note = {**value, "kind": kind, "by": by, "at": time.time(), "digest": digest}
    with file_lock(_path(state_dir)):
        data = _all(state_dir)
        data.setdefault(_key(host, model), {})[kind] = note
        _write(state_dir, data)
    return note


def read(state_dir, host: str, model: str, *, digest: Optional[str] = None) -> dict:
    got = _all(state_dir).get(_key(host, model)) or {}
    out = {}
    for kind, note in got.items():
        if kind in KINDS and isinstance(note, dict):
            out[kind] = {**note, "older_build": bool(digest and note.get("digest") and note["digest"] != digest)}
    return out


def remove(state_dir, host: str, model: str, kind: str) -> bool:
    from halo_harness.filelock import file_lock
    with file_lock(_path(state_dir)):
        data = _all(state_dir)
        mine = data.get(_key(host, model)) or {}
        if kind not in mine:
            return False
        mine.pop(kind)
        if not mine:
            data.pop(_key(host, model), None)
        _write(state_dir, data)
    return True


def by_line(note: dict) -> str:
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(note["at"])) if isinstance(note.get("at"), (int, float)) else "?"
    return f"written by {note.get('by') or '?'}, {when}" + (" (about an older build of this tag)" if note.get("older_build") else "")
