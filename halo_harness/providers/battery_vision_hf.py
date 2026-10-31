"""halo_harness.providers.battery_vision_hf -- the battery's vision probe on a Hugging Face local server (Halo 3.3.7.0
R4; the 3.3.6.0 R6 leftover: "only Ollama runs the battery"). The same one 1 px red image and the same scoring
(battery_probes.VISION_ASK / score_vision), sent where the endpoint takes an image; "not asked" where it does not.

    takes_image(base_url, model, *, kind=None, get=None) -> (True | False | None, why)
        llama-server: `/props` `modalities.vision` (started with --mmproj); LM Studio: `/api/v0/models` `type: vlm`;
        MLX: `mlx-vlm` takes one, `mlx` (mlx-lm) does not; any other server (vLLM, TGI, unknown): None -- not asked
    probe(base_url, model, *, kind=None, get=None, post=None, state_dir=None, server="") -> profile
        {model, host, kind, vision: yes | no | unverified | "not asked", vision_why, probed_at, probe_set, evidence}
        one `/v1/chat/completions` with the image as an `image_url` data URL; the profile is kept in the capability
        cache under "hf-local:<base_url>" (providers/ollama_capability.py's file), where vision_fact reads it
    profile_of(state_dir, base_url, model) -> the kept profile | None    any_profile(state_dir, model) -> any server's
`get(url) -> dict | None` and `post(url, body) -> dict | None` are the tests' seams; the defaults go with a
timeout through providers.http's choke point; under the test flag only a loopback address is asked. It sends one tiny call; nothing loads here.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.parse
from typing import Callable, Optional

TIMEOUT_S = 60.0
KEY = "hf-local:"


def _root(base_url: str) -> str:
    u = str(base_url or "").rstrip("/")
    return u[:-3] if u.endswith("/v1") else u


def _guard(url: str) -> Optional[str]:
    import os
    if not os.environ.get("BRIDGE_TEST_HOME"):
        return None
    host = urllib.parse.urlparse(url).hostname or ""
    return None if host in ("127.0.0.1", "localhost", "::1") else f"the test flag keeps {host} out of reach"


def _get(url: str):
    if _guard(url):
        return None
    from halo_harness.providers.huggingface_local_probe import _probe_get
    u = urllib.parse.urlparse(url)
    return _probe_get(f"{u.scheme}://{u.netloc}", u.path, api_key=None, timeout=10.0)


def _post(url: str, body: dict):
    """One POST through the providers.http choke point (open_upstream); {error} on any failure."""
    import http.client
    from halo_harness.providers.http import UpstreamConnectError, open_upstream
    why = _guard(url)
    if why:
        return {"error": why}
    u, conn = urllib.parse.urlparse(url), None
    try:
        conn = open_upstream(u.hostname, u.port or (443 if u.scheme == "https" else 80), u.scheme == "https",
                             connect_timeout=10)
        if conn.sock:
            conn.sock.settimeout(TIMEOUT_S)
        conn.request("POST", u.path, body=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        got = json.loads(resp.read().decode("utf-8", "replace") or "{}")
        if resp.status != 200:
            err = got.get("error") if isinstance(got, dict) else None
            return {"error": str((err or {}).get("message") if isinstance(err, dict) else err or f"HTTP {resp.status}")}
        return got
    except (UpstreamConnectError, OSError, http.client.HTTPException, ValueError) as e:
        return {"error": f"{type(e).__name__}: {e}"}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def takes_image(base_url: str, model: str, *, kind: Optional[str] = None, get: Optional[Callable] = None) -> tuple:
    get = get or _get
    root, k = _root(base_url), str(kind or "").lower()
    if k in ("mlx-vlm", "mlx_vlm"):
        return True, "mlx-vlm's server takes an image_url"
    if k in ("mlx", "mlx-lm", "mlx_lm"):
        return False, "mlx-lm's server is text only: not asked"
    props = get(root + "/props") if k in ("", "llama-server", "llama") else None
    if isinstance(props, dict):
        mods = props.get("modalities") if isinstance(props.get("modalities"), dict) else {}
        if mods.get("vision") is True:
            return True, "llama-server with a projector (/props modalities: vision)"
        return False, "llama-server with no projector (/props lists no vision): not asked"
    models = get(root + "/api/v0/models") if k in ("", "lmstudio", "lm-studio") else None
    rows = (models or {}).get("data") if isinstance(models, dict) else None
    if isinstance(rows, list):
        hit = next((r for r in rows if isinstance(r, dict) and str(r.get("id")) == model), None)
        if hit is not None:
            return (True, "LM Studio lists it as a vlm") if hit.get("type") == "vlm" else \
                (False, f"LM Studio lists it as {hit.get('type') or 'an llm'}: not asked")
    return None, "this server says nothing about images (not llama-server, LM Studio or MLX-VLM): not asked"


def body(model: str) -> dict:
    from halo_harness.providers.battery_probes import VISION_ASK, VISION_PNG, VISION_PREDICT
    url = "data:image/png;base64," + base64.b64encode(VISION_PNG).decode("ascii")
    return {"model": model, "stream": False, "temperature": 0, "max_tokens": VISION_PREDICT,
            "messages": [{"role": "user", "content": [{"type": "text", "text": VISION_ASK},
                                                      {"type": "image_url", "image_url": {"url": url}}]}]}


def _ollama_shaped(reply) -> dict:
    if not isinstance(reply, dict):
        return {"error": "no answer"}
    if reply.get("error"):
        return {"error": str(reply["error"])}
    msg = ((reply.get("choices") or [{}])[0] or {}).get("message") or {}
    return {"message": {"content": msg.get("content") or "", "thinking": msg.get("reasoning_content") or ""}}


def probe(base_url: str, model: str, *, kind: Optional[str] = None, get: Optional[Callable] = None,
          post: Optional[Callable] = None, state_dir=None, server: str = "") -> dict:
    from halo_harness.providers.battery_probes import PROBE_SET, score_vision
    asked, why = takes_image(base_url, model, kind=kind, get=get)
    p = {"model": model, "host": KEY + _root(base_url), "server": server or _root(base_url), "kind": kind or "",
         "probed_at": time.time(), "probe_set": PROBE_SET, "evidence": {}}
    if not asked:
        p.update(vision="not asked", vision_why=why)
    else:
        reply = _ollama_shaped((post or _post)(_root(base_url) + "/v1/chat/completions", body(model)))
        p["vision"], p["vision_why"] = score_vision(reply)
        p["evidence"] = {"asked": why, "reply": str((reply.get("message") or {}).get("content") or reply.get("error"))[:120]}
    if state_dir is not None:
        save(state_dir, p)
    return p


def save(state_dir, p: dict) -> None:
    from halo_harness.filelock import file_lock
    from halo_harness.providers import ollama_capability as C
    with file_lock(C._capability_cache_path(state_dir)):
        cache = C.load_capability_cache(state_dir)
        k = f"{p['host']}|{p['model']}"
        entry = cache.get(k) if isinstance(cache.get(k), dict) else {}
        entry.setdefault("battery", {})[p["host"]] = p
        entry.update(model=p["model"], host=p["host"], checked_at=p["probed_at"])
        cache[k] = entry
        C.save_capability_cache(state_dir, cache)


def profile_of(state_dir, base_url: str, model: str) -> Optional[dict]:
    if state_dir is None or not model:
        return None
    from halo_harness.providers.ollama_capability import load_capability_cache
    host = KEY + _root(base_url)
    got = ((load_capability_cache(state_dir).get(f"{host}|{model}") or {}).get("battery") or {}).get(host)
    return got if isinstance(got, dict) else None


def any_profile(state_dir, model: str) -> Optional[dict]:
    """The newest kept profile of `model` on any HF local server (the card's read: no server is resolved, no request)."""
    if state_dir is None or not model:
        return None
    from halo_harness.providers.ollama_capability import load_capability_cache
    got = [p for k, e in load_capability_cache(state_dir).items() if str(k).startswith(KEY) and isinstance(e, dict)
           for p in (e.get("battery") or {}).values() if isinstance(p, dict) and p.get("model") == model]
    return max(got, key=lambda p: float(p.get("probed_at") or 0)) if got else None
