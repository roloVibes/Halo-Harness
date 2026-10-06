"""halo_harness.providers.catalog_refresh -- Halo 2.0.4 round 3
(deliverable 5): one scheduler for every provider's model catalog, each
provider registering its own {path, age, load, refresh} functions instead
of the SAME is_enabled/import/refresh-if-stale chain being hand-copied in
more than one place (`tui/slash.py::catalog_auto_refresh_worker` -- launch
and every `/model` open -- and `doctor.py`'s own catalog-age report).
H15 part 2 addendum 3.2's own docstring already named this exact module
(`providers.catalog_refresh.refresh_all_enabled_catalogs`) as the combined
scheduler, but it was never actually built -- the six provider branches
stayed duplicated inline instead. This is that piece, finally wired to
both callers; `catalog_cli.py`'s own `halo models --refresh` sequence is
left as its own, already-correct, already-tested implementation (it
prints a much richer per-provider report -- OpenRouter's live table,
Databricks' diff, models.dev's own cache -- that a generic one-line-per-
catalog loop would only flatten, for no real gain).

Every `refresh_fn` here is the exact SAME per-provider `refresh_*_if_
stale(state_dir, *, force=, env=)` function every other caller in this
codebase already uses -- this module adds no new network code of its own,
only ONE place that lists which function is which provider's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class CatalogSpec:
    name: str       # display name, e.g. "OpenRouter"
    provider: str   # providers.enablement canonical name
    path_fn: Callable        # (state_dir) -> Path
    age_fn: Callable         # (state_dir) -> Optional[float] seconds
    load_fn: Callable        # (state_dir) -> dict | list (len() counts rows)
    refresh_fn: Callable     # (state_dir, *, force: bool, env) -> Optional[bool]


def _refresh_databricks(state_dir, *, force: bool, env) -> "Optional[bool]":
    """Databricks' own `refresh_dbx_catalog_if_stale` returns the richer
    `(ok, diff, note)` triple (its diff text is what the TUI's existing
    worker and `halo models --refresh` both already show) -- this module's
    generic contract only needs the plain `ok`/`None` every other
    provider's refresh function already returns directly."""
    from halo_harness.providers.databricks import refresh_dbx_catalog_if_stale
    result = refresh_dbx_catalog_if_stale(state_dir, force=force, env=env)
    return None if result is None else result[0]


def _specs() -> "list[CatalogSpec]":
    """Built lazily, never at import time -- importing this module must
    not pull in every provider submodule up front, same lazy-import
    convention every per-provider branch in `Controller.list_models()`
    already follows."""
    from halo_harness.providers import anthropic_catalog, databricks, experiential_catalog, huggingface_catalog, openai_catalog
    return [
        CatalogSpec("OpenRouter", "openrouter", databricks.models_json_path, databricks.models_json_age_seconds,
                    databricks.load_models_json,
                    lambda sd, *, force, env: databricks.refresh_openrouter_catalog_if_stale(sd, force=force, env=env)),
        CatalogSpec("Anthropic", "anthropic", anthropic_catalog.ant_models_json_path, anthropic_catalog.ant_models_age_seconds,
                    anthropic_catalog.load_ant_models_json,
                    lambda sd, *, force, env: anthropic_catalog.refresh_anthropic_catalog_if_stale(sd, force=force, env=env)),
        CatalogSpec("Databricks", "databricks", databricks.dbx_endpoints_path, databricks.dbx_endpoints_age_seconds,
                    databricks.load_dbx_endpoints_json, _refresh_databricks),
        CatalogSpec("Hugging Face", "huggingface", huggingface_catalog.hf_models_json_path,
                    huggingface_catalog.hf_models_json_age_seconds, huggingface_catalog.load_hf_models_json,
                    lambda sd, *, force, env: huggingface_catalog.refresh_huggingface_catalog_if_stale(sd, force=force, env=env)),
        CatalogSpec("OpenAI", "openai", openai_catalog.oai_models_json_path, openai_catalog.oai_models_json_age_seconds,
                    openai_catalog.load_oai_models_json,
                    lambda sd, *, force, env: openai_catalog.refresh_openai_catalog_if_stale(sd, force=force, env=env)),
        CatalogSpec("Experiential Labs", "experiential", experiential_catalog.xp_models_json_path,
                    experiential_catalog.xp_models_json_age_seconds, experiential_catalog.load_xp_models_json,
                    lambda sd, *, force, env: experiential_catalog.refresh_experiential_catalog_if_stale(sd, force=force, env=env)),
    ]


def catalog_ages(state_dir) -> "list[dict]":
    """`[{"name", "provider", "path", "age_seconds", "count"}, ...]` for
    EVERY registered catalog, regardless of enablement -- a plain file
    read each, never a network call, so this is always cheap and safe to
    call from `halo doctor`/`/providers`. `age_seconds` is `None` when
    the file was never cached at all (doctor's own "never cached" line);
    `count` is 0 for that same case (`len(load_fn(...))` on an empty/
    missing-file read, which every `load_*_json` in this codebase already
    returns as `{}`/`[]` rather than raising)."""
    out = []
    for spec in _specs():
        try:
            age = spec.age_fn(state_dir)
        except Exception:
            age = None
        try:
            count = len(spec.load_fn(state_dir) or ())
        except Exception:
            count = 0
        try:
            path = str(spec.path_fn(state_dir))
        except Exception:
            path = "?"
        out.append({"name": spec.name, "provider": spec.provider, "path": path,
                     "age_seconds": age, "count": count})
    return out


def refresh_all_enabled_catalogs(state_dir, *, env: "Optional[dict]" = None, force: bool = False) -> "list[dict]":
    """One attempt per ENABLED provider's catalog (never for a disabled or
    not-configured one -- the same `is_enabled_with_env` gate every
    existing per-provider branch already applied individually), each
    entry `{"name", "provider", "attempted": bool, "ok": Optional[bool],
    "count": Optional[int]}`: `attempted=False` (nothing else meaningful)
    when this provider isn't enabled; `attempted=True, ok=None` when it IS
    enabled but the cache was fresh enough to skip (not `force`); `ok=True/
    False` for a real attempt, `count` the resulting cache's row count
    (`None` on failure -- the previous cache, if any, is left completely
    untouched by every `refresh_*_if_stale`'s own contract, so showing ITS
    row count on a failed attempt would misleadingly look like progress).
    Never raises: a single provider's exception is caught and reported as
    `ok=False` so one bad catalog can never take the others down with it
    (the SAME contract the individual refresh functions already promise on
    their own, kept here across the whole batch too)."""
    from halo_harness.providers.enablement import is_enabled_with_env
    out = []
    for spec in _specs():
        if not is_enabled_with_env(spec.provider, env):
            out.append({"name": spec.name, "provider": spec.provider, "attempted": False, "ok": None, "count": None})
            continue
        try:
            ok = spec.refresh_fn(state_dir, force=force, env=env)
        except Exception:
            ok = False
        if ok is None:
            out.append({"name": spec.name, "provider": spec.provider, "attempted": True, "ok": None, "count": None})
            continue
        count = None
        if ok:
            try:
                count = len(spec.load_fn(state_dir) or ())
            except Exception:
                count = None
        out.append({"name": spec.name, "provider": spec.provider, "attempted": True, "ok": ok, "count": count})
    return out


def refresh_one_catalog(provider: str, state_dir, *, env: "Optional[dict]" = None, force: bool = True) -> "Optional[dict]":
    """Halo 2.0.4 round 3 (deliverable 1/G4): the picker's own `r`
    ("refresh the current group") -- one provider's catalog, regardless
    of its own enablement state (the picker only ever shows a group that
    is ALREADY enabled, so re-checking here would be redundant; `force`
    defaults to True since an explicit `r` keypress is exactly the
    "I asked for this now" case `/models refresh`/`halo models --refresh`
    already treat as an override). `None` when `provider` names no
    registered catalog at all (cc:/cx:/ol:/local groups have none -- a
    bare alias/host probe, not a live catalog this module fetches) --
    the caller's own job to degrade that into "nothing to refresh here."
    Same per-provider exception safety as `refresh_all_enabled_catalogs`."""
    provider = _canonical_provider(provider)
    for spec in _specs():
        if spec.provider != provider:
            continue
        try:
            ok = spec.refresh_fn(state_dir, force=force, env=env)
        except Exception:
            ok = False
        if ok is None:
            return {"name": spec.name, "provider": spec.provider, "attempted": True, "ok": None, "count": None}
        count = None
        if ok:
            try:
                count = len(spec.load_fn(state_dir) or ())
            except Exception:
                count = None
        return {"name": spec.name, "provider": spec.provider, "attempted": True, "ok": ok, "count": count}
    return None


def _canonical_provider(provider: str) -> str:
    try:
        from halo_harness.providers.enablement import canonical
        return canonical(provider)
    except Exception:
        return provider
