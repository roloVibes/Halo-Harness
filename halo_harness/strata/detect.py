"""halo_harness.strata.detect -- a server on a probed port that is Strata (Halo 3.3.9.2; the loopback auto-detect,
providers/huggingface_local_probe.probe_models_endpoint, asks it).

Strata's `/v1/models` rows carry no `owned_by`; each has `meta: {n_ctx}`, `status: {value}` and `architecture`
(serve/server.py, from the source, unverified against a live run) -- a shape llama-server's router also uses, so the
shape alone only nominates it. `GET /health` (no key needed) answers `{"status": "ok", ..., "service": "strata"}`: that
names it. Strata answers `/props` too, llama.cpp-style ("build_info": "Strata <version>"), which is why the probe's
`/props` fallback would otherwise call it llama-server.

    strata_rows(base_url, rows, *, timeout=1.0) -> {model id: window} | None   None: not Strata
"""

from __future__ import annotations

from typing import Optional

from halo_harness.strata import SERVICE


def _window(row: dict) -> Optional[int]:
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    n = meta.get("n_ctx")
    return n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else None


def strata_rows(base_url: str, rows: list, *, timeout: float = 1.0) -> Optional[dict]:
    shaped = [r for r in rows if isinstance(r, dict) and not r.get("owned_by") and isinstance(r.get("meta"), dict)
              and "architecture" in r]
    if not shaped:
        return None
    from halo_harness.providers.huggingface_local_probe import _probe_get
    root = str(base_url or "").rstrip("/")
    root = root[:-3] if root.endswith("/v1") else root
    got = _probe_get(root, "/health", api_key=None, timeout=timeout)
    if not (isinstance(got, dict) and str(got.get("service") or "").lower() == SERVICE):
        return None
    return {str(r["id"]): w for r in shaped if r.get("id") and (w := _window(r))}
