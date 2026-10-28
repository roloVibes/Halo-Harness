"""halo_harness.providers.ollama_load -- Halo 3.3.5.0 R1: load a model into
an Ollama server's memory, or let it go, the way Ollama documents it: a
`POST /api/generate` with no prompt and a `keep_alive` (docs.ollama.com/faq:
"preload a model" / "keep a model loaded"; `keep_alive: 0` unloads it at once).
Nothing is generated and nothing about the server is changed: the window the
load asks for is the steward profile's (`ollama.profiles`), else the host's
`max_ctx`, else the server's own default.

    load(host, model, *, num_ctx=None, keep_alive=None)  -> {ok, say, status, num_ctx, keep_alive}
    unload(host, model)                                   -> the same, keep_alive 0
    window_for(host, model)                               -> (num_ctx | None, where it came from)
"""

from __future__ import annotations

from typing import Optional

LOAD_TIMEOUT_S = 300.0
UNLOAD_TIMEOUT_S = 30.0


def window_for(host, model: str) -> "tuple[Optional[int], str]":
    try:
        from halo_harness.ollama_steward.profiles import lookup
        prof = lookup(host, model) or {}
    except Exception:
        prof = {}
    if isinstance(prof.get("num_ctx"), int) and prof["num_ctx"] > 0:
        return prof["num_ctx"], "the steward profile"
    if isinstance(getattr(host, "max_ctx", None), int) and host.max_ctx > 0:
        return host.max_ctx, "the host's max_ctx"
    return None, "the server's default"


def _keep(host, model: str, keep_alive) -> Optional[object]:
    if keep_alive not in (None, ""):
        return keep_alive
    try:
        from halo_harness.ollama_steward.profiles import lookup
        prof = lookup(host, model) or {}
    except Exception:
        prof = {}
    return prof.get("keep_alive") or getattr(host, "keep_alive", None)


def _say(reply, verb: str, model: str, host) -> str:
    name = getattr(host, "name", "?")
    if reply.failure is None:
        return f"{model} {verb} on {name}"
    if reply.failure == "http":
        return f"{name} answered HTTP {reply.status} to {verb[:-2] if verb.endswith('ed') else verb} {model}"
    return f"{name} did not answer ({reply.failure})"


def load(host, model: str, *, num_ctx: Optional[int] = None, keep_alive=None) -> dict:
    """Load `model` at the profile's window (or `num_ctx`), kept for `keep_alive`."""
    from halo_harness.providers.ollama import request_json
    from halo_harness.providers.ollama_guard import control_blocked  # 3.3.5.0 R3
    if control_blocked(host):
        return {"ok": False, "say": control_blocked(host), "status": None, "num_ctx": num_ctx, "keep_alive": keep_alive}
    where = "asked"
    if num_ctx is None:
        num_ctx, where = window_for(host, model)
    keep = _keep(host, model, keep_alive)
    body: dict = {"model": model, "stream": False}
    if num_ctx:
        body["options"] = {"num_ctx": int(num_ctx)}
    if keep is not None:
        body["keep_alive"] = keep
    reply = request_json(host, "/api/generate", method="POST", body=body, timeout=LOAD_TIMEOUT_S)
    say = _say(reply, "loaded", model, host)
    if reply.failure is None:
        say += f" at {int(num_ctx):,} ({where})" if num_ctx else " at the server's default window"
        if keep is not None:
            say += f", kept {keep}"
    return {"ok": reply.failure is None, "say": say, "status": reply.status, "num_ctx": num_ctx, "keep_alive": keep,
            "window_from": where}


def unload(host, model: str) -> dict:
    from halo_harness.providers.ollama import request_json
    from halo_harness.providers.ollama_guard import control_blocked  # 3.3.5.0 R3
    if control_blocked(host):
        return {"ok": False, "say": control_blocked(host), "status": None, "num_ctx": None, "keep_alive": 0}
    reply = request_json(host, "/api/generate", method="POST", body={"model": model, "keep_alive": 0, "stream": False},
                         timeout=UNLOAD_TIMEOUT_S)
    return {"ok": reply.failure is None, "say": _say(reply, "unloaded", model, host), "status": reply.status,
            "num_ctx": None, "keep_alive": 0}
