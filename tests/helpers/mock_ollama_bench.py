"""tests.helpers.mock_ollama_bench -- Halo 3.3.6.0 R5: a scripted fake Ollama for the bench
(halo_harness/providers/local_bench.py) on tests/helpers/mock_ollama.MockUpstream: streamed `/api/chat` answers with
realistic durations per window, a load whenever `num_ctx` changes (Ollama reloads at a new window), the first call
after a load slow (graph capture: the warm-up), `/api/ps` listing the model at the window it was loaded at -- every
byte on the GPU up to the model's `gpu_up_to`, past it 80 % (a scripted spill at the ceiling) -- and a reply of
`reply` tokens cut at `num_predict` (`done_reason: length`). Never a literal LAN address.

    install(mock, names=None)    the models' /api/tags rows, /api/show answers and the chat scenario
    MODELS[name] = {size, info, gpu_up_to, load_s, reply, tok_s, prompt_tok_s}
    script_seconds(mock) -> the server-side seconds the scripted calls took (load + prompt + reply)
"""

from __future__ import annotations

import json

from tests.helpers.mock_ollama import _finish_chat, _real_prompt_count
from tests.helpers.steward_seed import CODER30, QWEN9

MODELS = {
    "bn-coder:30b": {"size": 18554258719, "info": {**CODER30, "qwen3moe.context_length": 262144}, "family": "qwen3moe",
                     "gpu_up_to": 32768, "load_s": 21.0, "reply": 200, "tok_s": 190.0, "prompt_tok_s": 2400.0},
    "bn-small:9b": {"size": 6600000000, "info": {**QWEN9, "qwen35.context_length": 65536}, "family": "qwen35",
                    "gpu_up_to": 10 ** 7, "load_s": 6.5, "reply": 200, "tok_s": 120.0, "prompt_tok_s": 3000.0},
    "bn-thinker:9b": {"size": 6600000000, "info": {**QWEN9, "qwen35.context_length": 32768}, "family": "qwen35",
                      "gpu_up_to": 10 ** 7, "load_s": 7.0, "reply": 420, "tok_s": 95.0, "prompt_tok_s": 2800.0},
}


# 3.6.0.25 T: the sweep's models (installed only when named): `per_ctx` bytes per window token, `cliff_at` -- past it
# the load still reads wholly on the card (Windows' shared memory) but the reply speed is a third
SWEEP = {
    "sw-up:8b": {"size": 5 * 2 ** 30, "info": {**QWEN9, "qwen35.context_length": 131072}, "family": "qwen35",
                 "gpu_up_to": 65536, "load_s": 5.0, "reply": 200, "tok_s": 120.0, "prompt_tok_s": 3000.0,
                 "per_ctx": 98304},
    "sw-cliff:8b": {"size": 5 * 2 ** 30, "info": {**QWEN9, "qwen35.context_length": 131072}, "family": "qwen35",
                    "gpu_up_to": 10 ** 7, "cliff_at": 49152, "load_s": 5.0, "reply": 200, "tok_s": 120.0,
                    "prompt_tok_s": 3000.0, "per_ctx": 98304},
    "sw-short:8b": {"size": 5 * 2 ** 30, "info": {**QWEN9, "qwen35.context_length": 40960}, "family": "qwen35",
                    "gpu_up_to": 10 ** 7, "load_s": 5.0, "reply": 200, "tok_s": 120.0, "prompt_tok_s": 3000.0,
                    "per_ctx": 98304},
    "sw-new:8b": {"size": 5 * 2 ** 30, "info": {**QWEN9, "qwen35.context_length": 131072}, "family": "qwen35",
                  "gpu_up_to": 10 ** 7, "load_s": 5.0, "reply": 200, "tok_s": 120.0, "prompt_tok_s": 3000.0,
                  "per_ctx": 98304, "fail": "unknown model architecture: 'qwen99'"},
    # the repair after the check: trained past Halo's 131,072 cap; a header without its trained window; a tag that
    # carries the user name of the scrub's tests and an Ollama error that carries a path
    "sw-long:4b": {"size": 3 * 2 ** 30, "info": {**QWEN9, "qwen35.context_length": 262144}, "family": "qwen35",
                   "gpu_up_to": 10 ** 7, "load_s": 5.0, "reply": 200, "tok_s": 120.0, "prompt_tok_s": 3000.0,
                   "per_ctx": 8192},
    "sw-nohead:8b": {"size": 5 * 2 ** 30, "info": dict(QWEN9), "family": "qwen35", "gpu_up_to": 10 ** 7, "load_s": 5.0,
                     "reply": 200, "tok_s": 120.0, "prompt_tok_s": 3000.0, "per_ctx": 98304},
    "tester-coder:8b": {"size": 5 * 2 ** 30, "info": {**QWEN9, "qwen35.context_length": 131072}, "family": "qwen35",
                        "gpu_up_to": 10 ** 7, "load_s": 5.0, "reply": 200, "tok_s": 120.0, "prompt_tok_s": 3000.0,
                        "per_ctx": 98304, "fail": "open /data/ollama/models/blobs/sha256-ab12: no such file or directory"},
}


def spec(name: str) -> dict:
    return MODELS.get(name) or SWEEP[name]


def _rates(m: dict, window: int, spilled: bool) -> "tuple[float, float]":
    fill = max(0.55, 1.0 - window / 262144.0)  # the decode rate falls as the window grows
    tok, pp = m["tok_s"] * fill, m["prompt_tok_s"] * fill
    if m.get("cliff_at") and window > m["cliff_at"]:
        return tok / 3.0, pp / 3.0
    return (tok / 4.5, pp / 6.0) if spilled else (tok, pp)


def scenario(name: str):
    def fn(h, body):
        mock, m = h.server.mock, spec(name)
        if m.get("fail"):  # a runtime that cannot load it: Ollama's 500 with its error
            data = json.dumps({"error": m["fail"]}).encode("utf-8")
            h.send_response(500)
            h.send_header("Content-Type", "application/json")
            h.send_header("Content-Length", str(len(data)))
            h.end_headers()
            h.wfile.write(data)
            return
        opts = body.get("options") or {}
        window, predict = int(opts.get("num_ctx") or 2048), int(opts.get("num_predict") or 128)
        with mock._lock:
            st = mock.bench_state.setdefault(name, {"ctx": None, "loads": 0, "fresh": False})
            load_ns = 1e6
            if st["ctx"] != window:
                load_ns = (m["load_s"] if st["loads"] == 0 else m["load_s"] * 0.6) * 1e9
                st.update(ctx=window, loads=st["loads"] + 1, fresh=True)
                size = m["size"] + window * m.get("per_ctx", 49152)
                vram = size if window <= m["gpu_up_to"] else int(size * 0.8)
                rest = [e for e in (mock.ps_response or {}).get("models") or [] if e.get("model") != name]
                mock.ps_response = {"models": rest + [{"model": name, "name": name, "size": size, "size_vram": vram,
                                                       "context_length": window}]}
            warm, st["fresh"] = st["fresh"], False
        spilled = window > m["gpu_up_to"]
        tok, pp = _rates(m, window, spilled)
        prompt = _real_prompt_count(body)
        n = min(predict, 8 if predict <= 8 else m["reply"])
        if warm:  # the first call after a load: graph capture, 5.7 tok/s
            tok, pp = 5.7, pp / 3
        dur, pdur = n / tok * 1e9, prompt / pp * 1e9
        with mock._lock:
            mock.bench_seconds = getattr(mock, "bench_seconds", 0.0) + (load_ns + dur + pdur) / 1e9
            mock.bench_calls.append((name, window, predict, warm))
        _finish_chat(h, [{"model": name, "message": {"role": "assistant", "content": "word " * 4}, "done": False},
                         {"model": name, "message": {"role": "assistant", "content": ""}, "done": True,
                          "done_reason": "length" if n >= predict and m["reply"] > predict else "stop",
                          "total_duration": int(load_ns + dur + pdur), "load_duration": int(load_ns),
                          "prompt_eval_count": "real", "prompt_eval_duration": int(pdur), "eval_count": n,
                          "eval_duration": int(dur)}])
    return fn


def row(name: str) -> dict:
    m = spec(name)
    return {"name": name, "model": name, "modified_at": "2026-10-01T00:00:00Z", "size": m["size"],
            "digest": "sha256:" + name.replace(":", "-"),
            "details": {"family": m["family"], "families": [m["family"]], "parameter_size": name.split(":")[1].upper(),
                        "quantization_level": "Q4_K_M", "format": "gguf"}}


def install(mock, names=None, *, version: str = "0.40.13") -> None:
    names = list(names or MODELS)
    mock.bench_state, mock.bench_calls, mock.bench_seconds = {}, [], 0.0
    mock.version_response = {"version": version}
    mock.tags_response = {"models": [row(n) for n in names]}
    mock.ps_response = {"models": []}
    for n in names:
        mock.show_responses[n] = {"modelfile": "", "parameters": "", "template": "", "capabilities": ["completion", "tools"],
                                  "details": row(n)["details"], "model_info": spec(n)["info"]}
        mock.scenarios[n] = scenario(n)


def script_seconds(mock) -> float:
    return round(getattr(mock, "bench_seconds", 0.0), 1)
