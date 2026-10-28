"""tests.helpers.mock_ollama_generate -- Halo 3.3.5.0 R1: the fake Ollama's
`POST /api/generate` with no prompt, the documented load / unload
(providers/ollama_load.py): `keep_alive: 0` drops the model from `/api/ps`,
anything else lists it there (at the request's `num_ctx`, fully on the GPU),
and the answer is the server's `{model, done: true, done_reason: load | unload}`.
A model the fake does not have (no `/api/show` answer) is a 404, like the server.
"""
from __future__ import annotations

import time


def apply_generate(mock, body: dict) -> "tuple[int, dict]":
    name = str((body or {}).get("model") or "")
    if name not in (mock.show_responses or {}):
        return 404, {"error": f"model '{name}' not found"}
    keep = (body or {}).get("keep_alive")
    unload = keep in (0, "0", "0s")
    with mock._lock:
        mock.generated.append({"model": name, "keep_alive": keep, "options": (body or {}).get("options"), "ts": time.monotonic()})
        rows = [e for e in (mock.ps_response.get("models") or []) if e.get("model") != name]
        if not unload:
            num_ctx = ((body or {}).get("options") or {}).get("num_ctx") or 4096
            rows.append({"name": name, "model": name, "size": 2 * 1024 ** 3, "size_vram": 2 * 1024 ** 3,
                         "expires_at": "2099-01-01T00:00:00Z", "context_length": num_ctx})
        mock.ps_response = {**mock.ps_response, "models": rows}
    return 200, {"model": name, "created_at": "2026-10-28T00:00:00Z", "response": "", "done": True,
                 "done_reason": "unload" if unload else "load"}
