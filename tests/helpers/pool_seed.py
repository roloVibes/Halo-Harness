"""tests.helpers.pool_seed -- Halo 3.3.8.0 R4: the pool's controller logs for the steward's pool findings
(ollama_steward/rules_pool.py; tests/test_steward_rules_pool.py), and a stopped-but-recorded pool to read them with.

Every line is WRITTEN FROM llama.cpp's source wording (from memory: `llama_model_load_from_file_impl: using device`,
`load_tensors: <dev> model buffer size`, `llama_kv_cache: <dev> KV buffer size`, ggml-rpc.cpp's RPC_STATUS_ASSERT
abort "Remote RPC server crashed or returned malformed response", its "Failed to connect to <host>:<port>", the
server's slot print_timing lines) and the research doc's figures; none is copied from a live log -- no rpc-server or
pooled llama-server has run here. Addresses are 192.0.2.x placeholders.

    LOAD(split_mib, offloaded="49/49")   the load block of a 3-device pool (two RPC workers, this machine's CUDA0)
    DEGRADED, SLOW, HEALTHY_TIMING       the lines after it
    seed(state, text, *, rtt_ms=0.4, link=None) -> the log path    the `pool` entry (its `log`) and run.json written
        as a launch leaves them (members worker1, worker2, me; split 0.42 / 0.42 / 0.16), no process
    card(state, tok_s) -> the pool's speed card as `halo local bench --host pool` writes it (8k and 32k at tok_s)
"""
from __future__ import annotations

import time
from pathlib import Path

ARGV = ("--- halo starts: /opt/llama/llama-server -m /models/Qwen3-Next-80B-A3B-Instruct-Q4_K_M.gguf --alias "
        "qwen3-next-80b-a3b-q4km --rpc 192.0.2.11:50052,192.0.2.12:50052 --tensor-split 0.42,0.42,0.16 -ngl 999 "
        "--host 192.0.2.5 --port 8090 --api-key-file /state/pool/api-key -c 32768")


def LOAD(mib=(19783.12, 19783.12, 7536.43), offloaded: str = "49/49", cpu_mib: float = 315.30) -> str:
    w1, w2, me = mib
    return "\n".join([
        ARGV,
        "build: 7300 (fa1ec0de) with cc (GCC) 13.2.0 for x86_64-linux-gnu",
        "llama_model_load_from_file_impl: using device RPC[192.0.2.11:50052] (RPC[192.0.2.11:50052]) - 24320 MiB free",
        "llama_model_load_from_file_impl: using device RPC[192.0.2.12:50052] (RPC[192.0.2.12:50052]) - 24320 MiB free",
        "llama_model_load_from_file_impl: using device CUDA0 (a 12 GB card) - 11010 MiB free",
        "srv    load_model: loading model '/models/Qwen3-Next-80B-A3B-Instruct-Q4_K_M.gguf'",
        "load_tensors: offloading 48 repeating layers to GPU",
        f"load_tensors: offloaded {offloaded} layers to GPU",
        f"load_tensors:   CPU_Mapped model buffer size = {cpu_mib:10.2f} MiB",
        f"load_tensors: RPC[192.0.2.11:50052] model buffer size = {w1:10.2f} MiB",
        f"load_tensors: RPC[192.0.2.12:50052] model buffer size = {w2:10.2f} MiB",
        f"load_tensors:        CUDA0 model buffer size = {me:10.2f} MiB",
        "llama_context: n_ctx         = 32768",
        "llama_context: n_ctx_per_seq = 32768",
        "llama_kv_cache: RPC[192.0.2.11:50052] KV buffer size =  1344.00 MiB",
        "llama_kv_cache: RPC[192.0.2.12:50052] KV buffer size =  1344.00 MiB",
        "llama_kv_cache:        CUDA0 KV buffer size =   512.00 MiB",
        "srv          init: initializing slots, n_slots = 1",
        "slot         init: id  0 | task -1 | new slot n_ctx_slot = 32768",
        "main: model loaded",
        "main: server is listening on http://192.0.2.5:8090 - starting the main loop",
        "srv  update_slots: all slots are idle"]) + "\n"


def _timing(tok_s: float, n: int = 200) -> str:
    ms = n / tok_s * 1000.0
    return ("slot print_timing: id  0 | task 3 | \n"
            "prompt eval time =    9830.00 ms /  4915 tokens (    2.00 ms per token,   500.00 tokens per second)\n"
            f"       eval time = {ms:10.2f} ms / {n:5d} tokens ({ms / n:8.2f} ms per token, {tok_s:8.2f} tokens per "
            "second)\n"
            "srv  log_server_r: request: POST /v1/chat/completions 192.0.2.5 200\n")


HEALTHY_TIMING = "".join(_timing(11.2) for _ in range(4))
SLOW = "".join(_timing(5.0) for _ in range(4))
DEGRADED = ("slot launch_slot_: id  0 | task 9 | processing task\n"
            "Failed to connect to 192.0.2.12:50052\n"
            "/src/ggml/src/ggml-rpc/ggml-rpc.cpp:579: Remote RPC server crashed or returned malformed response\n")


def seed(state, text: str, *, rtt_ms: float = 0.4, link=None) -> Path:
    from halo_harness.local_pool import entry, launch
    log = Path(state) / "local" / "servers" / "pool-8090.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(text, encoding="utf-8")
    entry.write(url="http://127.0.0.1:8090/v1", model="qwen3-next-80b-a3b-q4km", ctx=32768, log=str(log),
                members=["worker1", "worker2", "me"], cache="f16")
    launch._save({"model": "qwen3-next-80b-a3b-q4km", "display": "Qwen3-Next-80B-A3B Q4_K_M", "pid": None,
                  "port": 8090, "url": "http://127.0.0.1:8090/v1", "log": str(log), "ctx": 32768, "cache": "f16",
                  "members": ["worker1", "worker2", "me"], "order": ["worker1", "worker2", "me"],
                  "split": [0.42, 0.42, 0.16], "started": time.time() - 600,
                  "rpc": [{"member": "worker1", "addr": "192.0.2.11:50052", "rtt_ms": rtt_ms, "link": link},
                          {"member": "worker2", "addr": "192.0.2.12:50052", "rtt_ms": rtt_ms, "link": link}]}, state)
    return log


def card(state, tok_s: float) -> dict:
    from halo_harness.providers.local_bench_runs import save
    c = {"pool": True, "model": "qwen3-next-80b-a3b-q4km", "host": "pool", "digest": "pool|qwen3-next-80b-a3b-q4km",
         "at": time.time(), "members": ["worker1", "worker2", "me"], "split": [0.42, 0.42, 0.16], "cache": "f16",
         "ctx": 32768, "cold_load_s": 33.0, "windows": [{"window": w, "tok_s": tok_s, "prompt_tok_s": 500.0,
                                                          "ttft_ms": 9830, "on_gpu": True} for w in (8192, 32768)]}
    save(state, c)
    return c
