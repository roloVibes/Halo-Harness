"""halo_harness.providers.embeddings -- Halo 2.0.7: LOCAL embeddings for
memory and session search (the old 2.0.6 scope, renumbered into 2.0.7).

Two transports, one config:
  * Ollama's native `/api/embed` on the default (or named) host -- the
    usual case, zero new setup for anyone already using `ol:`;
  * any OpenAI-compatible `/v1/embeddings` server (`embeddings.base_url`
    + optional `embeddings.api_key`) -- LM Studio, llama.cpp server,
    vLLM, a managed server.

Config (`~/.halo/config.json`, key `embeddings`):
  {"model": "nomic-embed-text", "host": "<ollama host name, optional>",
   "base_url": "...", "api_key": "...", "enabled": true}
DISABLED until `embeddings.model` (or `embeddings.enabled`) is set -- no
host is ever probed, no index is ever built, nothing costs anything
until the owner asks for it.

Same fit spirit as every other local model: an embeddings model missing
from the host's catalog surfaces as a plain "pull it" instruction, never
as a silent failure.
"""
from __future__ import annotations

import json
import urllib.parse
from typing import Optional

DEFAULT_EMBEDDINGS_MODEL = "nomic-embed-text"
_EMBED_TIMEOUT_S = 30.0


def embeddings_config() -> dict:
    """The `embeddings` config dict ({} when unset/corrupt)."""
    try:
        from halo_harness.theme import get_config_value
        raw = get_config_value("embeddings", {})
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def embeddings_enabled() -> bool:
    cfg = embeddings_config()
    if cfg.get("enabled") is True:
        return True
    return bool(cfg.get("model"))


def _post_json(url: str, payload: dict, headers: dict, timeout: float) -> Optional[dict]:
    """One POST + JSON-decode through the ONE network choke point
    (providers.http.open_upstream -- the offline gate runs inside it,
    same as every ollama probe), never a bare urlopen. None on any
    failure: every caller here is best-effort."""
    from halo_harness.providers.http import UpstreamConnectError, open_upstream
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return None
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    tls = parsed.scheme == "https"
    body_bytes = json.dumps(payload).encode("utf-8")
    send_headers = {"Accept-Encoding": "identity", "Content-Type": "application/json", **headers}
    conn = None
    try:
        conn = open_upstream(hostname, port, tls, connect_timeout=timeout)
        if conn.sock:
            conn.sock.settimeout(timeout)
        conn.request("POST", parsed.path or "/", body=body_bytes, headers=send_headers)
        resp = conn.getresponse()
        raw = resp.read()
        if resp.status != 200:
            return None
        return json.loads(raw.decode("utf-8", "replace")) if raw else {}
    except (UpstreamConnectError, OSError, ValueError):
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def embed_texts(texts: list) -> Optional[list]:
    """`texts` -> a list of vectors (same order), or None when embeddings
    are disabled/unconfigured or the call failed (search callers treat
    None as "fall back to no ranking", never as an error)."""
    if not texts:
        return []
    cfg = embeddings_config()
    if not embeddings_enabled():
        return None
    model = cfg.get("model") or DEFAULT_EMBEDDINGS_MODEL
    try:
        if cfg.get("base_url"):
            # OpenAI-compatible /v1/embeddings.
            headers = {}
            key = cfg.get("api_key")
            if key:
                headers["Authorization"] = f"Bearer {key}"
            data = _post_json(cfg["base_url"].rstrip("/") + "/v1/embeddings",
                              {"model": model, "input": list(texts)}, headers, _EMBED_TIMEOUT_S)
            if data is None:
                return None
            return [d.get("embedding") for d in data.get("data") or []]
        # Ollama native /api/embed on the default (or named) host.
        from halo_harness.providers.ollama import _auth_headers, resolve_ollama_host
        host = resolve_ollama_host(cfg.get("host") or None)
        if host is None:
            return None
        data = _post_json(host.url.rstrip("/") + "/api/embed",
                          {"model": model, "input": list(texts)},
                          _auth_headers(host), _EMBED_TIMEOUT_S)
        if data is None:
            return None
        return data.get("embeddings")
    except Exception:
        return None


def cosine(a, b) -> float:
    """Plain cosine similarity; 0.0 for empty/mismatched vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if not na or not nb:
        return 0.0
    return dot / (na * nb)
