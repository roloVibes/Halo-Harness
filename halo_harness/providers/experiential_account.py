"""halo_harness.providers.experiential_account -- Halo 2.0.4 round 2: the
inference-key-reachable account endpoints (`docs/harness/EXPERIENTIAL-
RESEARCH.md` section 6) -- `GET /api/v1/credits` (the balance chip,
`halo doctor`/`halo providers`), `GET /api/v1/usage` (settled rows,
`halo cost --experiential`), and `GET /api/models/<slug>/providers` (the
waterfall rung list, `/xp routes <slug>`). All bounded-timeout, best-
effort reads -- never raise, so a doctor/providers/cost pass never hangs
or crashes on a slow/unreachable account endpoint; the richer Spend API
needs the separate `EXPLABS_PROVISIONING_KEY` this harness never asks for
(section 2) and is out of scope here."""

from __future__ import annotations

import json
import socket
import ssl
import http.client
import urllib.parse
from typing import Optional

_ACCOUNT_READ_TIMEOUT_S = 10


def _get_json(base_url: str, path: str, api_key: str, *, timeout: int = _ACCOUNT_READ_TIMEOUT_S):
    """One bounded GET against an Experiential Labs account-API path,
    returning the parsed JSON body on a 2xx or `None` on ANY failure
    (connect error, non-2xx, malformed body) -- every caller in this
    module is a best-effort read, never a turn-blocking requirement."""
    from halo_harness.providers.http import open_upstream
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    tls = parsed.scheme == "https"
    full_path = parsed.path.rstrip("/") + path
    headers = {"Authorization": f"Bearer {api_key}", "Accept-Encoding": "identity"}
    conn = None
    try:
        conn = open_upstream(host, port, tls, connect_timeout=timeout)
        if conn.sock:
            conn.sock.settimeout(timeout)
        conn.request("GET", full_path, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        if resp.status != 200:
            return None
        return json.loads(raw.decode("utf-8", "replace"))
    except (OSError, socket.timeout, ssl.SSLError, http.client.HTTPException, ValueError):
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def fetch_experiential_credits(env: Optional[dict] = None) -> Optional[dict]:
    """`{"total_credits": <USD>, "total_usage": <USD>}` from `GET
    /api/v1/credits` (research doc section 6, confirmed against the
    owner's own live call) -- `None` when not configured or the fetch
    fails for any reason."""
    from halo_harness.providers.config import resolve_experiential
    xp = resolve_experiential(env)
    if xp is None:
        return None
    body = _get_json(xp.account_base_url, "/credits", xp.api_key)
    data = body.get("data") if isinstance(body, dict) else None
    return data if isinstance(data, dict) else None


def format_experiential_balance_line(credits: Optional[dict]) -> Optional[str]:
    """`"Experiential Labs: $X.XX available of $Y.YY total credits"` --
    `None` when `credits` is unusable (so a caller can decide whether to
    show a fallback line of its own, same contract as `providers.
    openrouter_account.format_balance_line`)."""
    if not isinstance(credits, dict):
        return None
    total = credits.get("total_credits")
    used = credits.get("total_usage")
    if not isinstance(total, (int, float)) or not isinstance(used, (int, float)):
        return None
    available = total - used
    return f"Experiential Labs: ${available:.2f} available of ${total:.2f} total credits"


def fetch_experiential_generation(request_id: str, env: Optional[dict] = None) -> Optional[dict]:
    """Halo 2.0.4 round 5 (xp: contract alignment): `GET /api/v1/
    generation?id=<request_id>` (llms.txt "Cost API" -- "One request: ...
    GET /api/v1/generation?id=<id> (bare or gen-<id>) returns
    {data:{total_cost, provider_name, tokens...}}") -- after-the-fact
    attribution for one specific call by its own `x-request-id`, for
    `halo stats --experiential --id <id>`. `request_id` is sent exactly
    as given (the contract accepts it "bare or gen-<id>" -- never
    rewritten/guessed at here). `None` on any failure (not configured,
    unknown id, unreachable) -- same best-effort contract as every other
    reader in this module."""
    from halo_harness.providers.config import resolve_experiential
    xp = resolve_experiential(env)
    if xp is None:
        return None
    path = f"/generation?id={urllib.parse.quote(request_id, safe='')}"
    body = _get_json(xp.account_base_url, path, xp.api_key)
    data = body.get("data") if isinstance(body, dict) else None
    return data if isinstance(data, dict) else None


def fetch_experiential_usage_rows(env: Optional[dict] = None, *, cursor: Optional[str] = None) -> Optional[list]:
    """One page of `GET /api/v1/usage` (research doc section 6) --
    settled-row export for `halo cost --experiential`. `None` on any
    failure; `cursor` (the previous page's own `next_cursor`) pages
    forward -- a caller wanting every row loops until `next_cursor` is
    `None` (not done by this function itself, which only ever fetches the
    ONE page it was asked for)."""
    from halo_harness.providers.config import resolve_experiential
    xp = resolve_experiential(env)
    if xp is None:
        return None
    path = "/usage" if not cursor else f"/usage?cursor={urllib.parse.quote(cursor)}"
    body = _get_json(xp.account_base_url, path, xp.api_key)
    data = body.get("data") if isinstance(body, dict) else None
    return data if isinstance(data, list) else None


def fetch_experiential_routes(slug: str, env: Optional[dict] = None) -> Optional[list]:
    """`GET /api/models/<slug>/providers` (research doc section 3.4/4) --
    the waterfall rung list `/xp routes <slug>` prints. This path is
    neither of `ExpConfig`'s two base URLs: not `/v1` (inference) and not
    `/api/v1` (account) -- a THIRD, bare-host-rooted family the docs name
    directly (`/api/models/...`, no `/v1` segment at all) -- so this
    builds the request against the host alone, ignoring both base URLs'
    own path prefixes. `None` on any failure (not configured, bad slug,
    unreachable)."""
    from halo_harness.providers.config import resolve_experiential
    xp = resolve_experiential(env)
    if xp is None:
        return None
    parsed = urllib.parse.urlparse(xp.account_base_url)
    host_root = f"{parsed.scheme}://{parsed.netloc}"
    body = _get_json(host_root, f"/api/models/{urllib.parse.quote(slug, safe='')}/providers", xp.api_key)
    # Live shape (2026-10-05, measured with the owner's key):
    # {"slug": ..., "model_id": ..., "providers": [...]}; "data" and a bare
    # list are accepted too in case the gateway ever changes the envelope.
    if isinstance(body, dict):
        data = body.get("providers")
        if data is None:
            data = body.get("data")
    else:
        data = body
    return data if isinstance(data, list) else None
