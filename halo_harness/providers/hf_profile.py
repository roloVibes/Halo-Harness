"""halo_harness.providers.hf_profile -- Halo 3.3.8.0 R2: a call to a local server (an `hf:local/*` or `hf:mlx/*` ref)
reads the steward's profile for that server and model, `ollama.profiles["<server>|<model>"]`, the same key an Ollama
host's model has (ollama_steward/profiles.py; the server's name: servers_hf.py). The steward's fixes for a server
land there (agent_proposals, steward.apply_change) and take effect on the next call:

    num_ctx      the window Halo works to (model.resolve_model_profile): never above what the server reports
    num_predict  the reply's room (the request's max_tokens, agent/model_switch_history.switch_reserve)
    tools_max    the tool budget (agent/prompt_wire._profile_tools_max)

    profile_for_ref(ref, state_dir=None) -> {} | the profile
    window(ref, served) -> the window   reply_budget(session, budget) -> the budget   tools_max(ref) -> int | None
"""

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("bridge")


def _pos(v) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else None


def _local(ref) -> bool:
    return getattr(ref, "provider", "") == "huggingface" and bool(getattr(ref, "local", False) or getattr(ref, "mlx", False))


def profile_for_ref(ref, state_dir=None) -> dict:
    if not _local(ref) or not getattr(ref, "model", None):
        return {}
    try:
        from halo_harness.ollama_steward.profiles import lookup
        from halo_harness.ollama_steward.servers_hf import roster
        names = [ref.host] if getattr(ref, "host", None) else [s.name for s in roster(state_dir)]
        for name in names:
            got = lookup(name, ref.model)
            if got:
                return got
    except Exception:
        log.debug("hf_profile: the server profile could not be read", exc_info=True)
    return {}


def window(ref, served: Optional[int]) -> Optional[int]:
    """The served window, or the profile's when it is smaller (or the server says none); 3.3.8.0 R3: never past the
    server entry's `max_ctx` (the pool's fit window: a 64k promise never reaches a request)."""
    mine = _pos(profile_for_ref(ref).get("num_ctx"))
    out = mine if mine and (not _pos(served) or mine < served) else served
    cap = _entry_max(ref)
    return cap if cap and (not _pos(out) or out > cap) else out


def _entry_max(ref) -> Optional[int]:
    if not _local(ref) or not getattr(ref, "host", None):
        return None
    try:
        from halo_harness.providers.huggingface import resolve_huggingface_local_server
        return _pos(getattr(resolve_huggingface_local_server(ref.host), "max_ctx", None))
    except Exception:
        return None


def reply_budget(session, budget):
    p = profile_for_ref(getattr(session, "model_ref", None), getattr(session, "state_dir", None))
    room = _pos(p.get("num_predict"))
    if not room:
        return budget
    return max(room, budget) if _pos(budget) else room


def tools_max(ref) -> Optional[int]:
    return _pos(profile_for_ref(ref).get("tools_max"))
