"""halo_harness.providers.experiential_catalog -- Halo 2.0.4 round 2:
`GET /v1/models` on the Experiential Labs gateway, cached in its own state
file with a TTL -- mirrors `providers.huggingface_catalog`/`providers.
openai_catalog` (themselves modeled on `providers.databricks.probe_
openrouter_models`/`write_models_json`/`refresh_openrouter_catalog_if_
stale`). Kept in its OWN file (`experiential-models.json`, never a shared
flat file) for the same cross-host-id-collision reason every other
per-provider catalog file here already is.

Unlike the Hugging Face router or the real OpenAI API, this gateway's
`GET /v1/models` carries real pricing and context directly (`docs/harness/
EXPERIENTIAL-RESEARCH.md` section 4; the exact field names rest on the
owner's own live-measured response, `plans/ROADMAP.md`'s "ADDED
2026-10-04"/"ADDED 2026-10-05 ~12:40" bullets, not on anything the
hosted docs site states in prose) -- so this module's picker-field reader
needs no models.dev cross-check the way `openai_catalog.oai_picker_fields`
does; the cached file already has everything.
"""

from __future__ import annotations

import http.client
import json
import socket
import ssl
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Optional

_CATALOG_READ_TIMEOUT_S = 30
_AUTO_REFRESH_BACKOFF_S = 300.0

# plans/ROADMAP.md "ADDED 2026-10-04"/"ADDED 2026-10-05 ~12:40": the live-
# measured per-model field set -- carried through unmodified from `GET
# /v1/models` into the cache file (the brief's own "the fields listed
# above").
_FIELDS = (
    "context_window_tokens", "maximum_output_tokens", "pricing",
    "supports_tools", "supports_structured_output", "supports_reasoning",
    "supported_reasoning_efforts", "reasoning_effort", "reasoning_output_hidden",
    "reasoning_content_native", "reports_cached_input_tokens",
    "data_policy", "owned_by", "retention", "stats_source", "pricing_source",
)


def probe_experiential_models(base_url: str, api_key: str) -> "dict[str, dict]":
    """`GET {base_url}/models` -- returns `{"<slug>": {<_FIELDS subset>}}`.
    Raises `UpstreamConnectError` on connect/DNS failure, `RuntimeError` on
    a non-200, same contract as every other `probe_*_models` here."""
    from halo_harness.providers.http import UpstreamConnectError, format_connect_error, open_upstream
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    tls = parsed.scheme == "https"
    path = parsed.path.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {api_key}", "Accept-Encoding": "identity"}
    conn = None
    try:
        conn = open_upstream(host, port, tls)
        if conn.sock:
            conn.sock.settimeout(_CATALOG_READ_TIMEOUT_S)
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
    except (OSError, socket.timeout, ssl.SSLError, http.client.HTTPException) as e:
        raise UpstreamConnectError(format_connect_error(host, e), host=host) from e
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    if resp.status != 200:
        raise RuntimeError(f"Experiential Labs /models returned {resp.status}")
    data = json.loads(raw.decode("utf-8", "replace"))
    out: "dict[str, dict]" = {}
    entries = data.get("data") if isinstance(data, dict) else None
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        slug = entry.get("slug") or entry.get("id")
        if not isinstance(slug, str) or not slug:
            continue
        out[slug] = {k: entry[k] for k in _FIELDS if k in entry}
    return out


def xp_models_json_path(state_dir) -> Path:
    return Path(state_dir) / "experiential-models.json"


def write_xp_models_json(state_dir, entries: "dict[str, dict]") -> None:
    """Best-effort; swallows OSError, same atomicity (tmp file + replace)
    every other catalog writer here uses."""
    try:
        Path(state_dir).mkdir(parents=True, exist_ok=True)
        path = xp_models_json_path(state_dir)
        tmp_path = path.with_name(f".{path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
        import os
        os.replace(tmp_path, path)
    except OSError:
        pass


def load_vendored_experiential_fallback() -> "dict[str, dict]":
    """The package-shipped `providers/catalog/experiential-models.json` --
    built by hand from already-public, already-documented facts (`plans/
    ROADMAP.md`'s live-measured field list and named 2.0.4 models), not a
    fresh live fetch (that needs a real `EXPLABS_API_KEY`, which no round
    building this module ever reads) -- the same offline/no-key floor
    every sibling vendored catalog in this directory provides. `{}` if the
    package data file is somehow missing."""
    path = Path(__file__).resolve().parent / "catalog" / "experiential-models.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict) and not k.startswith("_")}


def load_xp_models_json(state_dir) -> dict:
    """Read experiential-models.json (dict keyed by slug); falls back to
    the vendored snapshot when the state file doesn't exist yet (never
    when it exists but is merely stale -- staleness is `refresh_
    experiential_catalog_if_stale`'s own concern) so a fresh install's
    very first `/model` open still shows real context/prices instead of a
    blank Experiential group."""
    path = xp_models_json_path(state_dir)
    if not path.exists():
        return load_vendored_experiential_fallback()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return load_vendored_experiential_fallback()


def xp_models_json_age_seconds(state_dir) -> Optional[float]:
    path = xp_models_json_path(state_dir)
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return None


_xp_refresh_lock = threading.Lock()
_xp_last_failure_at: "dict[str, float]" = {}


def refresh_experiential_catalog_if_stale(state_dir, *, max_age_hours: Optional[float] = None,
                                           force: bool = False, env: Optional[dict] = None) -> Optional[bool]:
    """The Experiential Labs twin of `refresh_openai_catalog_if_stale` --
    same shared staleness knob, single-flight lock, post-failure backoff
    and `None`-means-nothing-needed-doing / `True`/`False` contract.
    `None` when `EXPLABS_API_KEY` isn't set."""
    key = str(state_dir)
    try:
        if max_age_hours is None:
            from halo_harness.theme import get_config_value
            max_age_hours = get_config_value("databricks.catalog_max_age_hours", default=24)
        age = xp_models_json_age_seconds(state_dir)
        always = float(max_age_hours) <= 0
        if age is not None:
            age = max(0.0, float(age))
        if not force and not always and age is not None and age < float(max_age_hours) * 3600:
            return None
        last_failure_at = _xp_last_failure_at.get(key)
        if not force and last_failure_at is not None and (time.monotonic() - last_failure_at) < _AUTO_REFRESH_BACKOFF_S:
            return None
        from halo_harness.providers.config import resolve_experiential
        xp = resolve_experiential(env)
        if xp is None:
            return None
        from halo_harness.providers.databricks import CATALOG_REFRESH_BUSY
        if not _xp_refresh_lock.acquire(blocking=False):
            return CATALOG_REFRESH_BUSY
        try:
            fetched = probe_experiential_models(xp.base_url, xp.api_key)
            write_xp_models_json(state_dir, fetched)
            _xp_last_failure_at.pop(key, None)
            return True
        except Exception:
            _xp_last_failure_at[key] = time.monotonic()
            return False
        finally:
            _xp_refresh_lock.release()
    except Exception:
        return False


def xp_picker_fields(model_id: str, state_dir) -> dict:
    """`{"context_tokens", "max_output_tokens", "price_in_per_m",
    "price_out_per_m", "price_cache_read_per_m", "price_cache_write_per_m",
    "supports_tools", "supports_reasoning", "supports_structured_output",
    "supported_reasoning_efforts", "reasoning_effort_default",
    "reasoning_output_hidden", "data_policy_badge", "owned_by"}` (any
    subset, possibly empty) for the picker's Experiential group -- `0 ==
    free`/`None == unknown` is preserved as-is (`model_display.format_
    price_per_m` renders the difference), per `plans/ROADMAP.md`'s "0 =
    free, null = unknown shown differently"."""
    entry = load_xp_models_json(state_dir).get(model_id)
    if not isinstance(entry, dict):
        return {}
    out: dict = {}
    if isinstance(entry.get("context_window_tokens"), int):
        out["context_tokens"] = entry["context_window_tokens"]
    if isinstance(entry.get("maximum_output_tokens"), int):
        out["max_output_tokens"] = entry["maximum_output_tokens"]
    pricing = entry.get("pricing") if isinstance(entry.get("pricing"), dict) else {}
    out.update(nano_pricing_to_per_m(pricing))
    if "supports_tools" in entry:
        out["supports_tools"] = bool(entry["supports_tools"])
    if "supports_reasoning" in entry:
        out["supports_reasoning"] = bool(entry["supports_reasoning"])
    if "supports_structured_output" in entry:
        out["supports_structured_output"] = bool(entry["supports_structured_output"])
    efforts = entry.get("supported_reasoning_efforts")
    if isinstance(efforts, list):
        out["supported_reasoning_efforts"] = efforts
    if entry.get("reasoning_effort") is not None:
        out["reasoning_effort_default"] = entry["reasoning_effort"]
    if "reasoning_output_hidden" in entry:
        out["reasoning_output_hidden"] = bool(entry["reasoning_output_hidden"])
    out["owned_by"] = entry.get("owned_by")
    out["data_policy_badge"] = data_policy_badge(entry.get("data_policy"))
    # Halo 2.0.4 round 2 (plans/ROADMAP.md "2.0.4 'new labs' coverage"):
    # "a $0 preview model shows 'free (preview)'" -- a model priced $0
    # that the catalog's own `retention` field ALSO marks as a preview/
    # promotion (e.g. Space Bunny Alpha's "priced $0 today (preview)")
    # is distinguished from a model that is simply, permanently free:
    # `format_price_per_m` alone renders either as the bare word "free",
    # so this flag is what lets a caller add the "(preview)" qualifier.
    retention = str(entry.get("retention") or "")
    out["is_free_preview"] = out.get("price_in_per_m") == 0.0 and "preview" in retention.lower()
    return out


def nano_pricing_to_per_m(pricing: dict) -> dict:
    """`pricing.*_nano_usd_per_million_tokens` -> `price_*_per_m` in plain
    USD per million tokens (`/model_display.format_price_per_m`'s own
    unit) -- divide by 1e9 (1 USD = 1,000,000,000 nano-USD). `0` stays
    `0.0` (rendered "free"); a missing/`null` field is simply omitted
    (rendered blank/"unknown") -- never coerced to 0, which would show a
    model of genuinely UNPUBLISHED price as if it were confirmed free."""
    mapping = {
        "input_nano_usd_per_million_tokens": "price_in_per_m",
        "output_nano_usd_per_million_tokens": "price_out_per_m",
        "cached_input_nano_usd_per_million_tokens": "price_cache_read_per_m",
        "cache_write_nano_usd_per_million_tokens": "price_cache_write_per_m",
    }
    out: dict = {}
    for src_key, dst_key in mapping.items():
        value = pricing.get(src_key) if isinstance(pricing, dict) else None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[dst_key] = value / 1_000_000_000
    return out


def data_policy_badge(data_policy) -> Optional[str]:
    """The picker's one-word data-policy badge -- `"zdr"` (zero data
    retention) wins over a plain `"no_training"` badge when both are set
    (ZDR is the stronger posture and implies no training on the data
    either); `None` when neither flag is set or `data_policy` itself is
    missing/malformed (no badge shown, never a misleading blank one)."""
    if not isinstance(data_policy, dict):
        return None
    if data_policy.get("zdr"):
        return "zdr"
    if data_policy.get("no_training"):
        return "no_training"
    return None
