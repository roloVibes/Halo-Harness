"""halo_harness.start.provider -- does `halo start` have a model to run on
(Halo 3.1.1.0 R1)?

`ready()` is `(True, "<what>")` when a provider's credentials or login
resolve and it is enabled (`init_providers.configured_providers`), or when
config.json names a default model (a local or LAN model counts); else
`(False, the line that says so)`. `halo init` is what sets a provider up;
`halo setup` is its team and orgs screens, for later.
"""

from __future__ import annotations

NO_PROVIDER = ("No model provider is set up yet, so there is nothing for the agents to run on. "
               "halo init sets one up (a key, a login or a local model), then run halo start again; "
               "halo setup is the team and orgs screens for later.")


def configured() -> "list[str]":
    try:
        from halo_harness.init_providers import configured_providers
        return list(configured_providers())
    except Exception:
        return []


def default_model() -> str:
    try:
        from halo_harness.theme import get_config_value
        return str(get_config_value("model", "") or "")
    except Exception:
        return ""


def ready() -> "tuple[bool, str]":
    providers = configured()
    model = default_model()
    if providers:
        return True, "provider(s): " + ", ".join(providers) + (f"; default model {model}" if model else "")
    if model:
        return True, f"default model {model}"
    return False, NO_PROVIDER
