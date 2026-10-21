"""halo_harness.studio.models_fallback -- the refs the model select offers
beside the live catalog (Halo 3.1.4.0 R4: "the dropdown always has the refs
the user already uses").

`GET models/fallback` answers `{rows, in_use, shipped}`: every model ref named
in config.json (`model`, `roles.*`), in a bio (`models.preference` /
`fallback`) or in a lineup card (`agents[].models.*`) that the live catalog
lacks, and -- when OpenRouter is set up (the session's resolution,
catalog_env) but has no live list -- Halo's shipped OpenRouter list
(models_dev.load_vendored_openrouter_fallback). Each row has the catalog row's
shape plus `verified: false` and `source` ("in use" | "shipped"); its detail
says where it comes from. "Test" in the select tells whether a ref answers.
"""

from __future__ import annotations

from halo_harness import agents_yaml as A
from halo_harness import teams_yaml as T

_PREFIX = {"or": "openrouter", "ol": "ollama", "dbx": "databricks", "db": "databricks", "ant": "anthropic", "oai": "openai",
           "hf": "huggingface", "xp": "experiential"}


def provider_of(ref: str) -> str:
    head, sep, _rest = ref.partition(":")
    return _PREFIX.get(head, "other") if sep else "other"


def _refs_of(models) -> list:
    if isinstance(models, str):
        return [models]
    if not isinstance(models, dict):
        return []
    return [str(models[k]) for k in ("preference", "fallback", "model") if isinstance(models.get(k), str) and models.get(k)]


def in_use(state_dir, cwd=None) -> dict:
    """{ref: [where, ...]} for every model ref config.json, the bios and the lineups name."""
    from halo_harness.theme import get_config_value
    out: dict = {}

    def add(ref: str, where: str) -> None:
        ref = str(ref or "").strip()
        if ref and ":" in ref and where not in out.setdefault(ref, []):
            out[ref].append(where)

    add(get_config_value("model", "") or "", "config.json model")
    roles = get_config_value("roles", default={})
    for role, v in (roles.items() if isinstance(roles, dict) else ()):
        for ref in _refs_of(v):
            add(ref, f"config.json roles.{role}")
    for name in A.list_agent_bios(cwd=cwd, state_dir=state_dir):
        try:
            bio = A.load_agent_bio_raw(name, cwd=cwd, state_dir=state_dir) or {}
        except Exception:
            continue
        for ref in _refs_of(bio.get("models")):
            add(ref, f"bio {name}")
    for name in T.list_team_templates(cwd=cwd, state_dir=state_dir):
        try:
            raw = T.load_team_template_raw(name, cwd=cwd, state_dir=state_dir) or {}
        except Exception:
            continue
        for e in raw.get("agents") or []:
            if isinstance(e, dict):
                for ref in _refs_of(e.get("models")):
                    add(ref, f"lineup {name} ({e.get('as') or e.get('role') or e.get('agent') or '?'})")
    return out


def _row(ref: str, detail: str, source: str, *, price_in=None, price_out=None, context_tokens=None, facts=None) -> dict:
    """3.1.9.0 R1: `local` is `is_local_model_ref` (hf:local / hf:mlx too);
    a shipped OpenRouter row carries what its entry states and `best_at`."""
    from halo_harness.capabilities import capability_profile
    from halo_harness.capabilities_line import best_at_kinds, best_at_line
    from halo_harness.model import is_local_ref_string
    from halo_harness.model_display import format_price_per_m, format_token_count
    provider = provider_of(ref)
    base = {"ref": ref, "provider": provider, "price_in_per_m": price_in, "price_out_per_m": price_out,
            "context_tokens": context_tokens, "local": is_local_ref_string(ref), **(facts or {})}
    return {"ref": ref, "provider": provider, "group": "", "detail": detail, "price_in": price_in, "price_out": price_out,
            "price": format_price_per_m(price_in) or "?", "context": format_token_count(context_tokens) or "?",
            "context_tokens": context_tokens, "speed": "?", "local": base["local"],
            "chips": capability_profile(base)["chips"] if facts else "?",
            **{k: base.get(k) for k in ("modalities_in", "modalities_out", "tools", "reasoning")},
            "best_at": {"line": best_at_line(base), "kinds": best_at_kinds(base)},
            "verified": False, "source": source}


def _per_m(v):
    try:
        return float(v) * 1_000_000 if v is not None and not isinstance(v, bool) else None
    except (TypeError, ValueError):
        return None


def fallback_rows(state_dir, cwd, live_refs: set, env: dict) -> dict:
    used = in_use(state_dir, cwd)
    rows = [_row(ref, "not verified: named in " + ", ".join(where[:3]) + (f" (+{len(where) - 3} more)" if len(where) > 3 else ""), "in use")
            for ref, where in sorted(used.items()) if ref not in live_refs]
    shipped = False
    try:
        from halo_harness.providers.enablement import credentials_present, is_enabled
        or_on = is_enabled("openrouter", detected=credentials_present("openrouter", env=env))
    except Exception:
        or_on = False
    if or_on and not any(r.startswith("or:") for r in live_refs):
        from halo_harness.providers.model_row_facts import openrouter_facts
        from halo_harness.providers.models_dev import load_vendored_openrouter_fallback
        seen = {r["ref"] for r in rows}
        for mid, m in sorted(load_vendored_openrouter_fallback().items()):
            ref = "or:" + mid
            if ref in live_refs or ref in seen or not isinstance(m, dict):
                continue
            pricing = m.get("pricing") if isinstance(m.get("pricing"), dict) else {}
            rows.append(_row(ref, "not verified: Halo's shipped OpenRouter list (Refresh for the live one)", "shipped",
                             price_in=_per_m(pricing.get("prompt")), price_out=_per_m(pricing.get("completion")),
                             context_tokens=m.get("context_length") if isinstance(m.get("context_length"), int) else None,
                             facts=openrouter_facts(m)))
            shipped = True
    return {"rows": rows, "in_use": len(used), "shipped": shipped}
