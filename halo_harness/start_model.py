"""halo_harness.start_model -- Halo 3.6.0.11: the ONE answer to "which model does a new session started here begin on,
and why". Agents -> Map names it on main's box (studio/crew_map_api.py `start`) and `halo doctor` reports it
(doctor._effective_default_model is a call of this).

The order is `headless.build_session`'s own for a new session with no --model (headless.py, the model_raw chain):
the model pinned in the map's main (the caller passes it: `crew.map_session.model` of the map a session would run,
None on Auto) > the remembered /model (launch_state, per `model_memory`) > HALO_MODEL > routes.json `default` >
config.json `model` > the work-environment shortcut > the built-in default. build_session also skips a remembered
/model whose provider is gone or has no credentials on this box (it says so on the terminal); this answer does not
check credentials, as doctor never did.

The origins: "pin", "remembered", "env", "routes", "config", "work", "built-in"."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple


def start_model(cwd=None, *, map_pin: Optional[str] = None, settings_flag: Optional[str] = None) -> Tuple[str, str]:
    """`(ref, origin)` of the model a new session in `cwd` starts on (see the module's docstring)."""
    from halo_harness import launch_state
    from halo_harness.config.paths import bridge_home, env_compat
    from halo_harness.model import DEFAULT_MODEL_REF, resolve_default_model_raw
    from halo_harness.providers.config import listing_effective_env, load_routes
    from halo_harness.theme import get_config_value
    if map_pin:
        return str(map_pin), "pin"
    here = Path(cwd) if cwd else Path.cwd()
    memory = get_config_value("model_memory", default="cwd")
    last = launch_state.resolve_last_model(here, memory=memory if isinstance(memory, str) else "cwd")
    if last:
        return str(last), "remembered"
    if env_compat("MODEL"):
        return str(env_compat("MODEL")), "env"
    routes = load_routes(bridge_home() / "routes.json")
    if routes.get("default"):
        return str(routes["default"]), "routes"
    configured = get_config_value("model", default=None)
    if isinstance(configured, str) and configured:
        return configured, "config"
    raw = resolve_default_model_raw(routes, env=listing_effective_env(Path(cwd) if cwd else None, settings_flag))
    return (raw, "work") if raw != DEFAULT_MODEL_REF else (DEFAULT_MODEL_REF, "built-in")
