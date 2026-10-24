"""halo_harness.models_best_at -- the "best at" cache (Halo 3.1.9.0 R1).

`<state>/models/best-at.json`:

    {"schema": 1, "built": <epoch s>,
     "sources": {"models.json": <mtime>, ..., "gym": [<newest mtime>, <files>]},
     "rows": {ref: {"kinds": [...], "line": "...", "scores": {kind: s},
                    "facts": {provider, prices, context, modalities, tools,
                              reasoning, open_weights, local, measured}}},
     "best": {kind: {"cheapest": ref | null, "strongest": ref}}}

`index(state_dir, rows)` answers the cache while it is fresh and rebuilds it
when any SOURCE cache's mtime moved (`SOURCE_NAMES`: every provider catalog
cache, models.dev, telemetry's stats cache, the gym results, the Ollama
probe, the canary census, the learned rules, config.json, routes.json; 3.1.8.0
R3: the measured outcome numbers a line shows, outcomes/measured.signature) or
once it is older than `MAX_AGE_S` (an Ollama host's catalog and the
provider env have no file to watch). No refresh path needs wiring: a
`halo models --refresh`, `/model` refresh or Studio Refresh rewrites a
source, and the next read rebuilds. `halo models analyze` rebuilds on
demand (models_analyze_cli.py). Source names, never absolute paths, are
stored, so the file carries no path and no secret.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Optional

SCHEMA = 1
MAX_AGE_S = 6 * 3600
FIRST_BUILD_WAIT_S = 4.0  # how long a session start waits for a first-ever build
SOURCE_NAMES = ("models.json", "models-dev.json", "dbx-endpoints.json", "experiential-models.json",
                "huggingface-models.json", "openai-models.json", "ant-models.json", "stats-cache.json",
                "ollama-capabilities.json", "canary-census.json", "learned-rules.json", "config.json", "routes.json")
FACT_KEYS = ("provider", "price_in_per_m", "price_out_per_m", "context_tokens", "max_output_tokens", "modalities_in",
             "modalities_out", "image_output", "tools", "reasoning", "open_weights", "local", "measured")


def cache_path(state_dir) -> Path:
    return Path(state_dir) / "models" / "best-at.json"


def source_mtimes(state_dir) -> dict:
    base = Path(state_dir)
    out: dict = {}
    for name in SOURCE_NAMES:
        try:
            out[name] = round((base / name).stat().st_mtime, 3)
        except OSError:
            continue
    from halo_harness.outcomes.measured import signature  # 3.1.8.0 R3: the measured words a line shows
    sig = signature(base)  # (outcomes.jsonl's rated numbers; a rebuild only when a shown number moves)
    if sig:
        out["outcomes.jsonl"] = sig
    gym = base / "gym"
    try:
        files = [p for p in gym.glob("*/*.json") if not p.name.endswith(".tmp")]
        if files:
            out["gym"] = [round(max(p.stat().st_mtime for p in files), 3), len(files)]
    except OSError:
        pass
    return out


def load(state_dir) -> Optional[dict]:
    try:
        data = json.loads(cache_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("schema") == SCHEMA and isinstance(data.get("rows"), dict) else None


def is_fresh(cache: Optional[dict], state_dir) -> bool:
    if not cache:
        return False
    built = cache.get("built")
    if not isinstance(built, (int, float)) or time.time() - built > MAX_AGE_S:
        return False
    return cache.get("sources") == source_mtimes(state_dir)


def invalidate(state_dir) -> bool:
    """Mark the cache stale (its `built` 0) so the next read rebuilds it -- a stale cache still answers a
    session start at once (3.1.9.0 R3: `halo outcomes forget`). False when there is no cache."""
    cache = load(state_dir)
    if cache is None:
        return False
    path = cache_path(state_dir)
    with _WRITE_LOCK:
        try:
            tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps(dict(cache, built=0), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, path)
        except OSError:
            return False
    return True


def entry_for(row: dict, preflight: Optional[dict] = None) -> dict:
    from halo_harness.capabilities_line import best_at_kinds, best_at_line, kind_scores
    scores = kind_scores(row, preflight)
    return {"kinds": best_at_kinds(row, scores=scores), "line": best_at_line(row, preflight, scores=scores),
            "scores": {k: s for k, (s, _r) in scores.items() if s > 0},
            "facts": {k: row.get(k) for k in FACT_KEYS}}


def best_per_kind(entries: dict) -> dict:
    """{kind: {"cheapest", "strongest"}} over the models good at each kind;
    the cheapest by the blended price (a model with no price never wins it)."""
    from halo_harness.capabilities import KINDS
    from halo_harness.capabilities_strengths import blended_price
    out: dict = {}
    for kind in KINDS:
        good = [(ref, e) for ref, e in entries.items() if kind in (e.get("kinds") or [])]
        if not good:
            continue
        strongest = min(good, key=lambda t: (-t[1]["scores"].get(kind, 0), t[0]))[0]
        priced = [(blended_price({**(e.get("facts") or {}), "ref": ref}), ref, e) for ref, e in good]
        priced = [t for t in priced if t[0] is not None]
        cheapest = min(priced, key=lambda t: (t[0], -t[2]["scores"].get(kind, 0), t[1]))[1] if priced else None
        out[kind] = {"cheapest": cheapest, "strongest": strongest}
    return out


_WRITE_LOCK = threading.Lock()


def rebuild(state_dir, rows: list) -> dict:
    entries = {}
    for row in rows:
        ref = row.get("ref")
        if ref and row.get("provider") != "alias" and ref not in entries:
            entries[ref] = entry_for(row)
    cache = {"schema": SCHEMA, "built": time.time(), "sources": source_mtimes(state_dir), "rows": entries,
             "best": best_per_kind(entries)}
    path = cache_path(state_dir)
    with _WRITE_LOCK:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, path)
        except OSError:
            pass
    return cache


def catalog_rows(state_dir) -> list:
    """The catalog the way `halo models` lists it (the session's env chain)."""
    from halo_harness.providers.config import listing_effective_env, load_routes
    from halo_harness.providers.model_enumeration import build_model_rows
    base = Path(state_dir)
    routes = load_routes(base / "routes.json" if (base / "routes.json").exists() else None)
    return [r for r in build_model_rows(base, env=listing_effective_env(), routes=routes)
            if r.get("ref") and r.get("provider") != "alias"]


_BACKGROUND: dict = {}  # str(state_dir) -> the rebuild thread


def wait_for_rebuild(state_dir, timeout: float = 30.0) -> None:
    t = _BACKGROUND.get(str(state_dir))
    if t is not None:
        t.join(timeout)


def _rebuild_in_background(state_dir) -> None:
    key = str(state_dir)
    running = _BACKGROUND.get(key)
    if running is not None and running.is_alive():
        return

    def _run():
        try:
            rebuild(state_dir, catalog_rows(state_dir))
        except Exception:
            pass
    t = threading.Thread(target=_run, name="halo-best-at-rebuild", daemon=True)
    _BACKGROUND[key] = t
    t.start()


def index(state_dir, rows: Optional[list] = None, *, force: bool = False, stale_ok: bool = False) -> dict:
    """The fresh cache, rebuilt from `rows` (else the catalog) when stale or
    `force`; refs in `rows` the fresh cache lacks are scored for this call.
    `stale_ok` (a session start, which must not wait on a slow catalog or an
    Ollama host): a stale cache answers now and a rebuild runs in the
    background for the next reader; a missing one is waited for at most
    `FIRST_BUILD_WAIT_S`, then the caller goes on without it (the build
    finishes behind it)."""
    cache = None if force else load(state_dir)
    if not is_fresh(cache, state_dir):
        if stale_ok and rows is None:
            _rebuild_in_background(state_dir)
            if cache is not None:
                return cache
            wait_for_rebuild(state_dir, FIRST_BUILD_WAIT_S)
            return load(state_dir) or {"schema": SCHEMA, "rows": {}, "best": {}}
        return rebuild(state_dir, rows if rows is not None else catalog_rows(state_dir))
    if rows:
        missing = {r["ref"]: entry_for(r) for r in rows
                   if r.get("ref") and r.get("provider") != "alias" and r["ref"] not in cache["rows"]}
        if missing:
            cache = {**cache, "rows": {**cache["rows"], **missing}}
    return cache
