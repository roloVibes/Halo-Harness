"""halo_harness.providers.local_models_cached -- the local model rows from
what this process already knows, never a probe (Halo 3.3.0.0 R3).

`build_local_view(cached=True)` (providers/local_models.py) and so
`build_model_rows(..., cached=True)` read these instead of asking each
Ollama host and each local port again: a read of a page (Studio's
`GET setup/state`, the guided first run's card, a lineup's cost line)
opens no connection. What a Refresh read (`halo models --refresh`,
Studio's Refresh, `/local refresh`, the 30 s catalog cache any probe
fills) is what these rows show, however old it is; a host never read in
this process is one row "(not read yet: Refresh)", which the catalog
leaves out (a name in parentheses is never a model).

    ollama_cached_rows(host, state_dir)   the host's rows from providers.ollama's catalog cache
    cached_detected_servers()             the last auto-detected local servers (no probe)
    hosts_not_read(env)                   the configured Ollama hosts with nothing cached yet
"""

from __future__ import annotations

from typing import Optional

NOT_READ = "(not read yet: Refresh)"


def cached_catalog(host) -> Optional[dict]:
    """The catalog the last read of `host` cached (`providers.ollama.get_catalog`), whatever its age; None when
    nothing read it in this process."""
    from halo_harness.providers import ollama as O
    with O._CATALOG_LOCK:
        entry = O._CATALOG_CACHE.get(host.url)
    return entry[1] if entry is not None else None


def ollama_cached_rows(host, state_dir) -> list:
    """`_ollama_rows` without the probe: the cached catalog's models (context from the catalog, `loaded` unknown),
    or one NOT_READ row."""
    from halo_harness.providers.local_models import LocalModelRow, _capability_text
    group = f"Ollama ({host.name})"
    catalog = cached_catalog(host)
    if catalog is None:
        return [LocalModelRow(group=group, name=NOT_READ, reachable=None)]
    from halo_harness.providers.ollama import trained_context_for
    try:
        from halo_harness.providers.ollama_capability import load_capability_cache
        cap_cache = load_capability_cache(state_dir)
    except Exception:
        cap_cache = {}
    out = []
    for row in catalog.get("models") or []:
        name = row.get("model") or row.get("name") if isinstance(row, dict) else None
        if not name:
            continue
        details = row.get("details") or {}
        probed = cap_cache.get(row.get("digest"), {}).get("tool_calls") if row.get("digest") else None
        declared = row.get("capabilities") if isinstance(row.get("capabilities"), list) else []
        out.append(LocalModelRow(group=group, name=name, ref=f"ol:{name}" if host.default else f"ol:{name}@{host.name}",
                                 size_bytes=row.get("size") if isinstance(row.get("size"), int) else None,
                                 quant=details.get("quantization_level"), context=trained_context_for(catalog, name),
                                 capability=_capability_text(declared="tools" in declared, probed=probed),
                                 loaded=None, reachable=None, capabilities=tuple(str(c) for c in declared) or None,
                                 tools_probe=probed if isinstance(probed, bool) else None))
    return out


def cached_detected_servers() -> list:
    """The local servers the last auto-detection found (providers.huggingface_local_probe), any age; [] when none ran."""
    from halo_harness.providers import huggingface_local_probe as P
    cache = getattr(P, "_auto_detect_cache", None)
    return list(cache[2]) if cache else []


def hosts_not_read(env: Optional[dict] = None) -> list:
    """The Ollama hosts config.json names (`ollama.hosts`) that nothing has read in this process: the ones whose rows
    say "not read yet". The synthesized default host (no `ollama.hosts`) is left out: nobody set it up."""
    from halo_harness.theme import get_config_value
    raw = get_config_value("ollama.hosts", default=None)
    if not isinstance(raw, list) or not raw:
        return []
    from halo_harness.providers.ollama import resolve_ollama_hosts
    return [h for h in resolve_ollama_hosts(env) if cached_catalog(h) is None]
