"""tests.helpers.servers_seed -- Halo 3.3.8.0 R2: a fresh home with local servers (a llama-server Halo started, a
manual LM Studio entry, a manual mlx_lm.server entry with its `log`) and their logs written by hand in each runtime's
format, for the steward's server tests (tests/test_server_log_hf.py, test_server_rules_hf.py, test_local_log_cli.py).
The LM Studio folder is a fake under the scratch home (never the real ~/.lmstudio). Nothing is sent anywhere; no server
is started: the registry row's pid is one no process has.

The formats are written from memory of llama.cpp's server (b5xxx-b6xxx), LM Studio 0.3.x's server-logs file and
mlx_lm.server (Python's http.server + logging): unverified against a live server this round.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "OLLAMA_HOST", "BRIDGE_TEST_NO_BACKGROUND_NET")
DEAD_PID = 2 ** 22 + 12345

LLAMA_LOG = """--- halo starts: /opt/llama/llama-server -m /models/Qwen3-8B-Q4_K_M.gguf --alias qwen3-8b --port 8080 -c 16384 -ngl 99 -np 2
build: 6123 (abcdef12) with cc (GCC) 13.2.0 for x86_64-linux-gnu
main: HTTP server is listening, hostname: 127.0.0.1, port: 8080, http threads: 15
main: loading model
srv    load_model: loading model '/models/Qwen3-8B-Q4_K_M.gguf'
ggml_cuda_init: found 1 CUDA devices:
  Device 0: a 10 GB card, compute capability 8.6, VMM: yes
llama_model_loader: loaded meta data with 32 key-value pairs and 399 tensors from /models/Qwen3-8B-Q4_K_M.gguf (version GGUF V3 (latest))
load_tensors: offloaded 30/37 layers to GPU
llama_context: n_ctx         = 16384
llama_context: n_ctx_per_seq = 8192
srv          init: initializing slots, n_slots = 2
slot         init: id  0 | task -1 | new slot n_ctx_slot = 8192
main: model loaded
main: server is listening on http://127.0.0.1:8080 - starting the main loop
srv  update_slots: all slots are idle
slot launch_slot_: id  0 | task 0 | processing task
slot update_slots: id  0 | task 0 | input truncated, n_ctx = 8192, n_keep = 0, n_left = 8192, n_prompt_tokens = 4560
prompt eval time =    1234.56 ms /  4560 tokens (    0.27 ms per token,  3693.66 tokens per second)
       eval time =    9876.54 ms /   512 tokens (   19.29 ms per token,    51.84 tokens per second)
slot process_toke: id  0 | task 0 | stopped by limit, n_predict = 512
srv  log_server_r: request: POST /v1/chat/completions 127.0.0.1 200
"""

LLAMA_CRASH = """ggml_backend_cuda_buffer_type_alloc_buffer: allocating 2048.00 MiB on device 0: cudaMalloc failed: out of memory
srv  log_server_r: request: POST /v1/chat/completions 127.0.0.1 500
/src/ggml/src/ggml-cuda/ggml-cuda.cu:75: GGML_ASSERT(err == cudaSuccess) failed: CUDA error
"""

LMS_LOG = """[{T0}][INFO] [LM STUDIO SERVER] Success! HTTP server listening on port 1234
[{T1}][INFO] [LM STUDIO SERVER] [qwen2.5-7b-instruct] Running chat completion on conversation with 12 messages.
[{T1}][ERROR] [qwen2.5-7b-instruct] Trying to keep the first 5210 tokens when context the overflows. However, the model is loaded with context length of only 4096 tokens, which is not enough. Try to load the model with a larger context length, or provide a shorter input
[{T2}][INFO] [LM STUDIO SERVER] [qwen2.5-7b-instruct] Generated prediction: {"id": "chatcmpl-1", "choices": [{"index": 0, "finish_reason": "length"}]}
[{T2}][ERROR] [qwen2.5-7b-instruct] The model has crashed without additional information. (Exit code: 18446744072635812000)
"""

MLX_LOG = """{P0},001 - INFO - Starting httpd at 127.0.0.1 on port 8081...
127.0.0.1 - - [{H0}] "POST /v1/chat/completions HTTP/1.1" 200 -
[METAL] Command buffer execution failed: Insufficient Memory (00000008:kIOGPUCommandBufferCallbackErrorOutOfMemory)
Traceback (most recent call last):
ValueError: [metal::malloc] Attempting to allocate 21474836480 bytes which is greater than the maximum allowed buffer size
127.0.0.1 - - [{H1}] "POST /v1/chat/completions HTTP/1.1" 500 -
libc++abi: terminating due to uncaught exception of type std::runtime_error
"""


def lms_log(ago: float = 900.0) -> str:
    """LM Studio's fixture with its timestamps in the last quarter hour (the rules read the last 24 h)."""
    import time
    stamp = lambda s: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - s))  # noqa: E731
    return LMS_LOG.replace("{T0}", stamp(ago)).replace("{T1}", stamp(ago - 60)).replace("{T2}", stamp(ago - 120))


def mlx_log(ago: float = 900.0) -> str:
    """mlx_lm.server's fixture with its timestamps in the last quarter hour."""
    import time
    t = lambda s, f: time.strftime(f, time.localtime(time.time() - s))  # noqa: E731
    return (MLX_LOG.replace("{P0}", t(ago, "%Y-%m-%d %H:%M:%S")).replace("{H0}", t(ago - 5, "%d/%b/%Y %H:%M:%S"))
            .replace("{H1}", t(ago - 60, "%d/%b/%Y %H:%M:%S")))


class Home:
    """A scratch home: `llama` (a server Halo started, its registry row and log), `lms` (manual, LM Studio on 1234, its
    fake server-logs folder under the home), `mlx` (manual, its `log` path); `voice` (3.3.9.0 R1, off by default): the
    speech servers `stt` and `tts` (tests/helpers/servers_seed_voice.py)."""

    def __init__(self, *, llama: bool = True, lms: bool = True, mlx: bool = True, pid: int = DEAD_PID,
                 extra: "dict | None" = None, voice: bool = False):
        self.want, self.pid, self.extra = {"llama": llama, "lms": lms, "mlx": mlx, "voice": voice}, pid, extra or {}

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in _VARS}
        self.root = Path(tempfile.mkdtemp(prefix="hv_servers-")).resolve()
        self.state = self.root / ".halo"
        self.state.mkdir(parents=True)
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), BRIDGE_STATE_DIR=str(self.state),
                          OLLAMA_HOST="http://127.0.0.1:9", BRIDGE_TEST_NO_BACKGROUND_NET="1")
        servers = []
        if self.want["lms"]:
            servers.append({"name": "studio", "url": "http://127.0.0.1:1234/v1"})
            d = self.root / ".lmstudio" / "server-logs" / "2026-10"
            d.mkdir(parents=True)
            (d / "2026-10-29.1.log").write_text("[2026-10-29 09:00:00][INFO] [LM STUDIO SERVER] old day\n", encoding="utf-8")
            self.lms_log = d / "2026-10-30.1.log"
            self.lms_log.write_text(lms_log(), encoding="utf-8")
            os.utime(d / "2026-10-29.1.log", (1, 1))
        if self.want["mlx"]:
            self.mlx_log = self.root / "mlx.log"
            self.mlx_log.write_text(mlx_log(), encoding="utf-8")
            servers.append({"name": "mac-mlx", "url": "http://127.0.0.1:8081/v1", "runtime": "mlx", "log": str(self.mlx_log)})
        cfg = {"ollama": {"hosts": [{"name": "pc", "url": "http://192.0.2.10:11434"}]},
               "huggingface": {"local_servers": servers}}
        for section, values in self.extra.items():
            cfg.setdefault(section, {}).update(values)
        (self.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        if self.want["llama"]:
            self.llama_log = self.state / "local" / "servers" / "llama-8080.log"
            self.llama_log.parent.mkdir(parents=True)
            self.llama_log.write_text(LLAMA_LOG, encoding="utf-8")
            row = {"id": "llama-8080", "kind": "llama-server", "runtime": "llama-server", "model": "qwen3-8b", "port": 8080,
                   "pid": self.pid, "base_url": "http://127.0.0.1:8080/v1", "log": str(self.llama_log), "halo": True,
                   "cmdline": ["/opt/llama/llama-server", "-m", "/models/Qwen3-8B-Q4_K_M.gguf", "--alias", "qwen3-8b",
                               "--port", "8080", "-c", "16384", "-ngl", "99", "-np", "2"]}
            (self.state / "run").mkdir(parents=True, exist_ok=True)
            (self.state / "run" / "local-servers.json").write_text(json.dumps([row]), encoding="utf-8")
        if self.want["voice"]:  # 3.3.9.0 R1: the speech servers stt and tts (tests/helpers/servers_seed_voice.py)
            from tests.helpers.servers_seed_voice import seed
            seed(self)
        from halo_harness.ollama_steward import server_log_hf, servers_hf
        from halo_harness.providers import huggingface_local_probe as P
        self._probe, P._auto_detect_cache = P._auto_detect_cache, None  # another module's sweep is not this home's
        servers_hf.reset()
        server_log_hf.reset()
        return self

    def __exit__(self, *exc):
        from halo_harness.ollama_steward import server_log_hf, servers_hf
        from halo_harness.providers import huggingface_local_probe as P
        P._auto_detect_cache = self._probe
        servers_hf.reset()
        server_log_hf.reset()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def server(self, name: str):
        from halo_harness.ollama_steward.servers_hf import by_name
        return by_name(name, self.state)

    def append(self, path: Path, text: str) -> None:
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def calls(self, *lines) -> None:
        from halo_harness.ollama_steward.ledger import append_lines
        append_lines(self.state, list(lines))


def hf_line(url: str = "http://127.0.0.1:8080/v1", model: str = "qwen3-8b", ago: float = 600.0, **kw) -> dict:
    """A ledger line of an hf:local call (the OpenAI dialect: no num_ctx sent; the counts from `usage`)."""
    import time
    from halo_harness.ollama_steward.ledger import blank_line, now_iso
    from halo_harness.ollama_steward.ledger_call import _netloc
    base = {"host": {"name": _netloc(url), "url": url}, "model": model, "dialect": "openai", "status": 200,
            "num_ctx_sent": None, "prompt_eval_count": 3000, "eval_count": 300, "kind": "turn", "session": "s1",
            "window_source": "server default", "at": now_iso(time.time() - ago)}
    return blank_line(**{**base, **kw})
