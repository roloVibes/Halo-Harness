"""halo_harness.providers.ollama_discover_hosts -- Halo 3.2.3.0 R2: what
happens to a found server: `add_hosts` writes the chosen new rows as
`ollama.hosts` entries, and the shared one-line renderings `halo ollama
discover`, the wizard, `halo ollama`, `halo local` and the detection
summary all print.

`add_hosts` never repoints an existing host (a row whose address is
already an entry is left alone), keeps the first entry ever the default,
and writes no key. When `ollama.hosts` is still empty and the host Halo
synthesizes from `OLLAMA_HOST` / 127.0.0.1:11434 was itself found, that
host is written first, as `default`, so a bare `ol:<model>` keeps
reaching the same daemon after a network host is added.
"""

from __future__ import annotations

import os
import urllib.parse
from typing import Iterable, Optional

from halo_harness.providers.ollama_discover import NOT_ADDED_HINT, Found, _unique, discover_local_cached, url_key


def models_text(models: "list[str]", *, limit: int = 4) -> str:
    if not models:
        return "no models pulled yet"
    shown = ", ".join(models[:limit]) + (f", +{len(models) - limit} more" if len(models) > limit else "")
    return f"{len(models)} model{'' if len(models) == 1 else 's'}: {shown}"


def host_port(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc or url
    except ValueError:
        return url


def format_row(row: Found) -> str:
    """`pc        http://<addr>:11434  0.12.x  3 models: a, b, c  configured`"""
    return (f"{row.name:<9} {row.url:<28} {row.version or '?':<9} {models_text(row.models)}  "
            f"{'configured' if row.configured else 'new'}")


def _config_hosts() -> "list[dict]":
    from halo_harness.theme import get_config_value
    hosts = get_config_value("ollama.hosts", default=None)
    return [dict(h) for h in hosts if isinstance(h, dict)] if isinstance(hosts, list) else []


def add_hosts(found: "Iterable[Found]", names: "Optional[Iterable[str]]" = None, state_dir=None) -> "list[str]":
    """Writes an `ollama.hosts` entry for every new row in `found` (all of
    them, or those whose name is in `names`) and returns one line per
    host added. `state_dir` is accepted for symmetry with the other
    discovery calls; the entries go to the same `config.json` every
    `ollama.hosts` reader uses."""
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.theme import set_config_value
    found = list(found)
    wanted = {n.strip().lower() for n in names if n and n.strip()} if names is not None else None
    chosen = [r for r in found if not r.configured and (wanted is None or r.name.lower() in wanted)]
    if not chosen:
        return []
    hosts = _config_hosts()
    keys = {url_key(h["url"]) for h in hosts if isinstance(h.get("url"), str)}
    taken = {str(h.get("name") or "").lower() for h in hosts}
    new: "list[dict]" = []
    lines: "list[str]" = []
    if not hosts:
        synth = resolve_ollama_hosts()[0]
        if any(r.configured and url_key(r.url) == url_key(synth.url) for r in found):
            entry = {"name": synth.name, "url": synth.url, "default": True}
            if os.environ.get("OLLAMA_API_KEY"):
                entry["api_key_env"] = "OLLAMA_API_KEY"
            new.append(entry)
            keys.add(url_key(synth.url))
            taken.add(synth.name.lower())
            lines.append(f"kept the default host {synth.name!r} ({synth.url}) as the first ollama.hosts entry, "
                         f"so ol:<model> still reaches it")
    for row in chosen:
        key = url_key(row.url)
        if key in keys or any(tuple(a) in keys for a in row.aliases):
            continue
        name = _unique(row.name, taken)
        entry = {"name": name, "url": row.url}
        if not hosts and not new:
            entry["default"] = True
        new.append(entry)
        keys.add(key)
        taken.add(name.lower())
        ref = "ol:<model>" if entry.get("default") else f"ol:<model>@{name}"
        lines.append(f"added Ollama host {name!r} ({row.url}), {models_text(row.models)} -- use {ref}")
    if new:
        set_config_value("ollama.hosts", hosts + new)
    return lines


def found_not_added(env=None, *, force: bool = False) -> "list[Found]":
    """The local servers the 60 s discovery cache knows that are not
    `ollama.hosts` entries yet (never raises)."""
    try:
        return [r for r in discover_local_cached(env=env, force=force) if not r.configured]
    except Exception:
        return []


def found_not_added_lines(env=None, *, force: bool = False) -> "list[str]":
    return [f"Ollama at {host_port(r.url)} ({r.name}): {models_text(r.models)} -- {NOT_ADDED_HINT}"
            for r in found_not_added(env, force=force)]


def local_summary_lines(env=None, *, force: bool = False) -> "list[str]":
    """One line per local Ollama found, for the wizard's detection
    summary: "Ollama at 127.0.0.1:11434: 3 models" / "...: 1 model, not
    added"."""
    try:
        rows = discover_local_cached(env=env, force=force)
    except Exception:
        return []
    out = []
    for r in rows:
        count = f"{len(r.models)} model{'' if len(r.models) == 1 else 's'}"
        out.append(f"Ollama at {host_port(r.url)}: {count}" + ("" if r.configured else ", not added"))
    return out
