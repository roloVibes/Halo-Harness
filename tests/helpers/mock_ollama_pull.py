"""tests.helpers.mock_ollama_pull -- Halo 3.3.5.0 R3: the fake Ollama's
`POST /api/pull` (a scripted NDJSON stream) and `POST /api/copy`, the way the
real server answers them (docs.ollama.com/api/pull, /api/copy):

    {"status": "pulling manifest"}
    {"status": "pulling <12 hex>", "digest": "sha256:...", "total": N, "completed": n}   (STEPS times)
    {"status": "verifying sha256 digest"}
    {"status": "writing manifest"}
    {"status": "success"}

A name the fake can pull is in `mock.pullable` (name -> its `/api/show`
answer) or starts with `hf.co/`; any other name gets `{"error": "pull model
manifest: file does not exist"}`, like the server. After "success" the model
joins `/api/tags` and `/api/show`. `mock.pull_delay_s` waits between lines (a
cancel test, a progress bar the browser sees); a client that hangs up mid-way
is recorded in `mock.pull_cancelled` and nothing is added. `mock.pulled` lists
every finished pull.
"""

from __future__ import annotations

import hashlib
import json
import time

STEPS = 5
TOTAL = 5 * 1024 ** 3
HF_SHOW = {"capabilities": ["completion"], "details": {"family": "llama", "format": "gguf", "parameter_size": "8.0B",
                                                         "quantization_level": "Q4_K_M"},
           "model_info": {"llama.context_length": 131072, "llama.block_count": 32}, "parameters": "", "template": "",
           "modelfile": "", "license": "llama3.1 community licence (fixture)"}


def _norm(name: str) -> str:
    name = (name or "").strip()
    return name if ":" in name.rsplit("/", 1)[-1] else f"{name}:latest"


def script(name: str, total: int = TOTAL, steps: int = STEPS) -> list:
    digest = "sha256:" + hashlib.sha256(name.encode("utf-8")).hexdigest()
    lines = [{"status": "pulling manifest"}]
    for i in range(1, steps + 1):
        lines.append({"status": f"pulling {digest[7:19]}", "digest": digest, "total": total, "completed": total * i // steps})
    return lines + [{"status": "verifying sha256 digest"}, {"status": "writing manifest"}, {"status": "success"}]


def _add(mock, name: str, show: dict) -> None:
    key = _norm(name)
    with mock._lock:
        mock.show_responses[key] = json.loads(json.dumps(show))
        if key != name:
            mock.show_responses[name] = mock.show_responses[key]
        tags = mock.tags_response.setdefault("models", [])
        tags[:] = [t for t in tags if _norm(t.get("model") or t.get("name") or "") != key]
        tags.append({"name": key, "model": key, "size": TOTAL, "digest": f"sha256:pulled{len(tags)}",
                     "modified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "details": show.get("details") or {}})
        mock.pulled.append(name)


def apply_pull(handler, mock, body: dict) -> None:
    from tests.helpers.mock_ollama import _finish_chat, end_ndjson, start_ndjson, write_ndjson_line
    from tests.helpers.mock_openai import ClientDisconnected
    name = str((body or {}).get("model") or "")
    show = (getattr(mock, "pullable", {}) or {}).get(name)
    if show is None and name.startswith("hf.co/"):
        show = HF_SHOW
    if show is None:
        _finish_chat(handler, [{"status": "pulling manifest"}, {"error": "pull model manifest: file does not exist"}])
        return
    delay = float(getattr(mock, "pull_delay_s", 0.0) or 0.0)
    start_ndjson(handler)
    try:
        for line in script(name):
            if delay:
                time.sleep(delay)
            write_ndjson_line(handler, line)
    except ClientDisconnected:
        with mock._lock:
            mock.pull_cancelled.append(name)
        return
    _add(mock, name, show)
    end_ndjson(handler)


def apply_copy(mock, body: dict) -> "tuple[int, dict]":
    src, dst = str((body or {}).get("source") or ""), str((body or {}).get("destination") or "")
    with mock._lock:
        key = next((k for k in (src, _norm(src)) if k in mock.show_responses), None)
        if key is None or not dst:
            return 404, {"error": f"model '{src}' not found"}
        mock.show_responses[_norm(dst)] = json.loads(json.dumps(mock.show_responses[key]))
        tags = mock.tags_response.setdefault("models", [])
        base = next((t for t in tags if _norm(t.get("model") or t.get("name") or "") == _norm(src)), {"size": 1})
        tags[:] = [t for t in tags if _norm(t.get("model") or t.get("name") or "") != _norm(dst)]
        tags.append({**json.loads(json.dumps(base)), "name": _norm(dst), "model": _norm(dst)})
        mock.copied.append((src, dst))
    return 200, {}
