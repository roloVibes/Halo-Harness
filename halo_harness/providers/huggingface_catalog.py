"""halo_harness.providers.huggingface_catalog -- Halo 2.0.3 round 4: the
router's `GET /v1/models` catalog, cached in the state dir with a TTL,
mirroring `providers.databricks.probe_openrouter_models`/`write_models_
json`/`refresh_openrouter_catalog_if_stale`. Split out of `providers.
huggingface` (which owns `huggingface.endpoints`/`huggingface.bill_to`
config resolution) purely to keep each file's own writes under the house
250-line-per-write habit while this was being built -- both modules are
Halo 2.0.3 round 4, same design doc.

Halo 2.0.4 round 3 (owner live report, 2026-10-05: "hugging face in models
does not show the costs or context prices in the /model list"; confirmed
in plans/2.0.3-release-notes-for-fix-pass.md's own "MUST FIX" note,
2026-10-04, with the owner's real token): the router's `GET /v1/models` is
NOT flat like OpenRouter's -- each entry's price/context/capability live
PER INFERENCE PROVIDER, under its own `providers` list: `{id, object,
created, owned_by, architecture, providers: [{provider, status,
context_length, pricing: {input, output}, is_free, supports_tools,
supports_structured_output, first_token_latency_ms, throughput,
is_model_author}, ...]}`. `_parse_catalog_entry`/`pick_best_provider_row`
below now read THAT shape (one coherent provider row supplies ALL of a
model's columns together, never a blend of several providers' own
numbers) -- the OLD flat top-level `context_length`/`pricing` assumption
(this module's pre-round-3 docstring called it "a DOCUMENTED ASSUMPTION,
not a confirmed fact") is kept ONLY as one more candidate row when no real
`providers` list is present, so a flatter response (or a test fixture
written against the old assumption) still parses exactly as before."""

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


def _to_float(v) -> "Optional[float]":
    if isinstance(v, bool) or v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _normalize_provider_row(row) -> "Optional[dict]":
    """One raw `providers[]` entry -> `{"provider", "status",
    "context_length", "pricing": {"prompt", "completion"}, "is_free",
    "supports_tools", "supports_structured_output",
    "first_token_latency_ms", "throughput"}` (every key optional, `None`
    if nothing usable at all). `pricing` is re-keyed to "prompt"/
    "completion" -- the SAME names `_profile_from_models_json_entry`
    (model.py) and OpenRouter's own rows already use -- reading the real
    shape's `input`/`output` first, falling back to `prompt`/`completion`
    for a flatter/older-shaped row (a test fixture, or a future response
    that happens to match OpenRouter's own naming)."""
    if not isinstance(row, dict):
        return None
    out: dict = {}
    if isinstance(row.get("provider"), str) and row["provider"]:
        out["provider"] = row["provider"]
    if isinstance(row.get("status"), str) and row["status"]:
        out["status"] = row["status"]
    if isinstance(row.get("context_length"), int):
        out["context_length"] = row["context_length"]
    pricing = row.get("pricing")
    if isinstance(pricing, dict):
        # Unit, measured live 2026-10-05: the router's provider rows carry USD
        # PER MILLION tokens as numbers ({"input": 0.42, "output": 3.0}); only
        # the older OpenRouter-style form is a per-token STRING ("0.0000002").
        # Everything stored in the cache is $/M, so the picker never converts.
        def _per_m(raw):
            val = _to_float(raw)
            if val is None:
                return None
            return val * 1_000_000 if isinstance(raw, str) else val
        raw_in = pricing.get("input") if pricing.get("input") is not None else pricing.get("prompt")
        raw_out = pricing.get("output") if pricing.get("output") is not None else pricing.get("completion")
        price_in = _per_m(raw_in)
        price_out = _per_m(raw_out)
        if price_in is not None or price_out is not None:
            out["pricing"] = {}
            if price_in is not None:
                out["pricing"]["prompt"] = price_in
            if price_out is not None:
                out["pricing"]["completion"] = price_out
    for bool_key in ("is_free", "supports_tools", "supports_structured_output"):
        if isinstance(row.get(bool_key), bool):
            out[bool_key] = row[bool_key]
    for num_key in ("first_token_latency_ms", "throughput"):
        if isinstance(row.get(num_key), (int, float)) and not isinstance(row.get(num_key), bool):
            out[num_key] = row[num_key]
    return out if out else None


def _price_sort_key(row: dict):
    """Ascending by prompt-side price; a row with no usable price sorts
    LAST regardless of direction (never mistaken for "the cheapest" just
    because an unknown price compares as smaller than a real one)."""
    price = (row.get("pricing") or {}).get("prompt")
    return (0, price) if isinstance(price, (int, float)) else (1, 0.0)


def pick_best_provider_row(providers: "list[dict]", *, pinned_provider: "Optional[str]" = None) -> "Optional[dict]":
    """ONE provider row to source every column from together (price,
    context, speed, is_free) -- never a mix of several providers' own
    numbers (owner report: "make the HF group's columns come from THE
    provider the router would route to"). `pinned_provider` (an
    `hf:<org>/<model>:<provider>` ref's own routing suffix, when the
    caller has one and it is still live) wins outright; otherwise the
    cheapest LIVE row. A row with no `status` field at all is treated as
    live (permissive default -- a flatter/older-shaped response, or a
    test fixture, never carries one); when NONE of the real rows report
    `status == "live"` either (every provider down, or the vocabulary
    this probe assumes doesn't match a real response), falls back to the
    cheapest row regardless of status rather than going blank. `None`
    only when `providers` itself is empty."""
    if not providers:
        return None
    if pinned_provider:
        for row in providers:
            if row.get("provider") == pinned_provider and row.get("status", "live") == "live":
                return row
    live = [r for r in providers if r.get("status", "live") == "live"]
    pool = live if live else providers
    return min(pool, key=_price_sort_key)


def _parse_catalog_entry(entry: dict) -> Optional[dict]:
    """One `GET /v1/models` row -> `{"id", "providers", "context_length",
    "pricing", "is_free", "first_token_latency_ms", "throughput",
    "provider"}` -- every key but `id` optional. `providers` is the full
    normalized per-provider list (kept so a later, more specific lookup --
    a `:<provider>`-pinned ref -- can still re-pick from it); the other
    keys are `pick_best_provider_row`'s own choice among them, hoisted to
    the top level so `_profile_from_models_json_entry` (model.py's `hf:`
    request-time profile resolution) keeps reading the EXACT SAME
    `context_length`/`pricing.{prompt,completion}` shape it always has,
    now correctly populated instead of perpetually absent."""
    if not isinstance(entry, dict) or not entry.get("id"):
        return None
    normalized_providers: "list[dict]" = []
    providers_raw = entry.get("providers")
    if isinstance(providers_raw, list):
        for row in providers_raw:
            normalized = _normalize_provider_row(row)
            if normalized:
                normalized_providers.append(normalized)
    if not normalized_providers:
        # Backward-compat candidate: a bare top-level context_length/
        # pricing (the pre-round-3 assumption) or a nested "endpoints"
        # list (never "providers" -- already handled above) -- degrades
        # to this ONLY when no real per-provider list was usable at all.
        flat: dict = {}
        if isinstance(entry.get("context_length"), int):
            flat["context_length"] = entry["context_length"]
        if isinstance(entry.get("pricing"), dict):
            normalized_flat_pricing = _normalize_provider_row({"pricing": entry["pricing"]})
            if normalized_flat_pricing:
                flat["pricing"] = normalized_flat_pricing["pricing"]
        if flat:
            normalized_providers.append(flat)
        else:
            nested = entry.get("endpoints")
            if isinstance(nested, list):
                for row in nested:
                    normalized = _normalize_provider_row(row)
                    if normalized:
                        normalized_providers.append(normalized)
    out: dict = {"id": entry["id"]}
    if normalized_providers:
        out["providers"] = normalized_providers
        best = pick_best_provider_row(normalized_providers)
        if best:
            for key in ("context_length", "pricing", "is_free", "first_token_latency_ms", "throughput", "provider"):
                if key in best:
                    out[key] = best[key]
    return out


def probe_huggingface_models(base_url: str, api_key: str) -> "list[dict]":
    """`GET {base_url}/models` on the router -- returns a `probe_openrouter_
    models`-shaped list (`id`, optional `context_length`/`pricing`). Raises
    `UpstreamConnectError` on connect/DNS failure, `RuntimeError` on a
    non-200, same contract as `probe_openrouter_models`."""
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
        raise RuntimeError(f"Hugging Face /models returned {resp.status}")
    data = json.loads(raw.decode("utf-8", "replace"))
    out = []
    for entry in data.get("data", []) if isinstance(data, dict) else []:
        parsed_entry = _parse_catalog_entry(entry)
        if parsed_entry is not None:
            out.append(parsed_entry)
    return out


def hf_models_json_path(state_dir) -> Path:
    """Deliberately a SEPARATE file from `providers.databricks.models_json_
    path` (OpenRouter's `models.json`): both files are bare-id-keyed with
    no provider namespace of their own, and an OpenRouter id colliding with
    a Hugging Face one (e.g. the same `org/model` string served by both)
    would silently cross-contaminate a shared flat file -- kept apart
    instead so `model.resolve_model_profile`'s huggingface branch only ever
    reads what THIS probe actually wrote."""
    return Path(state_dir) / "huggingface-models.json"


def write_hf_models_json(state_dir, models: "list[dict]") -> None:
    """Write huggingface-models.json as {"<id>": {"context_length":,
    "pricing":, "providers":, "is_free":, "first_token_latency_ms":,
    "throughput":, "provider":}, ...} (every key but the id optional),
    same tmp-file-plus-replace atomicity as `providers.databricks.write_
    models_json`. Best-effort; swallows OSError.

    Halo 2.0.4 round 3: `providers`/`is_free`/`first_token_latency_ms`/
    `throughput`/`provider` join the original two keys -- the full
    per-provider list (so a later, more specific lookup can still re-pick
    from it) plus `_parse_catalog_entry`'s own already-chosen best row's
    extra fields, hoisted to the top level for `hf_picker_fields` to read
    with no second pass over the list."""
    try:
        Path(state_dir).mkdir(parents=True, exist_ok=True)
        out = {}
        for m in models:
            mid = m.get("id")
            if not mid:
                continue
            entry = {}
            for key in ("context_length", "pricing", "providers", "is_free",
                        "first_token_latency_ms", "throughput", "provider"):
                if key in m:
                    entry[key] = m[key]
            out[mid] = entry
        path = hf_models_json_path(state_dir)
        tmp_path = path.with_name(f".{path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        import os
        os.replace(tmp_path, path)
    except OSError:
        pass


def load_hf_models_json(state_dir) -> dict:
    """Read huggingface-models.json (dict keyed by id); {} if missing/
    unparseable. Pure file read, no network -- the picker's first paint
    (`Controller.list_models()`) calls this directly, never the probe."""
    path = hf_models_json_path(state_dir)
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def hf_picker_fields(entry: dict, *, pinned_provider: "Optional[str]" = None) -> dict:
    """Halo 2.0.4 round 3 (deliverable 1 fix, owner live report
    2026-10-05): the picker's own price/context/speed columns for ONE
    `hf:` catalog entry (as `load_hf_models_json` returns it) --
    `{"context_tokens", "price_in_per_m", "price_out_per_m",
    "speed_ttft_s", "speed_tokens_per_second"}`, every key omitted when
    unknown (the caller's own `unknown_as_qmark` renders that as "?").
    `pinned_provider`: re-picks from the entry's own stored `providers`
    list for an `hf:<org>/<model>:<provider>` ref instead of using the
    cache-write-time default (cheapest live) -- `None` (the picker's own
    bare, unsuffixed rows) uses that stored default directly, no second
    pick needed."""
    source = entry
    if pinned_provider and isinstance(entry.get("providers"), list):
        best = pick_best_provider_row(entry["providers"], pinned_provider=pinned_provider)
        if best:
            source = best
    out: dict = {}
    if isinstance(source.get("context_length"), int):
        out["context_tokens"] = source["context_length"]
    pricing = source.get("pricing") if isinstance(source.get("pricing"), dict) else {}
    # The cache stores $/M (see _normalize_provider_row); no conversion here.
    price_in = _to_float(pricing.get("prompt"))
    price_out = _to_float(pricing.get("completion"))
    if price_in is not None:
        out["price_in_per_m"] = price_in
    if price_out is not None:
        out["price_out_per_m"] = price_out
    if source.get("is_free") is True:
        out["price_in_per_m"] = 0.0
        out["price_out_per_m"] = 0.0
    ttft_ms = source.get("first_token_latency_ms")
    if isinstance(ttft_ms, (int, float)) and not isinstance(ttft_ms, bool) and ttft_ms >= 0:
        out["speed_ttft_s"] = ttft_ms / 1000.0
    throughput = source.get("throughput")
    if isinstance(throughput, (int, float)) and not isinstance(throughput, bool) and throughput > 0:
        out["speed_tokens_per_second"] = throughput
    return out


def hf_models_json_age_seconds(state_dir) -> Optional[float]:
    path = hf_models_json_path(state_dir)
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return None


_hf_refresh_lock = threading.Lock()
_hf_last_failure_at: "dict[str, float]" = {}


def refresh_huggingface_catalog_if_stale(state_dir, *, max_age_hours: Optional[float] = None,
                                          force: bool = False, env: Optional[dict] = None) -> Optional[bool]:
    """The Hugging Face mirror of `providers.databricks.refresh_openrouter_
    catalog_if_stale` -- same staleness knob (`databricks.catalog_max_age_
    hours`, shared across every network catalog this harness caches, per
    that function's own "one shared staleness knob, never a second config
    key" rule), same single-flight lock/post-failure backoff shape, same
    `None`-means-nothing-needed-doing / `True`/`False` contract. `None`
    when Hugging Face isn't configured (no `HF_TOKEN`) -- an endpoint-only
    setup has no router catalog to refresh either, by design."""
    key = str(state_dir)
    try:
        if max_age_hours is None:
            from halo_harness.theme import get_config_value
            max_age_hours = get_config_value("databricks.catalog_max_age_hours", default=24)
        age = hf_models_json_age_seconds(state_dir)
        always = float(max_age_hours) <= 0
        if age is not None:
            age = max(0.0, float(age))
        if not force and not always and age is not None and age < float(max_age_hours) * 3600:
            return None
        last_failure_at = _hf_last_failure_at.get(key)
        if not force and last_failure_at is not None and (time.monotonic() - last_failure_at) < _AUTO_REFRESH_BACKOFF_S:
            return None
        from halo_harness.providers.config import resolve_huggingface
        hf = resolve_huggingface(env)
        if hf is None:
            return None
        from halo_harness.providers.databricks import CATALOG_REFRESH_BUSY
        if not _hf_refresh_lock.acquire(blocking=False):
            return CATALOG_REFRESH_BUSY
        try:
            fetched = probe_huggingface_models(hf.base_url, hf.api_key)
            write_hf_models_json(state_dir, fetched)
            _hf_last_failure_at.pop(key, None)
            return True
        except Exception:
            _hf_last_failure_at[key] = time.monotonic()
            return False
        finally:
            _hf_refresh_lock.release()
    except Exception:
        return False
