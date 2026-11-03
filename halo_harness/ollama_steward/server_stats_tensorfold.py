"""halo_harness.ollama_steward.server_stats_tensorfold -- Halo 3.3.9.3: a TensorFold server's queue, read from its
`/health` and `/metrics` beside its log (server_log_hf.scan asks it on each tick for a `tensorfold` server on this
machine; the log's done lines carry each request's queued seconds, these carry the queue itself).

From TensorFold's docs/api.md "Health" and "Metrics" (from the source, unverified against a live run): `GET /health`
answers without a key; with keys configured its body is only {"status": "ok"}, without keys it carries `live`
{connections: running + waiting, waiting, decode_tokens_per_second, prefill_tokens_per_second} and `max_batch_size`
(the lanes served at once). `GET /metrics` is Prometheus text -- `tensorfold:requests_running`,
`tensorfold:requests_waiting`, `tensorfold:lanes` (and vLLM's names for the same readings) -- and wants the key unless
the server runs with `--metrics-open`. Halo's own server runs behind Halo's key (providers/local_runtime_tensorfold.py),
so for it the key goes with the `/metrics` read; a hand-started server without keys answers `/health` in full.

    read(server, *, key=None, timeout=1.0) -> [event]   one `queue` event {connections, running, waiting, lanes,
        source: "/health" | "/metrics"} when requests wait, else []
    parse_metrics(text) -> {name: value}   the unlabelled samples of the scrape
Reads only, loopback only; never a model call.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from halo_harness.ollama_steward.server_rules import event

_SAMPLE = re.compile(r"^([A-Za-z_:][\w:]*)(?:\{[^}]*\})?\s+([-+0-9.eE]+|NaN)\s*$")


def _get(url: str, key: Optional[str], timeout: float):
    import http.client
    import urllib.parse
    from halo_harness.providers.http import UpstreamConnectError, open_upstream
    u = urllib.parse.urlparse(url)
    conn = None
    try:
        conn = open_upstream(u.hostname or "127.0.0.1", u.port or 80, u.scheme == "https", connect_timeout=max(1, int(timeout)))
        if conn.sock:
            conn.sock.settimeout(timeout)
        conn.request("GET", u.path or "/", headers={"Accept-Encoding": "identity",
                                                    **({"Authorization": f"Bearer {key}"} if key else {})})
        resp = conn.getresponse()
        return resp.status, resp.read().decode("utf-8", "replace")
    except (UpstreamConnectError, OSError, http.client.HTTPException, ValueError):
        return 0, ""
    finally:
        if conn is not None:
            conn.close()


def parse_metrics(text: str) -> dict:
    out: dict = {}
    for line in str(text or "").splitlines():
        m = _SAMPLE.match(line.strip()) if line and not line.startswith("#") else None
        if m and m.group(1) not in out:
            try:
                out[m.group(1)] = float(m.group(2))
            except ValueError:
                continue
    return out


def _key_for(server) -> Optional[str]:
    if str(getattr(server, "name", "") or "").lower() != "tensorfold" and getattr(server, "id", None) != "tensorfold":
        return None
    from halo_harness.providers.local_runtime_tensorfold import key
    return key()


def read(server, *, key: Optional[str] = None, timeout: float = 1.0) -> list:
    from halo_harness.ollama_steward.servers_hf import base
    root = base(getattr(server, "url", ""))
    code, body = _get(f"{root}/health", None, timeout)
    try:
        health = json.loads(body) if code == 200 else None
    except ValueError:
        health = None
    live = health.get("live") if isinstance(health, dict) else None
    model = getattr(server, "model", None)
    if isinstance(live, dict):
        waiting, conns = int(live.get("waiting") or 0), int(live.get("connections") or 0)
        lanes = health.get("max_batch_size")
        nums = {"connections": conns, "running": conns - waiting, "waiting": waiting,
                "lanes": lanes if isinstance(lanes, int) else None, "source": "/health"}
    else:
        code, text = _get(f"{root}/metrics", key if key is not None else _key_for(server), timeout)
        if code != 200:
            return []
        m = parse_metrics(text)
        if "tensorfold:requests_waiting" not in m:
            return []
        waiting, running = int(m["tensorfold:requests_waiting"]), int(m.get("tensorfold:requests_running") or 0)
        lanes = m.get("tensorfold:lanes")
        nums = {"connections": running + waiting, "running": running, "waiting": waiting,
                "lanes": int(lanes) if lanes is not None else None, "source": "/metrics"}
    if nums["waiting"] <= 0:
        return []
    say = (f"{nums['waiting']} requests waiting, {nums['running']} running"
           + (f" on {nums['lanes']} streams" if nums["lanes"] else "") + f" ({nums['source']})")
    return [event("queue", say, f"GET {root}{nums['source']}: {json.dumps(nums)}", model=model, runtime="tensorfold",
                  **nums)]
