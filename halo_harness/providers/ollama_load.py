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


def came_back(reply) -> str:
    """3.6.0.0 R8 fix pass M2/S8: what a server answered when it was not Ollama's answer, in plain words."""
    status = getattr(reply, "status", None)
    if reply.failure == "unreadable":
        return f"a page that is not Ollama's JSON (it starts {reply.error!r})" if reply.error else \
            "an empty or unreadable page, not Ollama's JSON"
    if reply.failure == "http":
        if status in (401, 403):
            return f"HTTP {status} (it asks for a sign-in or a key: something in front of Ollama)"
        if isinstance(status, int) and 300 <= status < 400:
            return f"HTTP {status} (a redirect: something other than Ollama answers at this address)"
        return f"HTTP {status}" + (f": {reply.error}" if reply.error else "")
    return "JSON that is not an Ollama answer"


def is_ollama_answer(reply, key: str = "done") -> bool:
    """A 200 whose JSON carries Ollama's own `key` (`done` for /api/generate, `models` for /api/ps)."""
    return reply.failure is None and isinstance(reply.body, dict) and key in reply.body


def _say(reply, verb: str, model: str, host) -> str:
    name = getattr(host, "name", "?")
    act = verb[:-2] if verb.endswith("ed") else verb
    if is_ollama_answer(reply):
        return f"{model} {verb} on {name}"
    if reply.failure in ("unreachable", "timeout", "error"):
        return f"{name} did not answer ({reply.failure})"
    status = reply.status if isinstance(reply.status, int) else 0
    if reply.failure == "http" and status not in (401, 403) and not 300 <= status < 400:
        return f"{name} answered HTTP {reply.status} to {act} {model}"
    return f"{name} answered the {act} of {model} with {came_back(reply)}: nothing was done"


def load(host, model: str, *, num_ctx: Optional[int] = None, keep_alive=None, window_from: Optional[str] = None) -> dict:
    """Load `model` at the profile's window (or `num_ctx`, `window_from` saying where it came from), kept for
    `keep_alive`."""
    from halo_harness.providers.ollama import request_json
    from halo_harness.providers.ollama_guard import control_blocked  # 3.3.5.0 R3
    if control_blocked(host):
        return {"ok": False, "say": control_blocked(host), "status": None, "num_ctx": num_ctx, "keep_alive": keep_alive}
    where = window_from or "asked"
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
    ok = is_ollama_answer(reply)  # 3.6.0.0 R8 fix pass M2: a real Ollama answer, not a proxy's page
    if ok:
        say += f" at {int(num_ctx):,} ({where})" if num_ctx else " at the server's default window"
        if keep is not None:
            say += f", kept {keep}"
    return {"ok": ok, "say": say, "status": reply.status, "num_ctx": num_ctx, "keep_alive": keep,
            "window_from": where}


def unload(host, model: str) -> dict:
    from halo_harness.providers.ollama import request_json
    from halo_harness.providers.ollama_guard import control_blocked  # 3.3.5.0 R3
    if control_blocked(host):
        return {"ok": False, "say": control_blocked(host), "status": None, "num_ctx": None, "keep_alive": 0}
    reply = request_json(host, "/api/generate", method="POST", body={"model": model, "keep_alive": 0, "stream": False},
                         timeout=UNLOAD_TIMEOUT_S)
    return {"ok": is_ollama_answer(reply), "say": _say(reply, "unloaded", model, host), "status": reply.status,
            "num_ctx": None, "keep_alive": 0}
