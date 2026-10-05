"""halo_harness.providers.huggingface_local_resolve -- Halo 2.0.3 round 5:
"which local server does this `hf:local/*` ref actually mean" plus the
short-TTL context-length cache `model.resolve_model_profile` reads for
one. Split out of `providers.huggingface_local_probe` (which owns the
probing itself: ports, the auto-detect sweep, the manual-entry on-demand
probe) purely to keep each file's own writes under the house 250-line-
per-write habit -- both modules are round 5, same design doc.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

from halo_harness.providers.huggingface_local_probe import auto_detect_local_servers, probe_models_endpoint

log = logging.getLogger("bridge")

_CONTEXT_CACHE_TTL_S = 30.0  # matches providers.ollama._CATALOG_TTL_S


@dataclass(frozen=True)
class ResolvedLocalServer:
    name: str
    base_url: str
    api_key: Optional[str]


def resolve_local_server(name: Optional[str], env: Optional[dict] = None, *,
                          model: Optional[str] = None, state_dir=None) -> Optional[ResolvedLocalServer]:
    """`hf:local/<model>` (`name=None`, the default server) or `hf:local/
    <model>@<name>` (a named manual entry) resolved to ONE `(name,
    base_url, api_key)` -- round 5 brief item 1. A NAMED ref matches a
    manual `huggingface.local_servers` entry ONLY -- a typo'd name fails
    plainly, never silently falling through to a same-numbered auto-
    detected port. A BARE ref prefers a configured manual entry (the
    default one, or the first configured when none is marked default);
    with nothing configured, item 1's own rule applies: "the default
    server is the first auto-detected one" -- this runs the SAME
    background-probe-gated sweep `auto_detect_local_servers` does. A
    per-request credential/profile resolution call (THIS function's two
    real callers, `headless._resolve_creds` and `model.resolve_model_
    profile`) is deliberately NOT the kind of 'background' probe that gate
    means -- same precedent `providers.ollama.get_catalog`'s own per-
    request catalog read already sets -- so this is called directly
    rather than from a fire-and-forget worker; under
    `BRIDGE_TEST_NO_BACKGROUND_NET` a BARE ref with no manual entry simply
    resolves to `None` (nothing detected), which a hermetic test can
    always avoid by configuring a manual entry instead (`/local`'s own
    print-mode end-to-end test does exactly that).

    Round 5c (brief item 3): a BARE ref with no manual entry and nothing
    live-auto-detected falls through once more to `providers.local_runtime`'s
    on-disk managed-server registry (`~/.halo/run/local-servers.json`) --
    the one source of truth for "what did `halo local serve` just start",
    read directly rather than duplicated into a second, in-memory
    registration step, so a SEPARATE `halo` process started after the
    `serve` call can resolve it too. The MOST RECENTLY STARTED entry wins
    when more than one is running -- a FALLBACK tie-break, never the
    first thing tried any more (see `model` below).

    Review fix pass (finding 11): a BARE ref's own `<model>` id, when
    given, is used FIRST to pick among the servers this process can
    actually CONFIRM serve it -- an exact registry entry (by its own
    `model` field, the Halo-side id `start_managed_server` recorded it
    under), probed alive right now (A12's `--alias` fix is what makes a
    managed llama-server's own `/v1/models` id equal that registry key at
    all); failing that, any auto-detected server whose `/v1/models`
    happens to list it. Only when NEITHER confirms it does this fall
    through to "the default server" below (the manual-default/first-
    auto-detected/most-recent-registry chain, UNCHANGED) -- the exact
    pre-fix behaviour, which used to be the ONLY rule a bare ref ever got:
    `halo local serve` prints `hf:local/<model_id>`, then a LATER `halo
    -p --model hf:local/<model_id>` could silently land on a completely
    different server (an auto-detected LM Studio on a well-known port, or
    a newer registry entry for a different model), llama-server itself
    never objecting (it ignores the request body's own `model` field). A
    one-line notice (`log.info`, visible in logs/`--verbose` -- this
    function has no event stream of its own to yield a `notification`
    through, same reasoning `agent/loop.Session.call_small_model` already
    gives for its own notices) names which server was actually chosen,
    only when THIS id-matched path is what decided it."""
    from halo_harness.providers.huggingface import resolve_huggingface_local_server
    manual = resolve_huggingface_local_server(name)
    if manual is not None:
        return ResolvedLocalServer(name=manual.name, base_url=manual.url, api_key=manual.api_key)
    if name:
        return None  # a NAMED ref that isn't configured must fail plainly, never fall back to auto-detect
    if model:
        from_registry = _registry_server_for_model(model, state_dir=state_dir)
        if from_registry is not None:
            log.info("hf:local/%s -- resolved to the managed server %r (%s), confirmed by its own served "
                      "model id", model, from_registry.name, from_registry.base_url)
            return from_registry
        from_auto = _auto_detected_server_for_model(model, env=env)
        if from_auto is not None:
            log.info("hf:local/%s -- resolved to the auto-detected server %r (%s), matched by its own served "
                      "model id", model, from_auto.name, from_auto.base_url)
            return from_auto
    detected = auto_detect_local_servers(env=env)
    if detected:
        first = detected[0]
        return ResolvedLocalServer(name=first.name, base_url=first.base_url, api_key=None)
    managed = _most_recent_managed_server(state_dir)
    if managed is None:
        return None
    return ResolvedLocalServer(name=managed.get("model"), base_url=managed.get("base_url"), api_key=None)


def _registry_server_for_model(model_id: str, *, state_dir=None) -> Optional[ResolvedLocalServer]:
    """Review fix pass (finding 11): `resolve_managed_server_by_model`'s
    own exact registry lookup, confirmed ALIVE by a real `/v1/models`
    probe before ever being handed out -- `None` (never the stale entry)
    when the probe fails outright or the server no longer reports this
    exact id, so a crashed/replaced managed server, or a stale entry left
    behind a reboot, is never resolved as if it still worked. The probe
    itself is the SAME `providers.huggingface_local_probe.probe_models_
    endpoint` an auto-detect sweep uses -- a single, short, loopback GET."""
    candidate = resolve_managed_server_by_model(model_id, state_dir=state_dir)
    if candidate is None:
        return None
    info = probe_models_endpoint(candidate.base_url, name=candidate.name, api_key=candidate.api_key)
    if info is None or model_id not in info.model_ids:
        return None
    return candidate


def _auto_detected_server_for_model(model_id: str, env: Optional[dict] = None) -> Optional[ResolvedLocalServer]:
    """Review fix pass (finding 11): among whatever `auto_detect_local_
    servers` already probed (loopback-only, the SAME background-probe-
    gated sweep the bare-ref default path below always ran), the first
    one whose `/v1/models` actually listed `model_id` -- never just "the
    first port that answered anything", which used to be the entire
    rule."""
    for info in auto_detect_local_servers(env=env):
        if model_id in info.model_ids:
            return ResolvedLocalServer(name=info.name, base_url=info.base_url, api_key=None)
    return None


def _most_recent_managed_server(state_dir=None) -> Optional[dict]:
    from halo_harness.providers.local_runtime import load_registry
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    entries = load_registry(state_dir)
    return entries[-1] if entries else None


def resolve_managed_server_by_model(model_id: str, *, state_dir=None) -> Optional[ResolvedLocalServer]:
    """Halo 2.0.3 round 5f: an EXACT registry lookup by `model` id --
    unlike `resolve_local_server`'s own "most recently started wins"
    fallback (right above), which is correct ONLY for a BARE `hf:local/
    <model>` ref that has no specific id of its own to insist on. An
    `hf:mlx/<repo>` ref always names its exact repo id, so it must find
    THAT entry specifically -- "most recent" would silently hand it a
    DIFFERENT model's server whenever more than one managed server is
    running at once. `None` when no registry entry has this exact `model`
    id (the caller, `providers.huggingface_mlx.ensure_mlx_server`, then
    starts one)."""
    from halo_harness.providers.local_runtime import load_registry
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    for entry in load_registry(state_dir):
        if entry.get("model") == model_id:
            return ResolvedLocalServer(name=model_id, base_url=entry.get("base_url"), api_key=None)
    return None


_context_cache_lock = threading.Lock()
_context_cache: dict = {}  # (base_url, model_id) -> (monotonic_ts, Optional[int])


def cached_local_context_tokens(name: Optional[str], model_id: str, *, env: Optional[dict] = None,
                                 ttl_s: float = _CONTEXT_CACHE_TTL_S) -> Optional[int]:
    """`model.resolve_model_profile`'s own read-back for an `hf:local/*`
    ref: resolves the target server (same rule `resolve_local_server`
    uses), reads its reported context for `model_id`, short-TTL cached per
    `(base_url, model_id)` so a session build never re-probes the server
    more than once every `ttl_s` seconds -- mirrors `providers.ollama.
    get_catalog`'s own cache shape/rationale. `None` when the target can't
    be resolved, is unreachable, or never reported a context number for
    this exact model id -- the caller's own dataclass default stands.

    Review fix pass (finding 11): `model_id` is now also passed to
    `resolve_local_server` itself, so a bare `hf:local/<model_id>`'s
    context readback targets the SAME server the id-aware resolution
    picked, never a different one "the default" would have guessed."""
    target = resolve_local_server(name, env, model=model_id)
    if target is None:
        return None
    key = (target.base_url, model_id)
    now = time.monotonic()
    with _context_cache_lock:
        cached = _context_cache.get(key)
    if cached is not None and (now - cached[0]) < ttl_s:
        return cached[1]
    info = probe_models_endpoint(target.base_url, name=target.name, api_key=target.api_key)
    ctx = info.context_by_model.get(model_id) if info is not None else None
    with _context_cache_lock:
        _context_cache[key] = (now, ctx)
    return ctx


def reset_local_probe_cache() -> None:
    """Test seam: force the next `cached_local_context_tokens` call to
    re-probe rather than reading a stale in-process cache entry."""
    with _context_cache_lock:
        _context_cache.clear()
