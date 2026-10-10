"""halo_harness.providers.model_enumeration -- Halo 2.0.4 round 4
(deliverable 1): the ONE merged-model-list builder `Controller.
list_models()` (the live `/model`/`/roles`/`/org` picker) and the roles
wizard's own post-keys-step live enumeration both share, so neither ever
grows a second copy of "every provider the picker knows, grouped and
labelled the same way" (the brief's own "do not duplicate the picker's
data source; share it").

`build_model_rows` is `Controller.list_models()`'s old method body,
unchanged line for line apart from reading `state_dir`/`env`/`routes` and
the "current session model" fields as plain parameters instead of `self.
*` attributes -- a pure, cache-only, synchronous read (no network of its
own), safe to call from the UI thread exactly like `list_models()` always
was. `Controller.list_models()` below is now a two-line wrapper around it.

`enumerate_live` is the NEW piece the wizard needs: unlike `build_model_
rows`, it actually REFRESHES every provider's catalog/login status first
(bounded, off whichever thread the caller already runs this from -- see
its own docstring), then hands the result to `build_model_rows` so a row
it returns is built by the exact same code. The wizard's own worker is
the only caller today; `halo doctor`/a future caller can reuse it too.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional


def build_model_rows(state_dir, *, env: "Optional[dict]" = None, routes: "Optional[dict]" = None,
                      current_ref: str = "", current_context_tokens=None, current_max_output_tokens=None,
                      current_provider: "Optional[str]" = None) -> list:
    """`[{ref, context_tokens, max_output_tokens, price_in_per_m,
    price_out_per_m, provider, group, detail, dbu}, ...]` for the
    ModelPicker/init picker -- from the same models.json/dbx-endpoints.
    json + routes.json aliases the resolver uses, so a pick is
    guaranteed to resolve. 1.0.1 hotfix 12: prices are ALWAYS USD per
    MILLION tokens now (`model_display.format_price_per_m`'s own unit),
    normalized at the source here regardless of which raw unit the
    underlying catalog used, so every row -- OpenRouter, cc:, Databricks
    alike -- renders through the exact same `model_display.
    format_model_row` with no per-provider special-casing left at
    render time.

    `env`: the resolver environment (`Settings.effective_env` for a real
    Controller; a merged "saved config plus whatever's typed but not yet
    saved this wizard run" dict for `enumerate_live` below; bare
    `os.environ` when `None`, same fallback every per-provider `resolve_*`
    already applies on its own). `current_ref`/`current_context_tokens`/
    `current_max_output_tokens`/`current_provider`: the session's own
    already-resolved model, inserted as row 0 when it isn't already in
    the catalog -- all default to "nothing to insert" (the wizard has no
    session yet, so it never passes these)."""
    from halo_harness.providers.databricks import load_models_json
    from halo_harness.providers.enablement import credentials_present, is_enabled, label_for, label_with_prefix

    # H15 item 21.2: one dim hint entry (never a selectable `ref`) per
    # provider that's DETECTED (real credentials/login) but not yet
    # ENABLED -- `tui/dialogs/model_picker.py` renders these as a
    # disabled row at the bottom instead of a selectable model.
    hints: "list[dict]" = []

    def _maybe_hint(name: str, *, detected: "Optional[bool]" = None) -> None:
        is_detected = credentials_present(name, env=env) if detected is None else detected
        if is_enabled(name, detected=is_detected) or not is_detected:
            return
        hints.append({"hint": f"{label_for(name)} detected but not enabled -- "
                               f"run `halo providers enable {name}`"})

    def _per_m(price_per_token) -> "float | None":
        # 1.0.1 fixpass finding 7: models.json stores EVERY OpenRouter
        # price as a STRING (e.g. "0.0000008", confirmed across all 464
        # cached entries) -- float(v) in a try/except, same as the
        # pre-1.0.1 code, so a numeric string is never treated as
        # unknown and every row's price columns go blank.
        if isinstance(price_per_token, bool):
            return None
        try:
            return float(price_per_token) * 1_000_000
        except (TypeError, ValueError):
            return None

    out: list = []
    seen = set()
    # H15 item 21.2: an openrouter alias is a `vendor/model` string with
    # no `or:` prefix of its own -- still gated the same way, so a
    # disabled OpenRouter never leaks its catalog through the routes.json
    # alias table either.
    or_detected = credentials_present("openrouter", env=env)
    or_enabled = is_enabled("openrouter", detected=or_detected)
    try:
        models = load_models_json(state_dir) or {} if or_enabled else {}
    except Exception:
        models = {}
    for name in sorted(models):
        entry = models.get(name) or {}
        ref = f"or:{name}"
        seen.add(ref)
        pricing = entry.get("pricing") or {}
        out.append({
            "ref": ref, "context_tokens": entry.get("context_length") or 128000,
            "max_output_tokens": entry.get("max_output_tokens") or 16384,
            "price_in_per_m": _per_m(pricing.get("prompt")), "price_out_per_m": _per_m(pricing.get("completion")),
            "provider": "openrouter",
        })
    _maybe_hint("openrouter", detected=or_detected)
    if or_enabled:
        for alias, target in sorted(((routes or {}).get("aliases") or {}).items()):
            if alias not in seen:
                out.append({"ref": alias, "provider": "alias", "target": target})
    # H11 Part A: the "Claude Code subscription" group (H15 part C's
    # own label, see providers/enablement.py LABELS) -- the cc:
    # aliases, with real profile data when known (providers.cc_models.
    # CC_MODEL_TABLE / a --refresh cache), so they filter/sort/price
    # alongside every OpenRouter row above instead of needing a
    # separate picker. 1.0.1 hotfix addendum 12: group label shortened
    # from "Claude subscription (via Claude Code)" so a full row still
    # fits in 110 columns.
    #
    # 1.0.1 hotfix addendum 9: shown ONLY when the subscription route is
    # actually available -- `claude auth status` reports a real
    # claude.ai login (`SUBSCRIPTION_AUTH_METHODS`, the SAME check
    # `init_cli.py::_claude_login_available`/`model.py`'s bare-alias
    # resolver already use). Verified live: a Databricks WORK box had
    # `claude` logged in via its OWN work settings (authMethod !=
    # "claude.ai") -- the old, unconditional version listed nine cc:
    # models here that a `cc:<name>` call would then refuse at request
    # time, with no hint from the picker that they'd never work.
    # 1.0.1 fixpass finding 1: `cached_claude_auth_status()`, never the
    # real `claude_auth_status()` -- this function is rebuilt on every
    # `/model` open; calling the real one here meant spawning a
    # `claude auth status` subprocess (up to a 10s timeout) synchronously
    # every single time, measured as the single largest piece of a
    # 2-5s TUI freeze on a real work box. Only a startup worker
    # (tui/app.py's on_mount) ever populates that cache now.
    from halo_harness.providers.cc_models import CC_ALIASES, SUBSCRIPTION_AUTH_METHODS, alias_display_detail, \
        cached_claude_auth_status, profile_fields_for_cc_model
    try:
        status = cached_claude_auth_status()
    except Exception:
        status = None
    cc_available = bool(status and status.logged_in and status.auth_method in SUBSCRIPTION_AUTH_METHODS)
    # 1.0.1 part 2 fixpass critical finding 2: `detected=cc_available`
    # -- `cc_available` is the EXACT SAME signal `credentials_present
    # ("claude_subscription")` would compute (a real claude.ai login),
    # just already read from the cache above; without this, both
    # `is_enabled("claude_subscription")` calls below independently
    # re-derived it via `credentials_present` -> `claude_login_
    # available()` -> an UNCACHED `claude auth status` SPAWN apiece --
    # 2 extra subprocess launches (up to a 10s timeout each) every
    # single `/model` open, reintroducing exactly what fixpass finding
    # 1 removed from `cc_available` itself just above.
    # H15 item 21.2/21.6: shown only once the Claude subscription is ALSO
    # enabled -- a real claude.ai login no longer lists cc: models on its
    # own (item 21.1: a login never enables anything by itself).
    # Halo 2.0.7 round 7b: the subscription-consent gate runs BEFORE
    # enablement -- "cc:/cx: are not offered until accepted" (the owner's
    # own wording) applies even to a detected-and-enabled login. A detected
    # login while the routes are off gets its own "available after
    # acceptance" hint instead of the usual "detected but not enabled" one
    # (which would be misleading -- enabling it changes nothing while the
    # consent gate is still closed).
    from halo_harness.subscription_consent import is_accepted as _subs_accepted
    subs_accepted = _subs_accepted()
    if cc_available and subs_accepted and is_enabled("claude_subscription", detected=cc_available):
        for alias, cc_target in CC_ALIASES.items():
            ref = f"cc:{alias}"
            if ref in seen:
                continue
            fields = profile_fields_for_cc_model(cc_target) or {}
            out.append({
                "ref": ref, "context_tokens": fields.get("context_tokens"),
                "max_output_tokens": fields.get("max_output_tokens"),
                "price_in_per_m": _per_m(fields.get("price_in")), "price_out_per_m": _per_m(fields.get("price_out")),
                # H15 addendum 2: "-> <resolved-id>" next to the alias.
                "detail": alias_display_detail(alias),
                "provider": "cc", "group": label_with_prefix("claude_subscription"),
            })
    elif cc_available and not subs_accepted:
        hints.append({"hint": f"{label_for('claude_subscription')} detected -- available after acceptance "
                               f"(run `halo subscriptions accept`)"})
    elif cc_available and not is_enabled("claude_subscription", detected=cc_available):
        hints.append({"hint": f"{label_for('claude_subscription')} detected but not enabled -- "
                               f"run `halo providers enable claude_subscription`"})
    # H15 item 21: the `ant:` (direct Anthropic API key) group -- the
    # same nine subscription-model aliases as cc: above, resolved
    # against the real API instead of the installed `claude` binary.
    # Never shown before this item (no gate existed to hide it behind),
    # so this is also the group's first appearance in `/model` at all.
    from halo_harness.providers.config import resolve_anthropic
    ant_available = resolve_anthropic(env) is not None
    if ant_available and is_enabled("anthropic", detected=ant_available):
        from halo_harness.init_providers import _cc_ant_entries
        from halo_harness.providers.cc_models import ANT_ALIASES
        ant_group = label_with_prefix("anthropic")
        for entry in _cc_ant_entries("ant", ANT_ALIASES):
            if entry["ref"] in seen:
                continue
            out.append({**entry, "provider": "anthropic", "group": ant_group})
        # Halo 2.0.4 round 3 (deliverable 3): "the picker groups read
        # the same cache" -- `halo models --ant`'s own live catalog
        # (`ant-models.json`, written by `refresh_anthropic_catalog_
        # if_stale`/`halo models --ant --refresh`/`halo models
        # --refresh`), not just the nine pinned aliases above, so an id
        # this key can reach that this harness never named gets a real,
        # pickable row instead of staying invisible until someone
        # hand-types it. A pure file read (no network), same first-
        # paint-safe gate as every other group in this function.
        try:
            from halo_harness.providers.anthropic_catalog import load_ant_models_json
            live_ant = load_ant_models_json(state_dir)
        except Exception:
            live_ant = {}
        alias_targets = set(ANT_ALIASES.values())
        for model_id in sorted(live_ant):
            if model_id in alias_targets:
                continue  # already shown above, under its own alias name
            ref = f"ant:{model_id}"
            if ref in seen:
                continue
            seen.add(ref)
            out.append({"ref": ref, "provider": "anthropic", "group": ant_group})
    elif ant_available:
        hints.append({"hint": f"{label_for('anthropic')} detected but not enabled -- "
                               f"run `halo providers enable anthropic`"})
    # H14 scope I: the discovered Databricks endpoint catalog
    # (~/.halo/dbx-endpoints.json, from `init --preset work`/
    # `models --refresh` -- never a vendored list), grouped by family,
    # each row showing its chosen path type and DBU rate when known;
    # a known non-chat endpoint (embeddings/whisper) is hidden here
    # (`halo models` itself still lists it, for diagnostics).
    dbx_detected = credentials_present("databricks", env=env)
    dbx_enabled = is_enabled("databricks", detected=dbx_detected)
    # deliverable 6: "Databricks (dbx:)" is the canonical label every
    # OTHER group on this page now uses too (label_with_prefix) --
    # Databricks keeps its own family sub-grouping (useful on a real
    # catalog with dozens of endpoints) as a " -- <family>" suffix
    # rather than losing it, so "Databricks (dbx:) -- qwen"/"...  --
    # judge / decision" reads as the same provider, further divided.
    dbx_group_label = label_with_prefix("databricks")
    try:
        from halo_harness.providers.databricks import dbx_endpoints_cache_is_old_shape, load_dbx_endpoints_json
        from halo_harness.providers.dbx_routing import (
            PATH_TYPE_DISPLAY, classify_family, default_path_type, format_dbu_cost,
        )
        endpoints = load_dbx_endpoints_json(state_dir) if dbx_enabled else {}
    except Exception:
        endpoints = {}
    _maybe_hint("databricks", detected=dbx_detected)
    # 1.0.1 hotfix 4/addendum 10: an old-shape cache (no `api_types` ever
    # recorded) makes `default_path_type` silently degrade to
    # "invocations" for every openai-chat family -- checked ONCE here,
    # same migration signal `catalog_cli.py`'s own table uses, so this
    # picker never shows that wrong answer as if it were real data.
    old_shape = dbx_endpoints_cache_is_old_shape(endpoints)
    from halo_harness.model_display import databricks_row_fields
    from halo_harness.providers.profiles import decision_only_info, load_model_table
    model_table = load_model_table()
    # 1.0.1 fixpass finding 1: loaded ONCE for the whole loop below, not
    # once per endpoint (databricks_row_fields's own `live_models_dev`/
    # `vendored_fallback` params) -- models-dev.json can be several MB;
    # 30 Databricks rows on a real catalog re-read and re-parsed the
    # same file 30 times (1.37s measured on a fast host) before this.
    try:
        from halo_harness.providers.models_dev import (
            databricks_entries_from_full_models_dev, load_models_dev_json, load_vendored_databricks_fallback,
        )
        # Halo 2.0.4 round 5: the SAME full dict `databricks_entries_from_
        # full_models_dev` above filters down to just the `databricks`
        # provider, kept here too (unfiltered) for the family-fallback
        # tier's OWN lookup under a vendor's own top-level key -- loaded
        # and parsed exactly ONCE for the whole loop below, never once per
        # endpoint (the identical "fixpass finding 1" reasoning the two
        # pre-existing params just above were already added for).
        full_models_dev = load_models_dev_json(state_dir)
        live_models_dev = databricks_entries_from_full_models_dev(full_models_dev)
        vendored_fallback = load_vendored_databricks_fallback()
    except Exception:
        live_models_dev, vendored_fallback, full_models_dev = {}, {}, {}
    for name in sorted(endpoints):
        ref = f"dbx:{name}"
        if ref in seen:
            continue
        e = endpoints[name] if isinstance(endpoints[name], dict) else {}
        family = classify_family(name, foundation_model_name=e.get("foundation_model_name") or "",
                                  model_class=e.get("model_class") or "")
        if family == "non_chat":
            continue
        if old_shape:
            path_type = "unknown"
        else:
            try:
                path_type = default_path_type(name, state_dir)
            except Exception:
                path_type = "?"
        usage_policy = e.get("usage_policy") if isinstance(e.get("usage_policy"), dict) else {}
        dbu = format_dbu_cost(usage_policy.get("output_dbu_per_1k_tokens"))
        try:
            fields = databricks_row_fields(name, state_dir=state_dir, model_table=model_table,
                                            live_models_dev=live_models_dev, vendored_fallback=vendored_fallback,
                                            full_models_dev=full_models_dev,
                                            foundation_model_name=e.get("foundation_model_name"))
        except Exception:
            fields = {}
        path_display = PATH_TYPE_DISPLAY.get(path_type, path_type)
        # Halo 2.0.4 round 5 (deliverable 1): "rows show a 'vendor list
        # price' marker when the figure comes from the fallback" / "use
        # [task, foundation model name, state] to fill the model name and
        # availability" -- appended to the SAME detail string the picker
        # already shows in brackets after the row, never a new column.
        detail_suffixes = []
        if fields.get("price_source") == "vendor_list_price":
            detail_suffixes.append("vendor list price")
        if e.get("ready") is False:
            detail_suffixes.append("not ready")
        # Halo 2.0.2 round 5 (Qwen-at-work brief, item 1): a decision-
        # only/judge endpoint (databricks-openjev-qwen35-4b and any
        # future one `decision_only_info`'s own table/pattern match
        # recognizes) groups separately from its family's ordinary
        # chat rows -- "the picker shows it under a 'judge / decision'
        # group with that note" -- never silently listed as if it
        # were just another qwen chat model.
        decision = decision_only_info(name, model_table)
        detail = decision["reason"] if decision else f"{family} · {path_display}"
        if detail_suffixes:
            detail = f"{detail}, {', '.join(detail_suffixes)}"
        out.append({
            "ref": ref, "context_tokens": fields.get("context_tokens"),
            "max_output_tokens": fields.get("max_output_tokens"),
            "price_in_per_m": fields.get("price_in_per_m"), "price_out_per_m": fields.get("price_out_per_m"),
            "provider": "databricks",
            "group": f"{dbx_group_label} -- judge / decision" if decision else f"{dbx_group_label} -- {family}",
            "path_type": path_type,
            "detail": detail,
            "dbu": dbu if dbu != "?" else None,
            "task": e.get("task"),
        })
    # Halo 2.0.3 round 4 (brief item 4): the router's cached catalog
    # (`huggingface-models.json`, a pure file read -- the background
    # worker that WRITES it, tui/slash.py's `catalog_auto_refresh_
    # worker`, is the only thing that ever touches the network, and
    # only post-first-paint) -- "router models appear in the picker
    # under a Hugging Face group when the route is enabled" /
    # "keep the first paint of the picker unaffected when the token is
    # absent (no network)": `hf_enabled` gates the read exactly like
    # `or_enabled` gates OpenRouter's own `load_models_json` above, so
    # an unconfigured Hugging Face costs this function nothing.
    hf_detected = credentials_present("huggingface", env=env)
    hf_enabled = is_enabled("huggingface", detected=hf_detected)
    try:
        from halo_harness.providers.huggingface_catalog import load_hf_models_json
        hf_models = load_hf_models_json(state_dir) or {} if hf_enabled else {}
    except Exception:
        hf_models = {}
    # Halo 2.0.4 round 3 (deliverable 1 fix, owner live report
    # 2026-10-05: "hugging face in models does not show the costs or
    # context prices"): the router's real per-provider shape means
    # `entry`'s own context_length/pricing (and now first_token_
    # latency_ms/throughput/is_free) are whatever `huggingface_
    # catalog._parse_catalog_entry` already chose from the cheapest
    # LIVE provider at cache-write time -- `hf_picker_fields` is the
    # ONE place that reads them, same as every other group's own
    # picker-fields helper (`xp_picker_fields`/`oai_picker_fields`).
    from halo_harness.providers.huggingface_catalog import hf_picker_fields
    for name in sorted(hf_models):
        ref = f"hf:{name}"
        if ref in seen:
            continue
        entry = hf_models.get(name) or {}
        fields = hf_picker_fields(entry)
        out.append({
            "ref": ref, "context_tokens": fields.get("context_tokens"),
            "max_output_tokens": None,
            "price_in_per_m": fields.get("price_in_per_m"), "price_out_per_m": fields.get("price_out_per_m"),
            "speed_ttft_s": fields.get("speed_ttft_s"), "speed_tokens_per_second": fields.get("speed_tokens_per_second"),
            "provider": "huggingface", "group": label_with_prefix("huggingface"),
        })
    _maybe_hint("huggingface", detected=hf_detected)

    # Halo 2.0.3 round 5i part 1: the real OpenAI API's own cached id
    # list (`GET /v1/models`, no price/context of its own -- docs/
    # harness/OPENAI-RESEARCH.md section 3) -- price/context merged
    # in from the SEPARATE models.dev cross-check (`providers.openai_
    # catalog.oai_picker_fields`), same source `model.resolve_model_
    # profile`'s own "openai" branch uses. Same first-paint-safe gate
    # as the huggingface group just above: a pure file read, gated on
    # enablement, never a network call from this function itself.
    oai_detected = credentials_present("openai", env=env)
    oai_enabled = is_enabled("openai", detected=oai_detected)
    try:
        from halo_harness.providers.openai_catalog import load_oai_models_json, oai_picker_fields
        oai_models = load_oai_models_json(state_dir) or {} if oai_enabled else {}
    except Exception:
        oai_models = {}
    for name in sorted(oai_models):
        ref = f"oai:{name}"
        if ref in seen:
            continue
        fields = oai_picker_fields(name, state_dir)
        out.append({
            "ref": ref, "context_tokens": fields.get("context_tokens"),
            "max_output_tokens": None,
            "price_in_per_m": fields.get("price_in_per_m"), "price_out_per_m": fields.get("price_out_per_m"),
            "provider": "openai", "group": label_with_prefix("openai"),
        })
    _maybe_hint("openai", detected=oai_detected)

    # Halo 2.0.4 round 2: the "Experiential Labs" group -- unlike the
    # huggingface/openai groups just above, this gateway's own `GET
    # /v1/models` carries real context/price/capability fields
    # DIRECTLY (`providers.experiential_catalog`), so there is no
    # separate models.dev cross-check tier; `load_xp_models_json`
    # falls back to the vendored snapshot on a fresh install with no
    # cache file yet, so the group is never empty just because `/model`
    # hasn't been refreshed once. Same first-paint-safe gate (pure file
    # read, gated on enablement) as every group above.
    xp_detected = credentials_present("experiential", env=env)
    xp_enabled = is_enabled("experiential", detected=xp_detected)
    try:
        from halo_harness.providers.experiential_catalog import load_xp_models_json, xp_picker_fields
        xp_models = load_xp_models_json(state_dir) or {} if xp_enabled else {}
    except Exception:
        xp_models = {}
    for name in sorted(xp_models):
        ref = f"xp:{name}"
        if ref in seen:
            continue
        fields = xp_picker_fields(name, state_dir)
        badge = fields.get("data_policy_badge")
        owned_by = fields.get("owned_by")
        detail_parts = [p for p in (owned_by, badge) if p]
        # "a $0 preview model shows 'free (preview)'" -- `format_
        # price_per_m` alone renders the bare word "free"; this adds
        # the qualifier here, in the detail bracket next to it.
        if fields.get("is_free_preview"):
            detail_parts.append("free (preview)")
        detail = " · ".join(detail_parts) or None
        out.append({
            "ref": ref, "context_tokens": fields.get("context_tokens"),
            "max_output_tokens": fields.get("max_output_tokens"),
            "price_in_per_m": fields.get("price_in_per_m"), "price_out_per_m": fields.get("price_out_per_m"),
            "provider": "experiential", "group": label_with_prefix("experiential"), "detail": detail,
        })
    _maybe_hint("experiential", detected=xp_detected)

    # Halo 2.0.3 round 5i part 2: the "Codex subscription (ChatGPT)"
    # group -- the `cx:` counterpart of the "Claude Code subscription"
    # block above, substituting `codex_models.cached_codex_auth_
    # status()` for `cc_models.cached_claude_auth_status()`. Shown
    # only once a real ChatGPT login is BOTH detected AND enabled, same
    # two-gate rule every subscription route on this page already
    # follows (a login never enables anything on its own).
    from halo_harness.providers.codex_models import (
        CODEX_ALIASES, alias_display_detail as cx_alias_display_detail, cached_codex_auth_status,
        profile_fields_for_codex_model,
    )
    try:
        cx_status = cached_codex_auth_status()
    except Exception:
        cx_status = None
    cx_available = bool(cx_status and cx_status.logged_in and cx_status.auth_method == "chatgpt")
    if cx_available and subs_accepted and is_enabled("codex_subscription", detected=cx_available):
        for alias in CODEX_ALIASES:
            ref = f"cx:{alias}"
            if ref in seen:
                continue
            fields = profile_fields_for_codex_model(alias) or {}
            out.append({
                "ref": ref, "context_tokens": fields.get("context_tokens"),
                "max_output_tokens": fields.get("max_output_tokens"),
                "price_in_per_m": None, "price_out_per_m": None,
                "detail": cx_alias_display_detail(alias),
                "provider": "codex", "group": label_with_prefix("codex_subscription"),
            })
    elif cx_available and not subs_accepted:
        hints.append({"hint": f"{label_for('codex_subscription')} detected -- available after acceptance "
                               f"(run `halo subscriptions accept`)"})
    elif cx_available and not is_enabled("codex_subscription", detected=cx_available):
        hints.append({"hint": f"{label_for('codex_subscription')} detected but not enabled -- "
                               f"run `halo providers enable codex_subscription`"})

    # C-2 finding 11: `ol:`/`hf:local/*`/`hf:mlx/*` never appeared here
    # at all, so `/model`/the picker/completion could never reach a
    # local model by name -- reuses the SAME shared discovery `halo
    # local`/`/local` already use (`providers.local_models.
    # build_local_view`) rather than re-deriving it, so a row this
    # picker shows is guaranteed to be the one `/local` already
    # reports; `refresh=False` (the default) matches every other group
    # above's own "first paint from whatever is already known/cached,
    # no live probe just from opening the picker" rule. Ollama is
    # deliberately ungated here (same as `/local`/`halo doctor --local`
    # -- round 2/3's own choice to keep it outside the generic
    # provider-enablement table, see providers/enablement.py). Only a
    # row with a real, addressable `ref` becomes a picker entry -- a
    # "(unreachable)"/"(no models reported)"/"(configured -- /local
    # refresh to check)" placeholder row (every one of this view's own
    # "nothing to pick yet" sentinels starts with "(", never a real
    # model id) is `/local`-only, exactly like a hint row here has no
    # `ref` either. Halo 2.0.4 round 3 (owner live report, 2026-10-05:
    # "also cover hf:local/*and hf:mlx/* rows (free, context from the
    # probe)"): local compute has a KNOWN price -- $0, never unknown
    # -- so `price_in_per_m`/`price_out_per_m` are 0 here (the picker's
    # own `format_price_per_m` already renders exactly 0 as "free",
    # round 2's own fix), not `None` (which would show "?" and
    # misdescribe a known fact as an unpublished one); `context_tokens`
    # already comes from `row.context`, the SAME local probe `/local`/
    # `halo doctor --local` read, unchanged by this round.
    try:
        from halo_harness.providers.local_models import build_local_view
        local_rows = build_local_view(env=env, state_dir=state_dir)
    except Exception:
        local_rows = []
    for row in local_rows:
        if not row.ref or row.ref in seen or row.name.startswith("("):
            continue
        seen.add(row.ref)
        out.append({
            "ref": row.ref, "context_tokens": row.context, "max_output_tokens": None,
            "price_in_per_m": 0, "price_out_per_m": 0,
            "provider": "ollama" if row.ref.startswith("ol:") else "huggingface",
            "group": row.group, "detail": row.capability,
        })

    current = current_ref
    if current and current not in {m["ref"] for m in out}:
        out.insert(0, {"ref": current, "context_tokens": current_context_tokens,
                       "max_output_tokens": current_max_output_tokens,
                       "provider": current_provider})
    # Halo 2.0.4 round 3 (deliverable 1): the picker's "speed" column --
    # computed ONCE for the whole batch (never per-row: `providers.
    # speed.speed_by_ref`'s own docstring is why this stays a single
    # cache-only read, keeping this function's documented "UI thread,
    # synchronous, cheap" contract regardless of the catalog's size),
    # then applied to every row that has a real `ref` -- OpenRouter,
    # cc:, ant:, dbx:, hf:, oai:, xp:, cx:, ol: alike, so "the same
    # layout in every group" (the brief's own wording) also means the
    # same speed SOURCE in every group, not just the same columns.
    try:
        from halo_harness.providers.speed import speed_by_ref
        speeds = speed_by_ref(state_dir)
    except Exception:
        speeds = {}
    if speeds:
        for m in out:
            ref = m.get("ref")
            entry = speeds.get(ref) if ref else None
            if entry:
                m["speed_ttft_s"] = entry.get("ttft_s")
                m["speed_tokens_per_second"] = entry.get("tokens_per_second")
    # H15 item 21.2: dim, non-selectable hint rows (no "ref" at all) go
    # LAST -- after the `current` insertion above, which indexes `out`
    # by `m["ref"]` and would KeyError on a hint dict otherwise.
    out.extend(hints)
    return out


# ---------------------------------------------------------------------------
# Live enumeration -- the roles wizard's own counterpart of the cache-only
# `build_model_rows` above (deliverable 1: "the wizard runs one off-thread
# enumeration ... every provider ... Show one progress line per provider as
# it answers; a provider that is not reachable gets a 'not reachable' row
# and never blocks the step").
# ---------------------------------------------------------------------------

# Belt-and-suspenders bound on top of whatever connect/idle timeout each
# provider's own HTTP call already has (`providers/http.py`'s
# `DEFAULT_CONNECT_TIMEOUT_S = 8`, an idle timeout past that) -- this is
# the MOST this function will ever wait, in total, regardless of how many
# providers are configured or how many of them hang: every job starts in
# parallel, and whichever ones are still running once this many seconds
# have passed are reported "not reachable (timed out)" and left running
# quietly in the background (they are daemon threads; Python cannot
# cancel a running thread, but a wizard step -- or the whole process --
# exiting never waits on one).
LIVE_ENUMERATION_TIMEOUT_S = 20.0

_CATALOG_PROVIDERS = ("openrouter", "anthropic", "databricks", "huggingface", "openai", "experiential")


def _catalog_probe(provider: str, state_dir, env: dict) -> "Callable[[], str]":
    def _run() -> str:
        from halo_harness.providers.catalog_refresh import refresh_one_catalog
        result = refresh_one_catalog(provider, state_dir, env=env, force=True)
        if result is None or result.get("ok") is None:
            return "not configured"
        if result.get("ok"):
            count = result.get("count")
            return f"{count} model(s) cached" if isinstance(count, int) else "cached"
        return "not reachable"
    return _run


def _claude_probe() -> str:
    from halo_harness.providers.cc_models import SUBSCRIPTION_AUTH_METHODS, refresh_cached_claude_auth_status
    status = refresh_cached_claude_auth_status()
    return ("logged in" if status and status.logged_in and status.auth_method in SUBSCRIPTION_AUTH_METHODS
            else "not logged in")


def _codex_probe() -> str:
    from halo_harness.providers.codex_models import refresh_cached_codex_auth_status
    status = refresh_cached_codex_auth_status()
    return "logged in" if status and status.logged_in and status.auth_method == "chatgpt" else "not logged in"


def _local_probe(state_dir, env: dict) -> str:
    from halo_harness.providers.local_models import build_local_view
    rows = build_local_view(refresh=True, env=env, state_dir=state_dir)
    reachable = [r for r in rows if r.ref and not r.name.startswith("(")]
    return f"{len(reachable)} model(s) found" if reachable else "not reachable"


def _enumeration_jobs(state_dir, env: dict) -> "list[tuple[str, Callable[[], str]]]":
    """`[(display_label, zero_arg_callable_returning_a_status_string), ...]`
    for every provider `/model` knows -- the exact label set `providers.
    catalog_refresh`'s own six registered catalogs use plus the two
    subscription routes and local/Ollama, built lazily (same reason every
    per-provider branch in this module imports from inside the function,
    never at module scope)."""
    from halo_harness.providers.enablement import label_with_prefix
    jobs: "list[tuple[str, Callable[[], str]]]" = []
    for provider in _CATALOG_PROVIDERS:
        jobs.append((label_with_prefix(provider), _catalog_probe(provider, state_dir, env)))
    jobs.append((label_with_prefix("claude_subscription"), _claude_probe))
    jobs.append((label_with_prefix("codex_subscription"), _codex_probe))
    jobs.append(("Ollama & local servers", lambda: _local_probe(state_dir, env)))
    return jobs


def enumerate_live(state_dir, *, env: "Optional[dict]" = None, routes: "Optional[dict]" = None,
                    progress_cb: "Optional[Callable[[str, str], None]]" = None,
                    timeout_s: float = LIVE_ENUMERATION_TIMEOUT_S) -> list:
    """Refreshes every provider's catalog/login status LIVE (bounded,
    parallel, off whichever thread the caller already runs this from --
    never the UI thread itself), then returns `build_model_rows(state_dir,
    env=env, routes=routes)` so the result is built by the exact same code
    `/model`/`Controller.list_models()` uses -- never a second copy of
    that logic.

    `env`: the credentials to probe WITH -- the wizard's own caller merges
    whatever's typed-but-not-yet-saved this run over the real `os.environ`/
    saved config and passes the result here; this function never writes
    anything to disk or to `os.environ` itself (every per-provider refresh
    call it invokes already follows that same "env in, nothing persisted
    but the provider's own cache file" contract on its own).

    `progress_cb(label, status)` -- when given -- is called once per
    provider job, in whatever order they finish (never blocking job N+1
    on job N); `status` is one of "not configured", "not logged in",
    "<n> model(s) cached"/"found"/"cached", or "not reachable"/"not
    reachable (timed out)". Exceptions from `progress_cb` itself are
    swallowed (a broken UI callback must never take the probe down with
    it); exceptions from a job are caught and reported as "not reachable
    (<ExceptionType>)".

    Bounded: this function returns within approximately `timeout_s`
    wall-clock seconds total no matter how many providers are configured
    or how many of them never answer -- see `LIVE_ENUMERATION_TIMEOUT_S`'s
    own docstring for why a straggler is left running rather than joined."""
    import os as _os
    env = dict(env) if env is not None else dict(_os.environ)
    jobs = _enumeration_jobs(state_dir, env)

    def _wrap(label: str, fn: "Callable[[], str]"):
        def _target() -> None:
            try:
                status = fn()
            except Exception as e:
                status = f"not reachable ({type(e).__name__})"
            if progress_cb is not None:
                try:
                    progress_cb(label, status)
                except Exception:
                    pass
        return threading.Thread(target=_target, name=f"halo-enum-{label}", daemon=True)

    threads = [(_wrap(label, fn), label) for label, fn in jobs]
    reported = set()
    original_cb = progress_cb

    def _progress_once(label: str, status: str) -> None:
        # Guards against reporting the SAME provider twice: a straggler
        # reported "timed out" by the deadline loop below that then goes
        # on to finish anyway (its own thread's `_target` above still
        # calls `progress_cb` on completion -- harmless on its own, but a
        # caller rendering one line per provider would otherwise see two).
        if label in reported:
            return
        reported.add(label)
        if original_cb is not None:
            original_cb(label, status)
    # Every `_target` closure above reads `progress_cb` from THIS function's
    # own scope at CALL time (Python closures resolve free variables when
    # the inner function actually runs, not when it's defined) -- so
    # reassigning it here, before any thread starts, routes every job's
    # own eventual callback through the de-duplicating wrapper too.
    progress_cb = _progress_once

    for t, _label in threads:
        t.start()
    deadline = time.monotonic() + timeout_s
    for t, label in threads:
        remaining = max(0.0, deadline - time.monotonic())
        t.join(remaining)
        if t.is_alive():
            _progress_once(label, "not reachable (timed out)")

    return build_model_rows(state_dir, env=env, routes=routes)
