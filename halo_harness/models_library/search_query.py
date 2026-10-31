"""halo_harness.models_library.search_query -- Halo 3.3.6.0 R2: the search as browse.library runs it, and the
resource strip the page pins above it (F6).

    run(state_dir, views, spec, *, host, window, host_card, intent) -> (rows, info)
        spec = {preset, for_role, sentence, needs, fit, supply, role, exclude_crashed}; no criteria: every row gets
        its facts, chips, cost and verdicts and keeps its order (the plain Library)
    strip(host, host_card, *, window) -> {host, gpu, usable, free, resident [{model, bytes}], disk_free, disk_from,
        window, line}
    DISK_SEAM: {"free": fn(host) -> (bytes | None, from)} (the tests' seam)

The disk is read only for a host this machine serves (its Ollama models folder: OLLAMA_MODELS, else ~/.ollama/models);
another host's disk is not read ("on that machine").
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

DISK_SEAM: dict = {}


def _criteria(spec: dict) -> bool:
    return any(spec.get(k) for k in ("preset", "for_role", "sentence", "needs", "fit", "supply", "role", "exclude_crashed",
                                     "replace"))


def run(state_dir, views: list, spec: Optional[dict], *, host: str, window: int, host_card: Optional[dict],
        intent: str = "") -> "tuple[list, dict]":
    from halo_harness.models_library.presets import resolve
    from halo_harness.models_library.search import search
    spec = dict(spec or {})
    if not _criteria(spec):
        rows = search(views, host=host, window=window, host_card=host_card, state_dir=state_dir, intent=intent,
                      keep_order=not intent)  # the plain Library keeps the listing's order
        return rows, {"preset": "", "bundle": None, "role": "", "understood": []}
    got = resolve(spec)
    b = got["bundle"]
    rows = search(views, host=host, window=window, needs=b["needs"], fit=b["fit"], supply=b["supply"],
                  intent=intent or b.get("intent") or "", role=got["role"], host_card=host_card, state_dir=state_dir,
                  exclude_crashed=bool(spec.get("exclude_crashed")))
    return rows, {"preset": b.get("id") or "", "bundle": b, "role": got["role"], "understood": got["understood"],
                  "for_role": spec.get("for_role") or "", "sentence": spec.get("sentence") or ""}


def _models_dir() -> Path:
    from halo_harness.config.paths import home
    env = os.environ.get("OLLAMA_MODELS")
    return Path(env) if env else home() / ".ollama" / "models"


def disk_free(host) -> "tuple[Optional[int], str]":
    if "free" in DISK_SEAM:
        return DISK_SEAM["free"](host)
    try:
        from halo_harness.fleet.ollama_share import served_here
        if host is None or not served_here(host.url):
            return None, "on that machine (its disk is not read from here)"
        import shutil
        d = _models_dir()
        probe = d if d.exists() else next((p for p in d.parents if p.exists()), d.anchor and Path(d.anchor) or d)
        return int(shutil.disk_usage(str(probe)).free), f"the disk of {probe}"
    except Exception as e:
        return None, f"not read ({type(e).__name__})"


def strip(host, host_card: Optional[dict], *, window: int) -> dict:
    name = getattr(host, "name", None)
    if not host_card:
        return {"host": name, "card": False, "window": window, "line": f"no hardware card read for {name or 'this host'} yet"}
    from halo_harness.ollama_steward.fit import card_budget
    b = card_budget(host_card, name or "")
    gpus = [g for g in host_card.get("gpus") or [] if isinstance(g, dict)]
    loaded = [x for x in host_card.get("loaded") or [] if isinstance(x, dict) and x.get("model")]
    held = sum(int(x.get("size_vram") or x.get("size") or 0) for x in loaded)
    free = max(0, b["budget"] - held)
    disk, disk_from = disk_free(host)
    gib = lambda n: f"{n / 2 ** 30:.1f} GB"  # noqa: E731
    res = ", ".join(x["model"] for x in loaded) or "nothing"
    return {"host": name, "card": True, "gpu": " + ".join(str(g.get("name") or "a GPU") for g in gpus) or "no GPU",
            "usable": b["budget"], "free": free, "others": b["others"], "kv": b["kv"],
            "resident": [{"model": x["model"], "bytes": int(x.get("size_vram") or x.get("size") or 0)} for x in loaded],
            "disk_free": disk, "disk_from": disk_from, "window": window,
            "version": (host_card.get("server") or {}).get("version"),
            "line": f"{name}: {gib(b['budget'])} usable, {gib(free)} free at {window:,} · resident: {res}"}
