"""halo_harness.studio.local_catalog -- Halo 3.3.5.0 R1: one catalog per host,
read again only when the host's model list changed.

The Ollama panel (studio/ollama_hosts_view.py) and the Local tab's Hosts and
Models pages ask for each host's catalog (`/api/tags`, then one `/api/show`
per model) every time they refresh; 3.3.4.0 R5 found the panel re-reading
every host's whole catalog each minute while it was open. Here the cache is
keyed by the catalog's mtime: `/api/tags` alone is read (at most once per
TAGS_TTL_S), and its signature -- every model's name, digest and
`modified_at`, the newest `modified_at` first -- decides: the same signature
keeps the catalog in hand, a new one (a pull, a delete, a twin made) builds it
again through `providers.ollama.get_catalog(force=True)`.

    catalog_for(host, *, tags=None, build=None) -> {"models": [...], "fetched_at", "signature"}
    reset()

`tags(host)` and `build(host)` are the tests' seams.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

TAGS_TTL_S = 15.0
_LOCK = threading.Lock()
_CACHE: dict = {}  # url -> {"sig", "catalog", "tags_at"}


def signature(tags: Optional[dict]) -> Optional[tuple]:
    rows = [r for r in (tags or {}).get("models") or [] if isinstance(r, dict)] if isinstance(tags, dict) else None
    if rows is None:
        return None
    newest = max((str(r.get("modified_at") or "") for r in rows), default="")
    return (newest,) + tuple(sorted((str(r.get("model") or r.get("name") or ""), str(r.get("digest") or ""),
                                     str(r.get("modified_at") or "")) for r in rows))


def _tags(host):
    from halo_harness.providers.ollama import fetch_tags
    return fetch_tags(host)


def _build(host) -> dict:
    from halo_harness.providers.ollama import get_catalog
    return get_catalog(host, force=True)


def catalog_for(host, *, tags: Optional[Callable] = None, build: Optional[Callable] = None) -> dict:
    url = str(getattr(host, "url", "") or "")
    now = time.monotonic()
    with _LOCK:
        hit = _CACHE.get(url)
    if hit is not None and now - hit["tags_at"] < TAGS_TTL_S:
        return hit["catalog"]
    from halo_harness.providers.ollama import host_is_openai_dialect
    if host_is_openai_dialect(host):
        sig = ("openai", int(now // 300))  # a gateway has no tags to compare: its /v1/models list, every 5 minutes
    else:
        sig = signature((tags or _tags)(host))
    if hit is not None and (sig is None or sig == hit["sig"]):
        with _LOCK:
            hit["tags_at"] = now  # unchanged (or the server did not answer): the catalog in hand stays
        return hit["catalog"]
    catalog = dict((build or _build)(host) or {"models": []})
    catalog["signature"] = list(sig[:1]) if sig else None
    with _LOCK:
        _CACHE[url] = {"sig": sig, "catalog": catalog, "tags_at": now}
    return catalog


def reset() -> None:
    with _LOCK:
        _CACHE.clear()
