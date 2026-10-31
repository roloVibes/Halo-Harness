"""halo_harness.providers.model_card -- Halo 3.3.5.0 R0b: what each model IS,
and how Halo talks to it.

    card_of(ref, *, state_dir, catalog=None, host=None, probe=None, host_card=None) -> Card

Card = {ref, name, host, kind ("ollama" | "llama-server" | "lmstudio" | "mlx" |
"openai-local" | "cloud"), thinks ("yes" | "no" | "default-on"), tools
("declared" | "probed" | "none" | "unknown"), vision, embedding_only, purpose
("coder" | "instruct" | "reasoning" | "vision" | "embedding" | "unknown"),
family, params (billions), quant, window (`agent/model_window.window_of`'s
dict), dialect ("native" | "openai" | the cloud route's), how [lines], fit_for
{orchestrator, coder, reviewer, small, eyes}, fit_why {role: line}, speed
(None: R5 measures it), sources {field: where it came from}, quirks [{kind, say}]
(3.3.5.0 R4: what the server log said, providers/model_card_quirks.py)}.

Sources, per field, in this order: the `/api/show` row (`capabilities`,
`details.family`, `model_info`), the tool-call probe's cache
(`ollama_capability`), the family rules (`model_card_purpose`), the name. A
cloud model gets a card from the catalog row's modalities (purpose instruct
unless the row says it reasons). Nothing here sends a request: the catalog is
the one passed in or the one this process already cached; the probe is the
cache file. The card is kept in the catalog row (`card`, `card_at`) and made
again when the row, the probe or the window changes.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from halo_harness.providers import model_card_purpose as P
from halo_harness.providers.model_card_purpose import parse_ref  # noqa: F401  (the one ref parser, kept importable here)

ORCHESTRATOR_WINDOW = 32768
SMALL_PARAMS = 9.0
ROLES = ("orchestrator", "coder", "reviewer", "small", "eyes")
CLOUD_DIALECTS = {"ant": "anthropic", "anthropic": "anthropic", "or": "openai", "openrouter": "openai", "oai": "openai",
                  "openai": "openai", "dbx": "databricks", "databricks": "databricks"}


def _row_for(catalog, model: str) -> Optional[dict]:
    if not isinstance(catalog, dict):
        return None
    if isinstance(catalog.get("models"), list):
        from halo_harness.providers.ollama import ollama_names_match
        return next((r for r in catalog["models"] if isinstance(r, dict) and (
            ollama_names_match(r.get("model"), model) or ollama_names_match(r.get("name"), model))), None)
    return catalog


def _ollama_host(ref, host):
    if host is not None:
        return host
    try:
        from halo_harness.providers.ollama import resolve_ollama_host
        return resolve_ollama_host(getattr(ref, "host", None))
    except Exception:
        return None


def _probe_for(state_dir, row, probe) -> Optional[bool]:
    if isinstance(probe, bool) or state_dir is None or not (row or {}).get("digest"):
        return probe if isinstance(probe, bool) else None
    try:
        from halo_harness.providers.ollama_capability import load_capability_cache
        got = (load_capability_cache(state_dir).get(row["digest"]) or {}).get("tool_calls")
    except Exception:
        return None
    return got if isinstance(got, bool) else None


def _hf_kind(ref, row) -> str:
    if getattr(ref, "mlx", False):
        return "mlx"
    runtime = str((row or {}).get("runtime") or "")
    if runtime in ("llama-server", "lmstudio", "mlx"):
        return runtime
    try:
        from halo_harness.providers.local_models_cached import cached_detected_servers
        for s in cached_detected_servers():
            if ref.model in (getattr(s, "model_ids", ()) or ()):
                label = getattr(s, "runtime_label", None)
                if label in ("llama-server", "mlx"):
                    return label
                if str(getattr(s, "base_url", "")).rstrip("/").endswith(":1234"):
                    return "lmstudio"
    except Exception:
        pass
    return "openai-local"


def _window(ref, kind, state_dir, host, row, host_card) -> dict:
    from halo_harness.agent.model_window import window_of
    readers: dict = {"catalog": lambda _h: None}
    if kind == "ollama" and state_dir is not None:
        from halo_harness.providers.ollama_calibrate import lookup_learned_cap
        readers["learned_cap"] = lambda h, m, r=None: lookup_learned_cap(state_dir, host_url=h.url, model=m,
                                                                         digest=(r or {}).get("digest"))
    if kind == "cloud":
        ctx = (row or {}).get("context_tokens")
        readers["cloud"] = (lambda _r: ctx) if isinstance(ctx, int) else (lambda _r: None)
    elif kind != "ollama":  # a local server: what it last reported, never a probe
        from halo_harness.providers.huggingface_local_resolve import served_window_cached
        readers.update(loaded=served_window_cached, props=lambda _r: None, lmstudio=lambda _r: None)
    try:
        return window_of(ref, state_dir=state_dir, host=host, catalog=row or {}, card=host_card, readers=readers)
    except Exception:
        return {"tokens": None, "source": "unknown", "ceiling": None, "ceiling_source": "", "kind": kind}


def _local_facts(ref, row, probe) -> dict:
    caps = row.get("capabilities") if isinstance((row or {}).get("capabilities"), list) and row["capabilities"] else None
    details = (row or {}).get("details") if isinstance((row or {}).get("details"), dict) else {}
    family, fam_src = P.family_of(ref.model, details)
    purpose, purpose_src = P.purpose_of(ref.model, caps, family)
    thinks, thinks_src = P.thinks_of(ref.model, caps, family)
    low = {str(c).lower() for c in caps or ()}
    if probe is True:
        tools, tools_src = "probed", "the tool-call probe made a call"
    elif probe is False:
        tools, tools_src = "none", "the tool-call probe got no call"
    elif caps is not None:
        tools, tools_src = ("declared", "/api/show capabilities") if "tools" in low else ("none", "/api/show capabilities: no tools")
    else:
        tools, tools_src = "unknown", "the server does not say"
    if caps is not None:
        vision, vision_src = "vision" in low or bool((row or {}).get("projector_info")), "/api/show capabilities"
    else:
        vision, vision_src = P.name_rule(ref.model) == "vision", "the name"
    return {"thinks": thinks, "tools": tools, "vision": vision, "purpose": purpose, "family": family,
            "embedding_only": purpose == "embedding", "caps": caps,
            "sources": {"thinks": thinks_src, "tools": tools_src, "vision": vision_src, "purpose": purpose_src,
                        "family": fam_src}}


def _cloud_facts(ref, row) -> dict:
    row = row or {}
    mods = row.get("modalities_in") if isinstance(row.get("modalities_in"), list) else None
    reasons = isinstance(row.get("reasoning"), dict) and row["reasoning"].get("kind") in ("native", "openai")
    t = row.get("tools")
    family, fam_src = P.family_of(ref.model, None)
    purpose = P.name_rule(ref.model) or "instruct"
    return {"thinks": "yes" if reasons else "no", "vision": bool(mods and "image" in mods),
            "tools": "declared" if t is True else "none" if t is False else "unknown",
            "purpose": purpose, "family": family, "embedding_only": purpose == "embedding", "caps": None,
            "sources": {"thinks": "the catalog's reasoning" if row else "unknown", "tools": "the catalog" if t is not None else
                        "the catalog does not say", "vision": "the catalog's modalities" if mods is not None else "unknown",
                        "purpose": ("the name" if P.name_rule(ref.model) else "a cloud model: instruct unless its name says "
                                    "otherwise"), "family": fam_src}}


def fit_of(card: dict) -> "tuple[dict, dict]":
    """`fit_for` and `fit_why` (the one reason a role is not a fit)."""
    purpose, tools, w = card["purpose"], card["tools"], (card.get("window") or {}).get("tokens")
    words = {"coder": "a coding model: it writes code; an orchestrator plans, acts and delegates",
             "vision": "a vision model: it reads images; an orchestrator plans, acts and delegates"}
    why: dict = {}
    if card["embedding_only"]:
        why = {r: "an embedding model: it turns text into vectors and does not chat" for r in ROLES}
    else:
        if tools == "none":
            why["orchestrator"] = "no tool calling on this server: it can write and answer but cannot act"
        elif isinstance(w, int) and w < ORCHESTRATOR_WINDOW:
            why["orchestrator"] = (f"its window here is {w:,} ({card['window'].get('source')}), under the "
                                   f"{ORCHESTRATOR_WINDOW:,} an orchestrator needs")
        elif purpose in words:
            why["orchestrator"] = words[purpose]
        if purpose in ("reasoning", "vision"):
            why["coder"] = ("a reasoning model: better at planning and review than at writing code" if purpose == "reasoning"
                            else "a vision model: it reads images rather than writing code")
        p = card.get("params")
        if p is None:
            why["small"] = "its size is unknown"
        elif p > SMALL_PARAMS:
            why["small"] = f"{p:g}B, over the {SMALL_PARAMS:g}B a small model holds"
        if not card["vision"]:
            why["eyes"] = "no vision: images reach it as captions"
    return {r: r not in why for r in ROLES}, why


def _key(raw, row, probe, choice, window, host_card) -> str:
    r = row or {}
    budget = sum(int(g.get("total_bytes") or 0) for g in (host_card or {}).get("gpus") or [] if isinstance(g, dict))
    return json.dumps([raw, r.get("digest"), r.get("modified_at"), r.get("capabilities"), r.get("size"), probe, choice,
                       window.get("tokens"), window.get("source"), budget], default=str)


def card_of(ref, *, state_dir=None, catalog=None, host=None, probe=None, host_card=None) -> dict:
    """See the module docstring."""
    from halo_harness.providers.model_card_words import how_lines
    ref = parse_ref(ref)
    raw = getattr(ref, "raw", "") or ""
    provider = getattr(ref, "provider", "")
    if provider == "ollama":
        kind = "ollama"
        host = _ollama_host(ref, host)
        if catalog is None and host is not None:
            from halo_harness.providers.local_models_cached import cached_catalog
            catalog = cached_catalog(host)
        dialect = "native"
        try:
            from halo_harness.providers.ollama import host_is_openai_dialect
            dialect = "openai" if host_is_openai_dialect(host) else "native"
        except Exception:
            pass
    elif provider == "local" or (provider == "huggingface" and (getattr(ref, "local", False) or getattr(ref, "mlx", False))):
        kind, dialect = None, "openai"
    else:
        kind, dialect = "cloud", CLOUD_DIALECTS.get(provider, provider)
    row = _row_for(catalog, ref.model) if catalog is not None else None
    if kind is None:
        kind = _hf_kind(ref, row) if provider == "huggingface" else "openai-local"
    probe = _probe_for(state_dir, row, probe) if kind == "ollama" else (probe if isinstance(probe, bool) else None)
    window = _window(ref, kind, state_dir, host, row, host_card)
    from halo_harness.providers.effort_on import think_choice_for
    choice = think_choice_for(raw)
    key = _key(raw, row, probe, choice, window, host_card)
    from halo_harness.providers.model_card_quirks import with_quirks  # 3.3.5.0 R4: what the server log said
    if isinstance(row, dict) and isinstance(row.get("card"), dict) and row.get("card_key") == key:
        return with_quirks(row["card"], state_dir)
    facts = _cloud_facts(ref, row) if kind == "cloud" else _local_facts(ref, row, probe)
    details = (row or {}).get("details") if isinstance((row or {}).get("details"), dict) else {}
    params, params_src = P.params_of(ref.model, details, (row or {}).get("model_info"))
    quant, quant_src = P.quant_of(ref.model, details)
    card = {"ref": raw, "name": ref.model, "host": getattr(host, "name", None) or getattr(ref, "host", None),
            "kind": kind, "thinks": facts["thinks"], "tools": facts["tools"], "vision": facts["vision"],
            "embedding_only": facts["embedding_only"], "purpose": facts["purpose"], "family": facts["family"],
            "params": params, "quant": quant, "window": window, "dialect": dialect, "think_choice": choice,
            "speed": None, "sources": {**facts["sources"], "params": params_src, "quant": quant_src,
                                       "window": window.get("source") or "unknown", "row": "/api/show" if row else "none"}}
    card["thinks_source"], card["purpose_source"] = card["sources"]["thinks"], card["sources"]["purpose"]
    card["fit_for"], card["fit_why"] = fit_of(card)
    card["how"] = how_lines(card)
    if isinstance(row, dict) and kind != "cloud":
        row["card"], row["card_at"], row["card_key"] = card, time.time(), key
    return with_quirks(card, state_dir)
