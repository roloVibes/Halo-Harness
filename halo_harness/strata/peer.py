"""halo_harness.strata.peer -- a Strata server reached from another machine (Halo 3.3.9.2; docs/MODELS-strata.md
"Through the host"): FreeToken's shape (freetoken/peer.py) for the `strata` entry.

The Strata server on the host machine is a host-served local server: `halo host` lists it among its servers
(host/state.server_rows: `kind: server`, `runtime: strata`, its model) in the join reply and the announce, and serves
its entry and key in its catalog (`GET catalog`'s `strata`, the view grant every paired peer holds) when it was started
with `--lan` (`--access lan`, every address behind Halo's key). A peer with no entry of that name resolves
`hf:local/<model>@<host>` (the host's own name, after FreeToken's) or `@strata` through it, to the host's LAN address.

    offer(home) -> {name, url, model, runtime, api_key, lan} | None   the host side (routes_view.catalog); None when the
        server is loopback-only (a peer cannot reach it, so it is not offered)
    remote_entry(name, home=None) -> HFLocalServer | None   the peer side (cached CACHE_S);
        providers/huggingface.resolve_huggingface_local_server falls back to it for a name no entry has
An unpaired machine gets nothing: the host answers only signed requests from its peers. Reads only.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
from pathlib import Path
from typing import Optional

from halo_harness.strata import KEY_ENV, NAME, RUNTIME

CACHE_S = 30.0
_CACHE: dict = {}


def offer(home) -> Optional[dict]:
    try:
        cfg = json.loads((Path(home) / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rows = ((cfg.get("huggingface") or {}).get("local_servers") or []) if isinstance(cfg, dict) else []
    e = next((r for r in rows if isinstance(r, dict) and str(r.get("name") or "").lower() == NAME
              and r.get("strata") is True), None)
    if e is None or not e.get("lan"):
        return None
    from halo_harness.strata.launch import key
    return {"name": NAME, "url": e.get("url"), "model": e.get("model"), "runtime": RUNTIME, "lan": True,
            "api_key": os.environ.get(str(e.get("api_key_env") or KEY_ENV)) or key()}


def _ask(name: str, home=None) -> Optional[dict]:
    try:
        from halo_harness.fleet import identity, store
        from halo_harness.ollama_steward.host_client import HostClient, HostError
        hosts = [e for e in store.hosts(home) if e.get("state", "joined") == "joined"]
    except Exception:
        return None
    from halo_harness.freetoken.peer import _on
    want = str(name or "").lower()
    for e in hosts:
        if want not in (NAME, str(e.get("name") or "").lower()):
            continue
        key = store.key_for(e, home)
        if key is None:
            continue
        try:
            got = HostClient(e, key, identity.harness()["id"]).catalog(4096).get(NAME)
        except HostError:
            continue
        if isinstance(got, dict) and got.get("url"):
            addr = urllib.parse.urlparse(str(e.get("url") or "")).hostname or ""
            return {**got, "url": _on(addr, got["url"]) if addr else got["url"], "via": e.get("name")}
    return None


def remote_entry(name: str, home=None):
    from halo_harness.providers.huggingface import HFLocalServer
    k = str(name or "").lower()
    hit = _CACHE.get(k)
    if hit and time.monotonic() - hit[0] < CACHE_S:
        got = hit[1]
    else:
        got = _ask(k, home)
        _CACHE[k] = (time.monotonic(), got)
    if not got or not got.get("url"):
        return None
    return HFLocalServer(name=str(name), url=str(got["url"]), api_key=got.get("api_key") or None, runtime=RUNTIME)


def reset() -> None:
    _CACHE.clear()
