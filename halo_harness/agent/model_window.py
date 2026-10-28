"""halo_harness.agent.model_window -- Halo 3.3.5.0 R0: the window of a model,
with its source.

    window_of(ref, *, state_dir, host=None, catalog=None, card=None, readers=None)
        -> {tokens, source, ceiling, ceiling_source, kind}

The first source that knows a number wins and is named, in this order:

1. the steward profile (`ollama.profiles["<host>|<model>"].num_ctx`)
2. the learned cap (the fit store, `~/.halo/ollama-fit.json`)
3. the server's loaded window: Ollama's `/api/ps` `context_length` (the
   hardware card's `loaded` rows), llama-server's `/props` `n_ctx`, LM
   Studio's model API or a local server's `/v1/models` row
4. the model's trained context: `/api/show` (the catalog row), the Hugging
   Face `config.json` `max_position_embeddings`, mlx-lm's config
5. the host entry's `max_ctx` (or a `local.servers` entry's `context`)
6. the server default (the knowledge's number per server kind)
7. the cloud catalog's context, for a cloud route

A smaller bound the call itself obeys -- the learned cap, the host's
`max_ctx`, what the card fits, Ollama's hard cap -- holds the number and is
named instead ("window 32,768 (host max_ctx)"). `ceiling` is the largest
window this model can get here: the learned cap, else what the card fits
(None when neither is known).

Pure: the lookups are `readers` (a dict of callables, each optional); the
defaults read what a session already reads (the profile, the fit store, the
short-TTL catalogs) and never load a model.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

log = logging.getLogger("bridge")

# the knowledge's number per server kind (ollama_steward/knowledge: Ollama's
# "vram-based default context" is 4,096 under 23 GiB; llama-server's `-c 0`
# and mlx-lm use the trained context, so they name none here)
SERVER_DEFAULTS = {"ollama": 4096, "lmstudio": 4096, "llama-server": None, "mlx": None, "vllm": None, "local": None}
SOURCE_ORDER = ("steward profile", "learned cap", "loaded window", "trained context", "host max_ctx",
                "server default", "cloud catalog")


def _pos(v) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else None


def kind_of(ref) -> str:
    """"ollama" | "hf-local" | "mlx" | "local" | "cloud"."""
    provider = getattr(ref, "provider", "")
    if provider == "ollama":
        return "ollama"
    if provider == "huggingface" and getattr(ref, "mlx", False):
        return "mlx"
    if provider == "huggingface" and getattr(ref, "local", False):
        return "hf-local"
    if provider == "local":
        return "local"
    return "cloud"


def _call(readers: dict, name: str, *args):
    fn = readers.get(name)
    if fn is None:
        return None
    try:
        return fn(*args)
    except Exception:
        log.debug("model_window: reader %s failed", name, exc_info=True)
        return None


def _catalog_row(catalog, model: str) -> Optional[dict]:
    if not isinstance(catalog, dict):
        return None
    if "models" in catalog and isinstance(catalog.get("models"), list):
        try:
            from halo_harness.providers.ollama_hw import catalog_row
            return catalog_row(catalog, model)
        except Exception:
            return None
    return catalog


def _trained_of(row: Optional[dict]) -> Optional[int]:
    for key in ("trained_context", "context_length", "context_tokens", "max_position_embeddings"):
        v = _pos((row or {}).get(key))
        if v:
            return v
    info = (row or {}).get("model_info") if isinstance((row or {}).get("model_info"), dict) else {}
    family = ((row or {}).get("details") or {}).get("family")
    if family and _pos(info.get(f"{family}.context_length")):
        return info[f"{family}.context_length"]
    return next((v for k, v in info.items() if k.endswith(".context_length") and _pos(v)), None)


def _loaded_on_card(card, model: str) -> Optional[int]:
    from halo_harness.ollama_steward.profiles import short_model
    for row in (card or {}).get("loaded") or []:
        if isinstance(row, dict) and short_model(row.get("model")) == short_model(model):
            return _pos(row.get("context_length"))
    return None


def _card_fit(card, row) -> Optional[int]:
    if not card or not row:
        return None
    from halo_harness.ollama_steward.fit import model_window_on_card
    return _pos(model_window_on_card(card, row, alone=True))


def default_readers(ref, state_dir, host) -> "dict[str, Callable]":
    """The lookups a session already makes; each one is replaceable."""
    kind = kind_of(ref)
    out: dict = {}
    if kind == "ollama":
        def _profile(h, model):
            from halo_harness.ollama_steward.profiles import lookup
            return (lookup(h, model) or {}).get("num_ctx")

        def _learned(h, model, row=None):
            # the same lookup the call makes (`ollama_hw.resolve_context_decision`): the digest and the
            # server's version must match what the measurement recorded
            from halo_harness.providers.ollama import cached_ollama_version
            from halo_harness.providers.ollama_calibrate import lookup_learned_cap
            if state_dir is None:
                return None
            return lookup_learned_cap(state_dir, host_url=h.url, model=model, digest=(row or {}).get("digest"),
                                      ollama_version=cached_ollama_version(h))

        def _catalog(h):
            from halo_harness.providers.ollama import get_catalog
            return get_catalog(h)
        out.update(profile=_profile, learned_cap=_learned, catalog=_catalog)
    elif kind in ("hf-local", "mlx"):
        def _served(r):
            from halo_harness.providers.huggingface_local_resolve import cached_local_context_tokens
            return cached_local_context_tokens(r.host, r.model, env=None)

        def _hf_config(r):
            from halo_harness.providers.huggingface_hub_cache import scan_hub_cache
            from halo_harness.providers.safetensors_config import safetensors_model_info_for_folder
            for m in scan_hub_cache():
                if m.repo_id == r.model and m.path is not None and m.path.is_dir():
                    return ((safetensors_model_info_for_folder(m.path) or {}).get("context_length"))
            return None
        out.update(loaded=_served, trained=_hf_config)
    elif kind == "local":
        def _server_context(r):
            from halo_harness.theme import get_config_value
            servers = get_config_value("local.servers", {}) or {}
            if not isinstance(servers, dict) or not servers:
                return None
            entry = servers.get(r.host) if r.host in servers else next(iter(servers.values()))
            return entry.get("context") if isinstance(entry, dict) else None
        out.update(host_max=_server_context)
    else:
        def _cloud(r):
            from halo_harness.model import resolve_model_profile
            return resolve_model_profile(r, state_dir).context_tokens if state_dir is not None else None
        out.update(cloud=_cloud)
    return out


def _server_kind(ref, readers) -> str:
    kind = kind_of(ref)
    if kind == "ollama":
        return "ollama"
    if kind == "mlx":
        return "mlx"
    named = _call(readers, "server_kind", ref)
    return named if isinstance(named, str) and named in SERVER_DEFAULTS else "local"


def window_of(ref, *, state_dir=None, host=None, catalog=None, card=None, readers=None) -> dict:
    """`{tokens, source, ceiling, ceiling_source, kind}` for `ref` (module docstring)."""
    kind = kind_of(ref)
    model = getattr(ref, "model", "")
    if kind == "ollama" and host is None:
        try:
            from halo_harness.providers.ollama import resolve_ollama_host
            host = resolve_ollama_host(getattr(ref, "host", None))
        except Exception:
            host = None
    r = {**default_readers(ref, state_dir, host), **(readers or {})}
    found: "list[tuple[str, Optional[int]]]" = []
    learned = row = None
    if kind == "ollama":
        if catalog is None and host is not None:
            catalog = _call(r, "catalog", host)
        row = _catalog_row(catalog, model)
        learned = _pos(_call(r, "learned_cap", host, model, row)) if host is not None else None
        found += [("steward profile", _pos(_call(r, "profile", host, model)) if host is not None else None),
                  ("learned cap", learned), ("loaded window", _loaded_on_card(card, model)),
                  ("trained context", _trained_of(row)), ("host max_ctx", _pos(getattr(host, "max_ctx", None)))]
    elif kind == "cloud":
        found.append(("cloud catalog", _pos(_call(r, "cloud", ref))))
    else:
        loaded = _pos(_call(r, "props", ref)) or _pos(_call(r, "lmstudio", ref)) or _pos(_call(r, "loaded", ref))
        row = _catalog_row(catalog, model)
        found += [("loaded window", loaded), ("trained context", _trained_of(row) or _pos(_call(r, "trained", ref))),
                  ("host max_ctx", _pos(_call(r, "host_max", ref)))]
    if kind != "cloud":
        found.append(("server default", SERVER_DEFAULTS.get(_server_kind(ref, r))))
    tokens, source = next(((v, s) for s, v in found if v), (None, "unknown"))
    fit = _card_fit(card, row) if kind == "ollama" else None
    bounds = [("learned cap", learned), ("host max_ctx", _pos(getattr(host, "max_ctx", None)) if kind == "ollama" else None),
              ("the card's fit", fit)]
    if kind == "ollama":
        from halo_harness.providers.ollama import HARD_CONTEXT_CAP
        bounds.append(("hard cap", HARD_CONTEXT_CAP))
    for name, bound in bounds:
        if tokens and bound and bound < tokens:
            tokens, source = bound, name
    ceiling, ceiling_source = (learned, "learned cap") if learned else ((fit, "the card's fit") if fit else (None, ""))
    return {"tokens": tokens, "source": source, "ceiling": ceiling, "ceiling_source": ceiling_source, "kind": kind}


def window_on_host(model: str, host, *, state_dir=None, catalog_row=None, card=None) -> dict:
    """`window_of` for `model` on an Ollama host entry, from what is already in hand (the
    steward's panel and `halo ollama traffic`): no catalog is fetched for it."""
    from types import SimpleNamespace
    ref = SimpleNamespace(provider="ollama", model=model, host=getattr(host, "name", None),
                          raw=f"ol:{model}@{getattr(host, 'name', '')}", dialect="ollama")
    try:
        if state_dir is None:
            from halo_harness.config.paths import bridge_home
            state_dir = bridge_home()
        from halo_harness.providers.ollama_calibrate import lookup_learned_cap

        def _learned(h, m, row=None):  # no version probe here: the panel reads what is on disk
            return lookup_learned_cap(state_dir, host_url=h.url, model=m, digest=(row or {}).get("digest"))
        return window_of(ref, state_dir=state_dir, host=host, catalog=catalog_row or {}, card=card,
                         readers={"catalog": lambda _h: None, "learned_cap": _learned})
    except Exception:
        log.debug("model_window: the window of %s could not be read", model, exc_info=True)
        return {"tokens": None, "source": "unknown", "ceiling": None, "ceiling_source": "", "kind": "ollama"}


def window_words(w: dict) -> str:
    """ "32,768 (learned cap)" / "unknown". """
    if not w or not w.get("tokens"):
        return "unknown"
    return f"{w['tokens']:,} ({w.get('source') or 'unknown'})"
