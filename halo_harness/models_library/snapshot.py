"""halo_harness.models_library.snapshot -- Halo 3.3.5.0 R2: the shipped Ollama catalog (snapshot_ollama.json).

The top of ollama.com/library by pulls, with each model's tags (size, context, input) and, for the tags a size chip
names, the registry manifest's bytes and the config blob's family, parameters and quantization; taken by
`python tools/library_snapshot.py` (dated in the file). It is the offline fallback, the first paint, and what
the live catalog borrows sizes from until a model's tags are read.

    load() -> {taken, taken_at, source, models}
    taken() -> "2026-10-28"; taken_at() -> epoch seconds
    models() -> [entry + {tags, manifests}]; entry_of(name); tags_of(name) -> [tag]; manifest_of(name, tag)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

FILE = Path(__file__).resolve().parent / "snapshot_ollama.json"
_MEMO: dict = {}


def load() -> dict:
    if "data" not in _MEMO:
        try:
            data = json.loads(FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("models", [])
        _MEMO["data"] = data
        _MEMO["by"] = {m.get("name"): m for m in data["models"] if isinstance(m, dict)}
    return _MEMO["data"]


def taken() -> str:
    return str(load().get("taken") or "unknown date")


def taken_at() -> Optional[float]:
    at = load().get("taken_at")
    return float(at) if isinstance(at, (int, float)) else None


def models() -> list:
    return list(load()["models"])


def entry_of(name: str) -> Optional[dict]:
    load()
    return _MEMO["by"].get(str(name or "").split(":", 1)[0])


def tags_of(name: str) -> list:
    e = entry_of(name)
    return list((e or {}).get("tags") or [])


def manifest_of(name: str, tag: str) -> Optional[dict]:
    e = entry_of(name) or {}
    got = (e.get("manifests") or {}).get(str(tag or ""))
    return dict(got) if isinstance(got, dict) else None
