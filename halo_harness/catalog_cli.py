"""halo_harness.catalog_cli -- `halo models` subcommand (H1 scope I):
lists OpenRouter models (from the cached models.json, refreshing via a live
probe when the cache is empty or --refresh is passed) and Databricks
endpoints (from dbx-endpoints.json), with context/output/price columns, and
near-miss slug correction for a `--model` that doesn't match anything.
"""

from __future__ import annotations

import argparse
import os
import difflib
import json
import sys

from halo_harness.config.paths import bridge_home
from halo_harness.model_display import ROW_HEADER, format_price_per_m, format_token_count
from halo_harness.providers.config import (
    load_provider_env_files, resolve_databricks, resolve_openrouter, derive_workspace_root,
)
from halo_harness.providers.databricks import (
    load_dbx_endpoints_json, load_models_json, probe_openrouter_models, write_models_json,
)
from halo_harness.providers.models_dev import fetch_models_dev, models_dev_json_path, write_models_dev_json


def _fmt_price(v) -> str:
    """USD per token -> "$X.XX/M" (per-million-token, the unit every
    provider's own pricing page uses); "?" for anything unparseable.
    Kept (only) for `--ant`'s own table below, which predates `model_display`
    and still wants "?" (not blank) for an unknown value in ITS OWN
    columns."""
    try:
        return f"${float(v) * 1_000_000:.2f}/M"
    except (TypeError, ValueError):
        return "?"


def near_miss_slug(requested: str, known_ids) -> "list[str]":
    """Ori-style near-miss slug correction (scope I/rule 11): the closest
    known model ids to an unrecognized `--model`, best match first."""
    return difflib.get_close_matches(requested, list(known_ids), n=5, cutoff=0.5)


def _cmd_models_ant(state_dir, *, refresh: bool) -> int:
    """Halo 2.0.4 round 3 (deliverable 3): `halo models --ant` -- the
    `ant:` (direct Anthropic API key) models. `GET /v1/models` IS a real
    enumeration -- this lists every id the configured key can actually
    see (`providers.anthropic_catalog`'s own cache,
    `ant-models.json`), not just the nine pinned aliases, so a model the
    account can reach but this harness never named (a new release, a
    preview) still shows up here the moment a refresh has run. The nine
    aliases still show FIRST, each with its `-> <resolved-id>` detail (the
    alias table never changes `ant:`'s own routing -- see `model.py`'s
    `resolve_ant_alias`), so the common case still reads as a short,
    named list; anything the live catalog adds beyond those nine ids
    follows under its own heading. Never touches the key file -- only
    `providers.config.resolve_anthropic` (env-only) and, with --refresh,
    one bounded `GET /v1/models` call."""
    from halo_harness.providers.anthropic_catalog import (
        ant_models_age_seconds, load_ant_models_json, refresh_anthropic_catalog_if_stale,
    )
    from halo_harness.providers.anthropic_aliases import ANT_ALIASES, alias_display_detail, profile_fields_for_ant_model
    from halo_harness.providers.config import resolve_anthropic
    ant = resolve_anthropic()
    if ant is None:
        print("Anthropic API: not configured (no ANTHROPIC_API_KEY found) -- ant: models unavailable")
    else:
        print(f"Anthropic API: key found ({ant.base_url})")

    if refresh:
        if ant is None:
            print("(skipped -- no ANTHROPIC_API_KEY to refresh with)\n")
        else:
            ok = refresh_anthropic_catalog_if_stale(state_dir, force=True)
            print("(refreshed ant-models.json from GET /v1/models)\n" if ok
                  else "(could not refresh from Anthropic -- the previous cache, if any, is unchanged)\n")

    age = ant_models_age_seconds(state_dir)
    live = load_ant_models_json(state_dir)
    age_text = "never cached" if age is None else f"cached {age / 3600:.1f}h ago"
    print(f"({len(live)} live id(s) known, {age_text} -- `halo models --ant --refresh` updates it)\n")

    print(f"{'alias':<12} {'ant: target':<30} {'context':>10} {'out cap':>9} {'in/M':>9} {'out/M':>9}")
    seen_ids = set()
    for name, target in ANT_ALIASES.items():
        seen_ids.add(target)
        fields = profile_fields_for_ant_model(target) or {}
        ctx = fields.get("context_tokens", "?")
        out_cap = fields.get("max_output_tokens", "?")
        print(f"{name:<12} {alias_display_detail(name):<30} {str(ctx):>10} {str(out_cap):>9} "
              f"{_fmt_price(fields.get('price_in')):>9} {_fmt_price(fields.get('price_out')):>9}")

    extra_ids = sorted(set(live) - seen_ids)
    if extra_ids:
        print(f"\n{len(extra_ids)} more id(s) this key can reach, no alias of their own:")
        for model_id in extra_ids:
            display_name = (live.get(model_id) or {}).get("display_name") or ""
            print(f"  {model_id}" + (f"  ({display_name})" if display_name else ""))
    return 0


def _endpoint_url_for_path_type(root: str, name: str, path_type: str) -> str:
    """The exact URL for an already-computed `path_type` (1.0.1 hotfix 4:
    split out of the old `_endpoint_url_and_path_type` so `_dbx_rows` can
    compute `path_type` ONCE, always, and only additionally build the full
    URL when `--urls` actually asked for it)."""
    if path_type == "anthropic":
        return f"{root}/ai-gateway/anthropic/v1/messages"
    if path_type in ("none", "?"):
        return "(refused -- non-chat endpoint)" if path_type == "none" else "?"
    from halo_harness.providers.dbx_routing import API_TYPE_INFO
    info = API_TYPE_INFO.get(path_type)
    if info is not None:
        return f"{root}{info['path']}"
    return f"{root}/serving-endpoints/{name}/invocations"


def _dbx_rows(endpoints: dict, root: str, state_dir, *, urls: bool) -> dict:
    """1.0.1 hotfix 4: `path_type`/`chat` are now ALWAYS computed (never
    gated behind `--urls`, which used to leave every bare-table row showing
    "path ?" even when a real route existed) and sourced from data the cache
    actually carries: `path_type` is `dbx_routing.default_path_type` (the
    SAME family/api_types decision `chat_route_candidates` makes for a real
    request -- no network call, it's all local), `chat` is
    `dbx_routing.is_chat_task` (the endpoint's own `task`, not a name-based
    family guess). An OLD-SHAPE cache (hotfix 4's own migration -- see
    `databricks.dbx_endpoints_cache_is_old_shape`) shows `path_type="unknown"`
    for every row instead of silently degrading to a wrong "invocations"
    (`chat_route_candidates` can't tell a real invocations-only route from a
    cache that simply never recorded `api_types` at all)."""
    from halo_harness.model_display import databricks_row_fields
    from halo_harness.providers.databricks import dbx_endpoints_cache_is_old_shape
    from halo_harness.providers.dbx_routing import classify_family, default_path_type, is_chat_task
    old_shape = dbx_endpoints_cache_is_old_shape(endpoints)
    rows = {}
    for name, e in endpoints.items():
        family = classify_family(name, foundation_model_name=e.get("foundation_model_name") or "",
                                  model_class=e.get("model_class") or "")
        path_type = "unknown" if old_shape else default_path_type(name, state_dir)
        row = {"family": family, "task": e.get("task"), "chat": is_chat_task(e.get("task")),
               "api_types": e.get("api_types") or [], "path_type": path_type}
        # 1.0.1 hotfix 12: ctx/output/price columns, same
        # models.dev-then-model_table.json-then-blank rule `Controller.
        # list_models()`'s own Databricks rows and the init picker use.
        try:
            row.update(databricks_row_fields(name, state_dir=state_dir))
        except Exception:
            pass
        if urls:
            row["url"] = ("(refresh needed -- cached before this version tracked gateway types)" if old_shape
                           else _endpoint_url_for_path_type(root, name, path_type) if root else "?")
        rows[name] = row
    return rows


def _path_display(path_type: str) -> str:
    """The human-readable `path` column label for the TEXT table only
    (`unknown` -- hotfix 4's old-cache migration marker -- reads as "unknown
    (refresh needed)"; a real route key gets dbx_routing's own
    `mlflow-chat`/`cursor-chat` spelling). `--json`/`--urls`' machine-
    readable `path_type` field is untouched by this -- see `_dbx_rows`."""
    from halo_harness.providers.dbx_routing import PATH_TYPE_DISPLAY
    if path_type == "unknown":
        return "unknown (refresh needed)"
    return PATH_TYPE_DISPLAY.get(path_type, path_type)


def format_dbx_table_lines(rows: dict, *, urls: bool = False) -> "list[str]":
    """The Databricks endpoint table's exact text rendering (name/family/
    path/chat/ctx/out/price[/url] columns) -- ONE implementation shared by
    `halo models`, the headless `/models` (`commands/builtins.py::
    _cmd_models`), and the TUI's own `/models` bare rendering (`tui/
    slash.py`), so the three surfaces can never drift apart on column
    widths or wording. `rows` is `_dbx_rows`'s own per-endpoint dict.

    1.0.1 hotfix 12: ctx/out/price columns (`model_display.
    format_token_count`/`format_price_per_m` -- blank, never "?", when
    unknown) alongside the existing family/path/chat/url diagnostic
    columns this CLI table already had (this command's whole purpose is
    diagnostic depth, so nothing here was REMOVED -- only the `/model`/
    `/models`/init picker surfaces, which show a compact single ref+price
    line per row via `format_model_row`, stay narrower)."""
    header = (f"{'name':<42} {'family':<16} {'path':<18} {'chat':>5} "
              f"{'ctx':>6} {'out':>6} {'in/M':>9} {'out/M':>9}")
    lines = [header + ("  url" if urls else ""), f"  ({ROW_HEADER})"]
    for name in sorted(rows):
        r = rows[name]
        line = (f"{name:<42} {r['family']:<16} {_path_display(r.get('path_type', '?')):<18} "
                f"{('yes' if r['chat'] else 'no'):>5} "
                f"{format_token_count(r.get('context_tokens')):>6} {format_token_count(r.get('max_output_tokens')):>6} "
                f"{format_price_per_m(r.get('price_in_per_m')):>9} {format_price_per_m(r.get('price_out_per_m')):>9}")
        if urls:
            line += f"  {r.get('url', '?')}"
        lines.append(line)
    return lines


def _cmd_models_capabilities(args) -> int:
    """`halo models --capabilities` / `--best-for KIND` (3.0.1.0 D1)."""
    from halo_harness.capabilities import KINDS, best_for, capability_lines
    from halo_harness.providers.config import listing_effective_env, load_provider_env_files, load_routes
    from halo_harness.providers.model_enumeration import build_model_rows
    load_provider_env_files()
    state_dir = bridge_home()
    routes = load_routes(state_dir / "routes.json" if state_dir.exists() else None)
    # 3.1.4.0 R4: the session's resolution (the settings.json env chain too), never a bare os.environ copy
    rows = [r for r in build_model_rows(state_dir, env=listing_effective_env(), routes=routes) if r.get("ref")]
    if args.best_for:
        kind = args.best_for.strip().lower()
        if kind not in KINDS:
            print(f"halo models: --best-for takes one of {', '.join(KINDS)}, not {args.best_for!r}", file=sys.stderr)
            return 2
        ranked = best_for(rows, kind, state_dir=state_dir)
        if not ranked:
            print(f"No model in the catalog states what {kind} needs; `halo models --refresh` updates the catalog.")
            return 1
        print(f"Best for {kind} (from the catalog's own modality, tool, reasoning, context, price and speed facts "
              f"and what this host measured; score 0-1):")
        for i, r in enumerate(ranked, 1):
            print(f"{i:>2}. {r['ref']:<40} {r['score']:.2f}  {r['chips']:<24} {r['reason']}")
        return 0
    print("ref                                      in: what the model accepts  out: what it produces  -- what it is best at "
          "('?' = not stated by the catalog)")
    for line in capability_lines(rows):
        print(line)
    return 0


def cmd_models(argv) -> int:
    if argv and argv[0] == "test":  # 3.0.7.0 R1: `halo models test <ref>`, the one-token probe
        from halo_harness.model_probe import cmd_models_test
        return cmd_models_test(list(argv[1:]))
    if argv and argv[0] == "analyze":  # 3.1.9.0 R1: rebuild what each model is good at
        from halo_harness.models_analyze_cli import cmd_models_analyze
        return cmd_models_analyze(list(argv[1:]))
    if argv and argv[0] == "browse":  # 3.3.5.0 R2: the library browser (models_browse_cli.py)
        from halo_harness.models_browse_cli import cmd_models_browse
        return cmd_models_browse(list(argv[1:]))
    from halo_harness.models_control_cli import VERBS as CONTROL_VERBS  # 3.3.5.0 R3: an Ollama host's models
    if argv and argv[0] in CONTROL_VERBS:
        from halo_harness.models_control_cli import cmd_models_control
        return cmd_models_control(argv[0], list(argv[1:]))
    if argv and argv[0] == "probe":  # 3.3.6.0 R1: the capability battery (models_probe_cli.py)
        from halo_harness.models_probe_cli import cmd_models_probe
        return cmd_models_probe(list(argv[1:]))
    if argv and argv[0] in ("measured", "dialect"):  # 3.3.6.0 R4: the card's measured facts, the dialect record
        from halo_harness import models_card_facts_cli as F
        return (F.cmd_models_measured if argv[0] == "measured" else F.cmd_models_dialect)(list(argv[1:]))
    if argv and argv[0] in ("retire", "shelf"):  # 3.3.6.0 R4: the model shelf (models_shelf_cli.py)
        from halo_harness.models_shelf_cli import cmd_models_shelf
        return cmd_models_shelf(argv[0], list(argv[1:]))
    if argv and argv[0] == "show":  # 3.3.5.0 R0b: the model card
        from halo_harness.model_card_cli import cmd_models_show
        return cmd_models_show(list(argv[1:]))
    parser = argparse.ArgumentParser(prog="halo models", add_help=True)
    parser.add_argument("--refresh", action="store_true", help="Re-probe OpenRouter/Databricks instead of using the cache")
    parser.add_argument("--ant", action="store_true",
                         help="List the real, reachable Anthropic API models (ant: aliases plus every "
                              "other id the key can see) instead of the OpenRouter/Databricks catalog; "
                              "with --refresh, re-fetches GET /v1/models")
    parser.add_argument("--urls", action="store_true",
                         help="Databricks endpoints: also print the exact URL and path type each one resolves to")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    # Halo 2.0.5 round 3 (G1): the blunt, whole-cache reset -- clears every
    # learned PARAMETER-rejection rule (providers.learned_params), on every
    # endpoint, in one go. Pairs naturally with a catalog refresh (a
    # provider-side change that invalidates one likely invalidates others);
    # `halo rules --forget <endpoint>` is the scoped, single-endpoint twin.
    parser.add_argument("--forget-rules", action="store_true",
                         help="Also clear every learned parameter-rejection rule for every endpoint")
    # 3.0.1.0 D1: which model for what -- straight from the catalog's own modality fields.
    parser.add_argument("--capabilities", action="store_true",
                         help="One line per model: what it accepts (text, image, audio, video, pdf), what it outputs "
                              "and what it is best at")
    parser.add_argument("--best-for", metavar="KIND", default="",
                         help="Rank models for one job: visual | audio | video | image | design | pdf | code | research | "
                              "bulk | fast | local (with a reason each); "
                              "image-gen | video-gen | audio-gen | upscale rank the ComfyUI media models")
    # 3.0.4.0 R2: the ComfyUI media-model inventory, keyed by what a model produces (never mixed with the LLM catalog).
    parser.add_argument("--media", nargs="?", const="all", default=None, choices=["image", "video", "audio", "all"],
                         help="List the ComfyUI media models (diffusion, video, upscale, TTS and their LoRAs, VAEs, "
                              "encoders) by what they produce; with --refresh, rescans the server")
    parser.add_argument("--measured", action="store_true",  # 3.1.8.0 R3 (outcomes/measured.py)
                         help="Measured success per model and task kind here: checked tasks, first-time passes, "
                              "the rate and the mean cost (outcomes.jsonl)")
    parser.add_argument("--cards", action="store_true",  # 3.3.5.0 R0b (model_card_cli.py)
                         help="One line per model from its card: think, tools, vision, purpose, window, the roles it "
                              "can hold and its fit here (`halo models show <ref>` prints one card in full)")
    args = parser.parse_args(argv)
    if args.cards:
        load_provider_env_files()
        from halo_harness.model_card_cli import cmd_models_cards
        return cmd_models_cards(as_json=args.json)
    if args.measured:
        from halo_harness.outcomes.cli import cmd_models_measured
        return cmd_models_measured(as_json=args.json)
    from halo_harness.capabilities import OUTPUT_KINDS
    if args.best_for and args.best_for.strip().lower() in OUTPUT_KINDS:
        from halo_harness.catalog_media_cli import cmd_best_for_media
        return cmd_best_for_media(args.best_for.strip().lower(), refresh=args.refresh)
    if args.media is not None:
        from halo_harness.catalog_media_cli import cmd_media_inventory
        return cmd_media_inventory(args.media, refresh=args.refresh, as_json=args.json)
    if args.capabilities or args.best_for:
        return _cmd_models_capabilities(args)

    # 2.0.0 fixpass finding 4: the new env file (2.0.5 round 3: the legacy
    # fallback this comment used to describe was removed -- see
    # providers.config.load_provider_env_files's own docstring).
    load_provider_env_files()

    if args.forget_rules:
        from halo_harness.providers.learned_params import forget_all_param_rules
        cleared = forget_all_param_rules(bridge_home())
        print(f"halo models: forgot learned parameter rules for {cleared} endpoint(s).")

    state_dir = bridge_home()
    if args.ant:
        return _cmd_models_ant(state_dir, refresh=args.refresh)
    # 1.0.1 hotfix 3: bare `halo models` (no --refresh) NEVER touches
    # the network, full stop -- not even "the first time the cache is
    # empty" (the old behavior here). A DNS/VPN-down box
    # must be able to run this to see "nothing cached yet" instantly rather
    # than hanging on an unreachable host it never asked to probe.
    # H15 part 2 addendum 3.2b: `--refresh` refreshes every ENABLED
    # provider's catalog now -- an explicitly-disabled provider (even with
    # real credentials) is left alone, same rule every other surface
    # follows.
    from halo_harness.providers.enablement import is_enabled
    models = load_models_json(state_dir)
    if args.refresh:
        orc = resolve_openrouter() if is_enabled("openrouter") else None
        if orc is not None:
            try:
                fetched = probe_openrouter_models(orc.base_url, orc.api_key)
                write_models_json(state_dir, fetched)
                models = load_models_json(state_dir)
            except Exception as e:
                print(f"halo models: could not refresh from OpenRouter: {e}", file=sys.stderr)

    dbx = resolve_databricks() if is_enabled("databricks") else None
    endpoints = load_dbx_endpoints_json(state_dir)
    dbx_diff = None
    if dbx is not None and args.refresh:
        from halo_harness.providers.databricks import refresh_dbx_catalog
        root = derive_workspace_root(dbx.host)
        ok, diff, note = refresh_dbx_catalog(state_dir, root, dbx.token)
        if ok:
            endpoints = load_dbx_endpoints_json(state_dir)
            dbx_diff = diff
        else:
            print(f"halo models: could not refresh from Databricks: {note}", file=sys.stderr)

    if args.refresh and is_enabled("anthropic"):
        from halo_harness.providers.anthropic_catalog import refresh_anthropic_catalog_if_stale
        ok = refresh_anthropic_catalog_if_stale(state_dir, force=True)
        if ok is False:
            print("halo models: could not refresh from Anthropic", file=sys.stderr)

    if args.refresh and is_enabled("openai"):
        # Pass-B finding 16 (major): `refresh_openai_catalog_if_stale` had
        # no caller anywhere -- `halo models --refresh` skipped OpenAI
        # entirely, same gap `/models refresh` had.
        from halo_harness.providers.openai_catalog import refresh_openai_catalog_if_stale
        ok = refresh_openai_catalog_if_stale(state_dir, force=True)
        if ok is False:
            print("halo models: could not refresh from OpenAI", file=sys.stderr)

    if args.refresh and is_enabled("experiential"):
        # Halo 2.0.4 round 2: same hooks round 5i part 1 wired for OpenAI
        # just above, for the Experiential Labs gateway.
        from halo_harness.providers.experiential_catalog import refresh_experiential_catalog_if_stale
        ok = refresh_experiential_catalog_if_stale(state_dir, force=True)
        if ok is False:
            print("halo models: could not refresh from Experiential Labs", file=sys.stderr)

    # H15 item 21.2: a provider with real credentials but not ENABLED shows
    # one line instead of its table -- same rule `/model`/the init picker/
    # doctor all follow; `halo providers enable <name>` is the fix
    # every one of those surfaces names too.
    from halo_harness.providers.enablement import is_enabled, is_provider_disabled_message
    or_enabled = is_enabled("openrouter")
    dbx_enabled = is_enabled("databricks")

    # 2.0.1 hygiene: doctor's own catalog-age check (`_check_catalog_ages`)
    # already tells the user "models.json: never cached (vendored package
    # fallback still applies)" -- a bare `halo models` with no OpenRouter
    # key/cache printed an empty table right underneath that claim, which
    # read as a flat contradiction. No live cache (and no EXPLICIT
    # `providers disable openrouter` override -- that message already
    # covers the "deliberately off" case) now falls back to the SAME
    # package-vendored rows `resolve_model_profile` itself already
    # consults, clearly labelled as such rather than looking like a live
    # probe.
    or_vendored_fallback = False
    if not models and is_provider_disabled_message("openrouter") is None:
        from halo_harness.providers.models_dev import load_vendored_openrouter_fallback
        vendored = load_vendored_openrouter_fallback()
        if vendored:
            models = vendored
            or_vendored_fallback = True

    # The vendored rows are static package data, not a credential-gated
    # live probe result -- shown whenever there's no explicit "disabled by
    # you" override, same as doctor's own unconditional catalog-age claim,
    # regardless of whether OpenRouter also happens to read as "enabled"
    # (the common fresh-install case: no key yet -> not auto-enabled, but
    # still not explicitly disabled either).
    show_openrouter = or_enabled or or_vendored_fallback

    if args.json:
        payload = {"openrouter": models if show_openrouter else {}}
        if not or_enabled and models and not or_vendored_fallback:
            payload["openrouter_disabled"] = True
        if or_vendored_fallback:
            payload["openrouter_vendored_fallback"] = True
        if dbx is not None:
            if dbx_enabled:
                payload["databricks"] = _dbx_rows(endpoints, derive_workspace_root(dbx.host), state_dir,
                                                    urls=args.urls)
                if dbx_diff is not None:
                    payload["databricks_diff"] = dbx_diff
            elif endpoints:
                payload["databricks_disabled"] = True
        print(json.dumps(payload, indent=2, default=str))
        return 0

    if not or_enabled and models and not or_vendored_fallback:
        print(f"OpenRouter: {len(models)} model(s) cached, but OpenRouter is not enabled -- "
              f"run `halo providers enable openrouter` to show them.")
        models = {}
    if or_vendored_fallback:
        print("OpenRouter models (vendored fallback -- no live cache yet; "
              "set OPENROUTER_API_KEY and run `halo models --refresh` for live pricing):")
    else:
        print("OpenRouter models (models.json):")
    print(f"{'id':<48} {'ctx':>8} {'out':>8} {'in/M':>10} {'out/M':>10}    ({ROW_HEADER})")
    for mid in sorted(models):
        entry = models[mid]
        pricing = entry.get("pricing") or {}
        # 1.0.1 fixpass finding 7: models.json stores EVERY OpenRouter price
        # as a STRING (e.g. "0.0000008") -- float(v) in a try/except, same
        # as the pre-1.0.1 code, so a numeric string is never treated as
        # unknown and this column goes blank.
        def _price_per_m(v) -> "float | None":
            if isinstance(v, bool):
                return None
            try:
                return float(v) * 1_000_000
            except (TypeError, ValueError):
                return None
        print(f"{mid:<48} {format_token_count(entry.get('context_length')):>8} "
              f"{format_token_count(entry.get('max_output_tokens')):>8} "
              f"{format_price_per_m(_price_per_m(pricing.get('prompt'))):>10} "
              f"{format_price_per_m(_price_per_m(pricing.get('completion'))):>10}")
    if models:
        print(f"{len(models)} models")  # 3.3.5.0 R0 (f): every row printed, the count said

    if dbx is not None and endpoints and not dbx_enabled:
        print(f"\nDatabricks: {len(endpoints)} endpoint(s) cached, but Databricks is not enabled -- "
              f"run `halo providers enable databricks` to show them.")
    elif dbx is not None and endpoints:
        root = derive_workspace_root(dbx.host)
        rows = _dbx_rows(endpoints, root, state_dir, urls=args.urls)
        print("\nDatabricks endpoints (dbx-endpoints.json):")
        for line in format_dbx_table_lines(rows, urls=args.urls):
            print(line)
        print(f"{len(endpoints)} endpoints")  # 3.3.5.0 R0 (f): the count line
        if dbx_diff is not None:
            from halo_harness.providers.databricks import format_dbx_diff
            print(f"\nDatabricks catalog diff (this refresh): {format_dbx_diff(dbx_diff)}")

    # H8 scope C: models.dev's api.json is public/unauthenticated -- cached
    # to models-dev.json for doctor's own freshness check and for future
    # model_table.json cross-checking (see providers/models_dev.py). 1.0.1
    # hotfix 3: only ever fetched with --refresh now (see the OpenRouter/
    # Databricks sections above for why "the first time it's empty" no
    # longer triggers a network call on its own).
    models_dev_path = models_dev_json_path(state_dir)
    if args.refresh:
        try:
            fetched = fetch_models_dev()
            write_models_dev_json(state_dir, fetched)
            print(f"\nmodels.dev: cached {len(fetched)} provider(s) to {models_dev_path}")
        except Exception as e:
            # 1.0.1 hotfix 11: names the real failure (often a
            # CERTIFICATE_VERIFY_FAILED at a TLS-inspecting work network --
            # see docs/TROUBLESHOOTING.md) AND says plainly that the
            # vendored/cached catalog stays in use either way -- this was
            # previously just the bare exception, with no indication that
            # nothing else was actually broken by it.
            print(f"halo models: could not refresh from models.dev: {e} "
                  f"-- the vendored/cached models.dev catalog stays in use.", file=sys.stderr)
    return 0
