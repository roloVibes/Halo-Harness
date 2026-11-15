"""tests.helpers.mock_ollama_loads -- Halo 3.6.0.0 R8: a fake Ollama that counts loads.

`LoadCountingOllama` is `tests/helpers/mock_ollama.MockUpstream` (loopback only, never a real Ollama, never a real
model) with a resident set the way a real server keeps one: a `/api/chat` or `/api/generate` for a model that is not
resident, or resident at another window (`options.num_ctx`) or another `num_gpu`, is a LOAD (a reload when it was
resident); `/api/generate` with `keep_alive: 0` is an UNLOAD; `/api/ps` lists what is resident with its
`context_length`, `size` and `size_vram` (fully on the card unless `vram` says otherwise). A non-streaming
`/api/chat` with `num_predict: 1` is a calibration step (Halo's own `ollama_calibrate_steps._load_model_at_num_ctx`).

    fake = LoadCountingOllama({"tiny:1b": {"size_gb": 1.0, "trained": 262144}}).start()
    fake.preload("tiny:1b", 65536)          # another client loaded it at 65,536
    fake.loads / fake.unloads / fake.calibrates / fake.keep_alives    what Halo asked for
    fake.cold_load_s = 0.5                  # a load takes this long (the reply waits)

Every chat answers "ready" with Ollama's real `prompt_eval_count` (`mock_ollama._real_prompt_count`) unless
`count_ratio` scales it (a model whose tokenizer is denser or looser than chars / 3.5).
"""
from __future__ import annotations

import json
import time

from tests.helpers.mock_ollama import MockUpstream, _finish_chat, _real_prompt_count

DEFAULT_CTX = 4096
GB = 1024 ** 3


def _row(name: str, spec: dict) -> dict:
    return {"name": name, "model": name, "modified_at": "2026-01-01T00:00:00Z", "size": int(spec["size_gb"] * GB),
            "digest": spec.get("digest") or f"sha256:{abs(hash(name)) % 10 ** 12:012d}",
            "details": {"family": "qwen3", "families": ["qwen3"], "parameter_size": spec.get("params", "1B"),
                        "quantization_level": "Q4_K_M", "format": "gguf"}}


def _show(spec: dict) -> dict:
    return {"modelfile": "", "parameters": "", "template": "", "capabilities": ["completion", "tools"],
            "details": {"family": "qwen3", "quantization_level": "Q4_K_M"},
            "model_info": {"qwen3.context_length": spec.get("trained", 262144), "qwen3.block_count": 28}}


class LoadCountingOllama(MockUpstream):
    def __init__(self, models: dict, **kw):
        tags = {"models": [_row(n, s) for n, s in models.items()]}
        show = {n: _show(s) for n, s in models.items()}
        super().__init__(tags_response=tags, show_responses=show, **kw)
        self.models = dict(models)
        self.resident: dict = {}      # model -> {"num_ctx", "num_gpu", "keep_alive"}
        self.loads: list = []         # {"model", "num_ctx", "num_gpu", "kind", "was"}
        self.unloads: list = []       # {"model", "how"}
        self.calibrates: list = []    # {"model", "num_ctx"}
        self.keep_alives: list = []   # {"model", "keep_alive", "path"}: every keep_alive a request carried
        self.cold_load_s = 0.0
        self.first_load_s = 0.0       # the server's first load only (a cold start)
        self.slow_at = {}             # num_ctx -> seconds EVERY request at that window waits (a load that never ends)
        self.count_ratio = 1.0
        self.vram = {}                # model -> callable(num_ctx) -> (size, size_vram)
        for name in models:
            self.scenarios[name] = self._answer

    # -- the server's state --------------------------------------------------------------------------------
    def preload(self, model: str, num_ctx: int, num_gpu=None) -> None:
        with self._lock:
            self.resident[model] = {"num_ctx": num_ctx, "num_gpu": num_gpu, "keep_alive": None}

    def _size(self, model: str, num_ctx: int) -> "tuple[int, int]":
        fn = self.vram.get(model)
        if fn is not None:
            return fn(num_ctx)
        weights = int(float((self.models.get(model) or {}).get("size_gb") or 1.0) * GB)
        size = weights + int(num_ctx) * 64 * 1024  # a KV cache that grows with the window
        return size, size

    def ps_snapshot(self) -> dict:
        with self._lock:
            rows = []
            for model, r in self.resident.items():
                size, size_vram = self._size(model, r["num_ctx"])
                rows.append({"name": model, "model": model, "size": size, "size_vram": size_vram,
                             "context_length": r["num_ctx"], "expires_at": "2318-01-01T00:00:00Z",
                             "digest": next((x["digest"] for x in self.tags_response["models"]
                                             if x["model"] == model), "")})
        return {"models": rows}

    def observe(self, method: str, path: str, body) -> None:
        if method != "POST" or path not in ("/api/chat", "/api/generate") or not isinstance(body, dict):
            return
        model = body.get("model")
        if model not in self.models:
            return
        opts = body.get("options") if isinstance(body.get("options"), dict) else {}
        keep = body.get("keep_alive")
        slow = False
        with self._lock:
            if keep is not None:
                self.keep_alives.append({"model": model, "keep_alive": keep, "path": path})
            if path == "/api/generate" and keep in (0, "0", "0s"):
                if self.resident.pop(model, None) is not None:
                    self.unloads.append({"model": model, "how": "keep_alive 0"})
                return
            calibrate = path == "/api/chat" and body.get("stream") is False and opts.get("num_predict") == 1
            if calibrate:
                self.calibrates.append({"model": model, "num_ctx": opts.get("num_ctx")})
            num_ctx = int(opts.get("num_ctx") or DEFAULT_CTX)
            num_gpu = opts.get("num_gpu")
            was = self.resident.get(model)
            # Ollama reloads a runner whose options differ: the window, and `num_gpu` (absent = the server's own)
            if was is None or was["num_ctx"] != num_ctx or was.get("num_gpu") != num_gpu:
                kind = "calibrate" if calibrate else "request"
                self.loads.append({"model": model, "num_ctx": num_ctx, "num_gpu": num_gpu, "kind": kind,
                                   "was": dict(was) if was else None, "path": path})
                self.resident[model] = {"num_ctx": num_ctx, "num_gpu": num_gpu, "keep_alive": keep}
                slow = self.cold_load_s + (self.first_load_s if len(self.loads) == 1 else 0.0)
            slow = (slow or 0.0) + float(self.slow_at.get(num_ctx) or 0.0)
        if slow:
            time.sleep(slow)

    # -- the reply -----------------------------------------------------------------------------------------
    def _answer(self, handler, body) -> None:
        if body.get("stream") is False:
            from tests.helpers.mock_ollama import send_json
            send_json(handler, 200, {"model": body.get("model"), "done": True, "done_reason": "length",
                                     "message": {"role": "assistant", "content": "r"},
                                     "prompt_eval_count": 11, "eval_count": 1, "load_duration": 1000})
            return
        real = max(1, int(_real_prompt_count(body) * self.count_ratio))
        self.real_prompt_counts = False  # the count below is the one this fake reads
        _finish_chat(handler, [{"message": {"role": "assistant", "content": "ready"}, "done": True,
                                "done_reason": "stop", "prompt_eval_count": real,
                                "prompt_eval_duration": 50_000_000, "eval_count": 2, "eval_duration": 10_000_000,
                                "load_duration": 1_000_000, "total_duration": 70_000_000}])

    def summary(self) -> str:
        return json.dumps({"loads": self.loads, "unloads": self.unloads, "calibrates": len(self.calibrates),
                           "keep_alives": self.keep_alives, "resident": self.resident}, default=str)[:1500]
