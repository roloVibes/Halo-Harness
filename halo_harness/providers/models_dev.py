"""halo_harness.providers.models_dev -- models.dev `api.json` fetch + cache
(H8 scope C). A public, unauthenticated, unversioned metadata catalog
(https://models.dev/api.json, ~5 MB, 200+ providers) that the plan uses "for
Databricks rows and to cross-check model_table.json" -- fetched and cached
to `<state_dir>/models-dev.json` by `halo models --refresh`
(catalog_cli.py), same lifecycle as `models.json`/`dbx-endpoints.json`.

The vendored PACKAGE fallback (`providers/catalog/models_dev_databricks_
fallback.json`) is a small, committed, one-time TRIM of this same live data
down to just the `databricks` provider entry (regenerate it the same way
this module fetches, then re-save via `write_databricks_fallback` below --
a human/release step, never done automatically) -- see
`providers/catalog/__init__.py`'s own docstring for why only that one
provider's ids are a direct model-id match for this harness's own routing.

Round 5i part 1 adds `providers/catalog/models_dev_openai_fallback.json`
the same way (fetch, keep just the `openai` provider entry, trim each
row's fields -- see `load_vendored_openai_fallback`/`openai_profile_
fields_from_models_dev` below) -- the `oai:` route's own direct model-id
match, same reasoning as the Databricks file.
"""

from __future__ import annotations

import http.client
import json
import re
import socket
import ssl
import urllib.parse
from pathlib import Path
from typing import Optional

MODELS_DEV_BASE_URL = "https://models.dev"


def fetch_models_dev(base_url: str = MODELS_DEV_BASE_URL) -> dict:
    """GET {base_url}/api.json; returns the FULL provider->models dict
    unchanged (no trimming here -- callers decide what to keep). Raises
    providers.http.UpstreamConnectError on connect/DNS failure, same
    vocabulary as every other probe in this package. 1.0.1 hotfix 2: bounded
    at `open_upstream`'s own default connect timeout (<=8s). 1.0.1 hotfix
    12: sends a real `User-Agent` -- verified live: models.dev's own CDN
    answers 403 to Python's bare default urllib agent string; this
    (header-less, `http.client`-based) request happened to pass today, but
    that's the CDN's own current rule, not a guarantee -- naming ourselves
    properly is what curl/every other client already does."""
    from halo_harness import __version__
    from halo_harness.providers.http import format_connect_error, open_upstream, UpstreamConnectError
    parsed = urllib.parse.urlparse(base_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    tls = parsed.scheme == "https"
    path = parsed.path.rstrip("/") + "/api.json"
    headers = {"Accept-Encoding": "identity", "User-Agent": f"halo/{__version__}"}
    conn = None
    try:
        conn = open_upstream(host, port, tls)
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
    except (OSError, socket.timeout, ssl.SSLError, http.client.HTTPException) as e:
        raise UpstreamConnectError(format_connect_error(host, e), host=host) from e
    finally:
        # NEW (H9 post-acceptance): a one-shot GET+read-fully-then-done
        # call -- nothing ever closed `conn`, leaking one socket per call
        # until GC (a real ResourceWarning, verified). Same fix as
        # providers/databricks.py's own one-shot probe functions.
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    if resp.status != 200:
        raise RuntimeError(f"models.dev /api.json returned {resp.status}")
    data = json.loads(raw.decode("utf-8", "replace"))
    if not isinstance(data, dict):
        raise RuntimeError("models.dev /api.json did not return a JSON object")
    return data


def refresh_models_dev_cache(state_dir) -> "tuple[bool, str]":
    """1.0.1 hotfix 12: `fetch_models_dev` + `write_models_dev_json` in one
    best-effort call -- used by EVERY `--refresh`/`/models refresh` surface
    now (not just `halo models --refresh`, which already did this
    directly), so a Databricks row's ctx/output/price columns (sourced from
    this SAME cache -- `model_display.databricks_row_fields`) get fresh
    data whenever the user refreshes from any of them, not only the CLI.
    Never raises: `(False, "<reason>")` on any failure, the existing cache
    (if any) is left completely untouched either way."""
    try:
        fetched = fetch_models_dev()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    write_models_dev_json(state_dir, fetched)
    return True, f"cached {len(fetched)} provider(s)"


def models_dev_json_path(state_dir) -> Path:
    return Path(state_dir) / "models-dev.json"


def write_models_dev_json(state_dir, data: dict) -> None:
    """Cache the FULL fetched dict verbatim. Best-effort; swallows OSError
    (a doctor/refresh failure to WRITE the cache is a warning, never a
    crash -- same contract as every other write_*_json in this package)."""
    try:
        Path(state_dir).mkdir(parents=True, exist_ok=True)
        with open(models_dev_json_path(state_dir), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass


def load_models_dev_json(state_dir) -> dict:
    path = models_dev_json_path(state_dir)
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _vendored_catalog_dir() -> Path:
    return Path(__file__).resolve().parent / "catalog"


def load_vendored_databricks_fallback() -> dict:
    """The package-shipped `{databricks-model-id: {...}}` dict (models.dev's
    own `databricks` provider entry, trimmed and committed to the repo) --
    {} if the file is somehow missing/unparseable (a fresh-enough install
    problem, never a crash)."""
    path = _vendored_catalog_dir() / "models_dev_databricks_fallback.json"
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def load_vendored_openrouter_fallback() -> dict:
    """The package-shipped OpenRouter fallback (same shape as
    `providers.databricks.load_models_json`'s own output) -- {} if missing/
    unparseable."""
    path = _vendored_catalog_dir() / "openrouter_fallback.json"
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def load_vendored_openai_fallback() -> dict:
    """Halo 2.0.3 round 5i part 1: the package-shipped `{openai-model-id:
    {...}}` dict -- models.dev's own `openai` provider entry (53 ids,
    confirmed live 2026-10-04, `docs/harness/OPENAI-RESEARCH.md`), trimmed
    to id/name/family/description/attachment/reasoning/reasoning_options/
    tool_call/structured_output/temperature/knowledge/release_date/
    last_updated/modalities/open_weights/limit(context,output)/cost(input,
    output,cache_read,cache_write) -- same trim shape `load_vendored_
    databricks_fallback` ships, minus `cost.tiers`/`context_over_200k`/
    `canonical_model_id`/`experimental`, which `oai:` never needs. {} if
    the file is somehow missing/unparseable."""
    path = _vendored_catalog_dir() / "models_dev_openai_fallback.json"
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def openai_entries_from_full_models_dev(raw: dict) -> dict:
    """The `openai` twin of `databricks_entries_from_full_models_dev` --
    navigates the FULL `models.dev/api.json` shape down to just the
    `openai` provider's `{model_id: entry}` map. `{}` for anything
    unexpected -- never raises."""
    provider = raw.get("openai") if isinstance(raw, dict) else None
    models = provider.get("models") if isinstance(provider, dict) else None
    return models if isinstance(models, dict) else {}


def openai_profile_fields_from_models_dev(entry: dict) -> dict:
    """One models.dev `openai` provider model entry -> the subset of
    `model.ModelProfile` fields it can supply -- same field mapping as
    `databricks_profile_fields_from_models_dev` (USD-per-million-token
    `cost` values divided down to per-token here); kept as its own
    function (rather than sharing one generic helper) to match this
    module's existing one-function-per-provider style. Never raises on a
    malformed entry."""
    out: dict = {}
    limit = entry.get("limit") if isinstance(entry.get("limit"), dict) else {}
    if isinstance(limit.get("context"), int):
        out["context_tokens"] = limit["context"]
    if isinstance(limit.get("output"), int):
        out["max_output_tokens"] = limit["output"]
    modalities = entry.get("modalities") if isinstance(entry.get("modalities"), dict) else {}
    input_modalities = modalities.get("input")
    if isinstance(input_modalities, list):
        out["vision"] = "image" in input_modalities
    if isinstance(entry.get("reasoning"), bool):
        out["reasoning"] = "openai" if entry["reasoning"] else "none"
    cost = entry.get("cost") if isinstance(entry.get("cost"), dict) else {}
    if isinstance(cost.get("input"), (int, float)):
        out["price_in"] = cost["input"] / 1_000_000
    if isinstance(cost.get("output"), (int, float)):
        out["price_out"] = cost["output"] / 1_000_000
    if isinstance(cost.get("cache_read"), (int, float)):
        out["price_cache_read"] = cost["cache_read"] / 1_000_000
    if isinstance(cost.get("cache_write"), (int, float)):
        out["price_cache_write"] = cost["cache_write"] / 1_000_000
    return out


def databricks_entries_from_full_models_dev(raw: dict) -> dict:
    """H9 whole-tree review finding 22: navigates the FULL, untrimmed
    `models.dev/api.json` shape (`{<provider_id>: {..., "models": {<model_
    id>: <entry>, ...}}, ...}` -- confirmed by `doctor`'s own "models.dev
    cached (223 providers)" count of top-level keys) down to just the
    `databricks` provider's `{model_id: entry}` map -- the SAME shape
    `load_vendored_databricks_fallback()` already returns (that file is a
    one-time, committed TRIM of exactly this same navigation, done by
    hand at release time), so a caller can feed either one through
    `databricks_profile_fields_from_models_dev` unchanged. `{}` for
    anything unexpected -- never raises."""
    provider = raw.get("databricks") if isinstance(raw, dict) else None
    models = provider.get("models") if isinstance(provider, dict) else None
    return models if isinstance(models, dict) else {}


def databricks_profile_fields_from_models_dev(entry: dict) -> dict:
    """One models.dev `databricks` provider model entry -> the subset of
    `model.ModelProfile` fields it can actually supply. Never raises on a
    malformed entry -- returns whatever it could parse, {} at worst."""
    out: dict = {}
    limit = entry.get("limit") if isinstance(entry.get("limit"), dict) else {}
    if isinstance(limit.get("context"), int):
        out["context_tokens"] = limit["context"]
    if isinstance(limit.get("output"), int):
        out["max_output_tokens"] = limit["output"]
    modalities = entry.get("modalities") if isinstance(entry.get("modalities"), dict) else {}
    input_modalities = modalities.get("input")
    if isinstance(input_modalities, list):
        out["vision"] = "image" in input_modalities
    if isinstance(entry.get("reasoning"), bool):
        out["reasoning"] = "native" if entry["reasoning"] else "none"
    cost = entry.get("cost") if isinstance(entry.get("cost"), dict) else {}
    # models.dev prices are USD per MILLION tokens; ModelProfile wants USD
    # per single token, matching OpenRouter's own pricing.prompt/completion
    # units (providers.databricks.probe_openrouter_models).
    if isinstance(cost.get("input"), (int, float)):
        out["price_in"] = cost["input"] / 1_000_000
    if isinstance(cost.get("output"), (int, float)):
        out["price_out"] = cost["output"] / 1_000_000
    # H5c Extra (from the H8 must-do list): models.dev's databricks provider
    # entries carry a real cache_read/cache_write breakdown for every Claude
    # row (confirmed in providers/catalog/models_dev_databricks_fallback.json
    # -- e.g. sonnet-4-5: input 3, output 15, cache_read 0.3, cache_write
    # 3.75, same USD-per-million units as input/output above).
    if isinstance(cost.get("cache_read"), (int, float)):
        out["price_cache_read"] = cost["cache_read"] / 1_000_000
    if isinstance(cost.get("cache_write"), (int, float)):
        out["price_cache_write"] = cost["cache_write"] / 1_000_000
    return out


# ---------------------------------------------------------------------------
# Halo 2.0.4 round 5 (plans/ROADMAP.md "ADDED 2026-10-05 ~11:40": "2.0.4
# provider-pack round 'Databricks enumeration'"): models.dev's own
# `databricks` provider entry (above) lists only 30 ids and lacks every
# endpoint newer than that snapshot -- but the VENDOR providers in the SAME
# models.dev dump (anthropic, google, deepseek, zai, ...) carry those
# families under their OWN, un-prefixed model ids. This section builds the
# normalized vendor id a raw Databricks (or OpenRouter/Experiential, same
# gap per round 5's "new labs coverage" deliverable 2) id guesses at, and
# looks it up there -- a "family fallback," not a per-model table, so a
# brand-new endpoint this harness has never seen a row for still shows real
# context/output/price instead of blanks, marked "vendor list price" since
# the vendor's own list price can differ from what Databricks/the gateway
# actually bills per token.
# ---------------------------------------------------------------------------

# A single digit immediately before AND after a dash, with no OTHER digit
# touching either side (`(?<!\d)`/`(?!\d)`) -- turns a version-looking
# "-4-5-"/"-3-5-"/"-5-3-"/"v4-1-" into "-4.5-"/"-3.5-"/"-5.3-"/"v4.1-"
# (every example the roadmap section gives) while leaving a PARAMETER-COUNT
# id like "gemma-3-12b" untouched: the "1" there is followed by another
# digit ("2"), so the right-hand `(?!\d)` guard never matches it as a
# standalone single digit. Applied in a loop (not one `re.sub` pass) so a
# hypothetical three-number chain ("4-5-6") still converges on "4.5.6"
# rather than stopping after the first, non-overlapping match.
_VERSION_DASH_RE = re.compile(r"(?<!\d)(\d)-(\d)(?!\d)")


def normalize_vendor_slug_punctuation(slug: str) -> str:
    """`opus-4-5` -> `opus-4.5`, `gemini-3-5-flash` -> `gemini-3.5-flash`,
    `glm-5-3` -> `glm-5.3`, `deepseek-v4-1-flash` -> `deepseek-v4.1-flash`
    (every roadmap example); `gemma-3-12b` is returned UNCHANGED (see
    `_VERSION_DASH_RE`'s own comment). Never raises -- `slug` is returned
    as-is for anything that isn't a non-empty string."""
    if not isinstance(slug, str) or not slug:
        return slug
    for _ in range(4):  # bounded -- a real model id never chains deeper than this
        new_slug = _VERSION_DASH_RE.sub(r"\1.\2", slug)
        if new_slug == slug:
            return slug
        slug = new_slug
    return slug


# Bedrock-style cross-region external endpoint id, e.g. `us-anthropic-
# claude-sonnet-4-5-20250929-v1-0` -- `databricks.probe_databricks_
# endpoints_full`'s own `foundation_model.name` can carry one of these for
# a Claude passthrough/system.ai endpoint. Captures the vendor segment and
# the model slug separately from the trailing `<8-digit-date>-v<major>-
# <minor>` version stamp, which carries no vendor-catalog-lookup meaning of
# its own and must be stripped before the slug is recognizable.
_EXTERNAL_ENDPOINT_ID_RE = re.compile(
    r"^(?:us|eu|apac|global)-(?P<vendor>[a-z0-9]+)-(?P<slug>.+)-(?P<date>\d{8})-v\d+-\d+$"
)


def parse_external_endpoint_id(raw_id) -> "Optional[tuple[str, str]]":
    """`(vendor, normalized_slug)` for a Bedrock-style external endpoint id
    (`us-anthropic-claude-sonnet-4-5-20250929-v1-0` -> `("anthropic",
    "claude-sonnet-4.5")`), else `None` -- including for anything that
    isn't a plain string, or doesn't match the `<region>-<vendor>-<slug>-
    <8-digit-date>-v<major>-<minor>` shape at all (every endpoint name that
    ISN'T one of these Bedrock-style ids, which is most of them)."""
    if not isinstance(raw_id, str):
        return None
    m = _EXTERNAL_ENDPOINT_ID_RE.match(raw_id)
    if not m:
        return None
    return m.group("vendor"), normalize_vendor_slug_punctuation(m.group("slug"))


# roadmap section's own named examples: "anthropic claude-opus-5 / sonnet-5,
# google gemini-3.5-flash, deepseek deepseek-v4-flash / -pro, zai
# glm-5.3-flash" -- a bare PREFIX guess against an already-"databricks-"-
# stripped, already-punctuation-normalized slug, consulted only once
# neither an exact id match NOR an external-endpoint-id parse found
# anything. Gemma is Google's own open-weight family (same provider entry
# as Gemini in models.dev), hence two prefixes -> "google".
_FAMILY_VENDOR_PREFIXES = (
    ("claude-", "anthropic"),
    ("gemini-", "google"),
    ("gemma-", "google"),
    ("deepseek-", "deepseek"),
    ("glm-", "zai"),
)


def guess_vendor_family(normalized_slug) -> "Optional[str]":
    """The models.dev provider id a bare, un-prefixed model slug probably
    belongs to, by the slug's own leading family name -- `None` when
    nothing in `_FAMILY_VENDOR_PREFIXES` matches (an unrecognized family:
    the caller leaves the row blank rather than guess further) or
    `normalized_slug` isn't a string."""
    if not isinstance(normalized_slug, str):
        return None
    low = normalized_slug.lower()
    for prefix, vendor in _FAMILY_VENDOR_PREFIXES:
        if low.startswith(prefix):
            return vendor
    return None


# OpenRouter vendor segments (the part of a `<vendor>/<slug>` id before the
# slash) that spell a models.dev provider id differently from models.dev's
# own key -- tried AFTER the verbatim vendor segment itself, never instead
# of it, so a segment that already matches a real models.dev provider id
# is never second-guessed.
_OPENROUTER_VENDOR_ALIASES = {"z-ai": "zai", "meta-llama": "meta"}


def vendor_family_profile_fields(raw_model_id, full_models_dev: dict, *,
                                  foundation_model_name=None, vendor_hint=None) -> "Optional[dict]":
    """Halo 2.0.4 round 5: the family-fallback lookup `plans/ROADMAP.md`'s
    "Databricks enumeration" section describes, generalized to the
    identical gap on `or:`/`xp:` ids (round 5's "new labs coverage"
    deliverable 2 -- "the same gap Databricks had"). Tries, in this order,
    the first candidate `(vendor, slug)` pair that resolves to a real entry
    in `full_models_dev` (the FULL, untrimmed `models-dev.json` shape --
    every provider, not just one already-filtered family):

      1. `foundation_model_name` parsed as a Bedrock-style external id.
      2. `raw_model_id` parsed the same way.
      3. `vendor_hint` (an OpenRouter `vendor/slug` id's own vendor
         segment, tried verbatim, then through `_OPENROUTER_VENDOR_
         ALIASES`) paired with `raw_model_id`'s slug half (after the
         slash), normalized.
      4. `foundation_model_name`, stripped of a leading "databricks-" and
         normalized, with the vendor GUESSED from its own prefix.
      5. `raw_model_id`, the same way.

    Returns `databricks_profile_fields_from_models_dev`'s own field dict
    (context/output/vision/reasoning/price -- that function reads a plain
    models.dev entry and has nothing Databricks-specific inside it) plus
    `"price_source": "vendor_list_price"`, so a caller can mark the row;
    `None` when nothing above found a matching provider+model id, or
    `full_models_dev` itself is empty/unusable. Never raises."""
    if not isinstance(full_models_dev, dict) or not full_models_dev:
        return None

    def _entry_for(vendor, slug):
        if not vendor or not slug:
            return None
        provider = full_models_dev.get(vendor)
        models = provider.get("models") if isinstance(provider, dict) else None
        return models.get(slug) if isinstance(models, dict) else None

    candidates: "list[tuple]" = []
    for candidate_id in (foundation_model_name, raw_model_id):
        parsed = parse_external_endpoint_id(candidate_id)
        if parsed:
            candidates.append(parsed)
    if vendor_hint and isinstance(raw_model_id, str) and "/" in raw_model_id:
        slug_half = normalize_vendor_slug_punctuation(raw_model_id.split("/", 1)[1])
        candidates.append((vendor_hint, slug_half))
        aliased = _OPENROUTER_VENDOR_ALIASES.get(vendor_hint)
        if aliased:
            candidates.append((aliased, slug_half))
    for candidate_id in (foundation_model_name, raw_model_id):
        if not isinstance(candidate_id, str):
            continue
        stripped = candidate_id[len("databricks-"):] if candidate_id.startswith("databricks-") else candidate_id
        normalized = normalize_vendor_slug_punctuation(stripped)
        candidates.append((guess_vendor_family(normalized), normalized))

    for vendor, slug in candidates:
        entry = _entry_for(vendor, slug)
        if isinstance(entry, dict):
            fields = databricks_profile_fields_from_models_dev(entry)
            if fields:
                fields["price_source"] = "vendor_list_price"
                return fields
    return None
