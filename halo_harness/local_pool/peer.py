"""halo_harness.local_pool.peer -- the pool reached from another machine (Halo 3.3.8.0 R3; docs/POOL.md "From a peer").

The controller's llama-server listens on its LAN address behind a generated api key. The controller's `halo host`
serves the `pool` entry and that key in its catalog (`GET catalog`'s `pool`, the view grant every paired peer holds);
a peer with no `pool` entry of its own resolves `hf:local/<model>@pool` through it, to the controller's LAN address.
An unpaired machine gets nothing: the host answers only signed requests from its peers.

    offer(home) -> {name, url, model, max_ctx, cache, members, api_key} | None    the host side (routes_view.catalog):
        the pool entry of THAT home's config.json and its key (the env var the entry names)
    remote_entry(home=None) -> HFLocalServer | None   the peer side: the first paired host whose catalog offers a pool
        (cached CACHE_S); providers/huggingface.resolve_huggingface_local_server("pool") falls back to it
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

CACHE_S = 30.0
_CACHE: dict = {}


def offer(home) -> Optional[dict]:
    try:
        cfg = json.loads((Path(home) / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rows = ((cfg.get("huggingface") or {}).get("local_servers") or []) if isinstance(cfg, dict) else []
    e = next((r for r in rows if isinstance(r, dict) and str(r.get("name") or "").lower() == "pool"
              and r.get("pool") is True), None)
    if e is None:
        return None
    from halo_harness.local_pool.entry import KEY_ENV, key
    env = str(e.get("api_key_env") or KEY_ENV)
    return {"name": "pool", "url": e.get("url"), "model": e.get("model"), "max_ctx": e.get("max_ctx"),
            "cache": e.get("cache"), "members": e.get("members") or [], "runtime": "llama-server",
            "api_key": os.environ.get(env) or (key() if env == KEY_ENV else None)}


def remote_entry(home=None):
    from halo_harness.providers.huggingface import HFLocalServer
    hit = _CACHE.get("pool")
    if hit and time.monotonic() - hit[0] < CACHE_S:
        got = hit[1]
    else:
        got = _ask(home)
        _CACHE["pool"] = (time.monotonic(), got)
    if not got or not got.get("url"):
        return None
    return HFLocalServer(name="pool", url=str(got["url"]), api_key=got.get("api_key") or None, runtime="llama-server",
                         max_ctx=got.get("max_ctx") if isinstance(got.get("max_ctx"), int) else None)


def _ask(home=None) -> Optional[dict]:
    try:
        from halo_harness.fleet import identity, store
        from halo_harness.ollama_steward.host_client import HostClient, HostError
        hosts = [e for e in store.hosts(home) if e.get("state", "joined") == "joined"]
    except Exception:
        return None
    for e in hosts:
        key = store.key_for(e, home)
        if key is None:
            continue
        try:
            got = HostClient(e, key, identity.harness()["id"]).catalog(4096).get("pool")
        except HostError:
            continue
        if isinstance(got, dict) and got.get("url"):
            return {**got, "via": e.get("name")}
    return None


def reset() -> None:
    _CACHE.clear()
