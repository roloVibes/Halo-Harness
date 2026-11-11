"""halo_harness.providers.left_core -- the providers and routes that left Halo's core, and the one line each gets.

3.1.5.0 removed the `cc:` and `cx:` routes; 3.4.0.0 "The core" removed TypeSafe (a key-only placeholder: it stored
`TYPESAFE_API_KEY` and routed no model). What is left of one in someone's setup -- a `ts:` ref, the key in the env
file or a settings env block, a `providers.typesafe` row in config.json, `halo providers enable typesafe` -- is
ignored and named in one line, never an error. A leftover key is still stripped from tool children and redacted
(providers/config.py, redact.py): it is a secret wherever it came from.
"""

from __future__ import annotations

import os
from typing import Optional

#: name -> (label, the version it left in, its env key, what to do instead)
GONE = {"typesafe": ("TypeSafe", "3.4.0.0", "TYPESAFE_API_KEY",
                     "it routed no model; pick one from halo models (or:, ant:, dbx:, oai:, xp:, ol:, hf:)")}
#: a ref prefix -> the provider that left with it
GONE_PREFIXES = {"ts:": "typesafe"}


def gone_line(name: str) -> str:
    """`typesafe left the core in 3.4.0.0: ...` -- the one line for a provider that left."""
    label, version, key, instead = GONE[name]
    return f"{name} ({label}) left the core in {version}: {instead}; {key} and providers.{name} are ignored"


def removed_route_line(raw: str) -> str:
    """The one line a ref on a removed route gets everywhere (headless, `/model`, a remembered last model, a config
    `model:`, a bio or a lineup): `cc:`/`cx:` (3.1.5.0) or `ts:` (3.4.0.0)."""
    for prefix, name in GONE_PREFIXES.items():
        if str(raw).startswith(prefix):
            return f"no route: {raw!r} ({prefix} {gone_line(name)})"
    return (f"no route: {raw!r} (the cc: and cx: routes were removed in 3.1.5.0; "
            f"use an API route, e.g. ant:sonnet with ANTHROPIC_API_KEY, or or:anthropic/<model>)")


def leftovers(env: Optional[dict] = None, cwd=None) -> "list[str]":
    """The providers that left whose key or config row is still here: `[name]` (env, the settings env chain, the
    `providers` block of config.json). Reads config and env only, never the network."""
    e = env if env is not None else os.environ
    try:
        from halo_harness.theme import get_config_value
        block = get_config_value("providers", default=None)
    except Exception:
        block = None
    out = []
    for name, (_label, _version, key, _instead) in GONE.items():
        found = bool(e.get(key)) or (isinstance(block, dict) and name in block)
        if not found and env is None:
            try:
                from pathlib import Path

                from halo_harness.providers.config import load_settings_env_chain
                found = bool(load_settings_env_chain(Path(cwd) if cwd else Path.cwd()).get(key))
            except Exception:
                found = False
        if found:
            out.append(name)
    return out


def leftover_lines(env: Optional[dict] = None, cwd=None) -> "list[str]":
    """One line per provider that left and still has its key or config row here (doctor, `halo providers`)."""
    return [gone_line(name) for name in leftovers(env, cwd)]
