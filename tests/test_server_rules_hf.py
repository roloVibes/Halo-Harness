"""tests.test_server_rules_hf -- Halo 3.3.8.0 R2: what llama-server, LM Studio and mlx_lm.server print, turned into the
steward's events (ollama_steward/server_rules_hf.py, server_context_hf.py) and findings (rules_servers.py): each
runtime's lines by kind, the kinds it never prints ("not asked"), the window per slot from the load, and the findings
keyed `<server>|<model>` with `server` and `runtime`: the window (Halo's window to the server's, `--ctx-size` said with
`applied: false`), the server's own n_predict, a spill, the tool budget, a crash that repeats with the runtime's
lines. Fixture lines written by hand from each runtime's format (unverified against a live server).
Run: python -m tests.test_server_rules_hf
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.servers_seed import LLAMA_CRASH, Home, hf_line  # noqa: E402

test, TESTS = new_registry()


def _kind(line, runtime):
    from halo_harness.ollama_steward.server_rules_hf import classify
    ev = classify(line, runtime=runtime)
    return ev["kind"] if ev else None


@test
def test_each_runtimes_lines_by_kind(ctx: Ctx):
    llama = {"slot update_slots: id  0 | task 0 | input truncated, n_ctx = 8192, n_keep = 0, n_left = 8192, "
             "n_prompt_tokens = 4560": "prompt-trimmed",
             "slot update_slots: id  0 | task 3 | context shift, n_keep = 0, n_left = 8190, n_discard = 4095": "prompt-trimmed",
             "srv  send_error: task id = 7, error: the request exceeds the available context size, try increasing it": "prompt-trimmed",
             "slot process_toke: id  0 | task 0 | stopped by limit, n_predict = 512": "reply-cut",
             "slot process_toke: id  0 | task 0 | stopped by limit, n_decoded = 512, n_predict = 512": "reply-cut",
             "load_tensors: offloaded 30/37 layers to GPU": "cpu-spill",
             "load_tensors: offloaded 37/37 layers to GPU": None,
             "ggml_backend_cuda_buffer_type_alloc_buffer: allocating 2048.00 MiB on device 0: cudaMalloc failed: out of memory": "gpu-memory",
             "srv    load_model: failed to load model, '/models/x.gguf'": "load-failed",
             "srv  log_server_r: request: POST /v1/chat/completions 127.0.0.1 500": "http-500",
             "srv  log_server_r: request: POST /v1/chat/completions 127.0.0.1 200": None,
             "/src/ggml-cuda.cu:75: GGML_ASSERT(err == cudaSuccess) failed": "other-error",
             "ggml_cuda_init: found 1 CUDA devices:": None, "--- halo starts: llama-server -m x.gguf": None}
    for line, want in llama.items():
        ctx.check(f"llama-server: {line[:60]!r} -> {want}", _kind(line, "llama-server") == want)
    lms = {"[2026-10-30 14:03:02][ERROR] Trying to keep the first 5210 tokens when context the overflows. However, the "
           "model is loaded with context length of only 4096 tokens, which is not enough.": "prompt-trimmed",
           '[2026-10-30 14:05:40][INFO] Generated prediction: {"choices": [{"finish_reason": "length"}]}': "reply-cut",
           "[2026-10-30 14:09:13][ERROR] The model has crashed without additional information. (Exit code: 1)": "other-error",
           "[2026-10-30 14:09:20][ERROR] Error loading model.": "load-failed",
           "[2026-10-30 14:02:11][INFO] [LM STUDIO SERVER] Success! HTTP server listening on port 1234": None}
    for line, want in lms.items():
        ctx.check(f"LM Studio: {line[22:80]!r} -> {want}", _kind(line, "lmstudio") == want)
    mlx = {'127.0.0.1 - - [30/Oct/2026 14:11:05] "POST /v1/chat/completions HTTP/1.1" 500 -': "http-500",
           "[METAL] Command buffer execution failed: Insufficient Memory (00000008)": "gpu-memory",
           "ValueError: [metal::malloc] Attempting to allocate 21474836480 bytes": "other-error",
           "libc++abi: terminating due to uncaught exception": "other-error",
           "load_tensors: offloaded 30/37 layers to GPU": None}
    for line, want in mlx.items():
        ctx.check(f"mlx: {line[:60]!r} -> {want}", _kind(line, "mlx") == want)


@test
def test_the_kinds_a_runtime_never_prints_are_not_asked(ctx: Ctx):
    from halo_harness.ollama_steward.server_rules_hf import can_say, not_asked
    ctx.check("mlx never says a cut prompt or a spill", {"prompt-trimmed", "cpu-spill"} <= set(not_asked("mlx")))
    ctx.check("llama-server says them all", not not_asked("llama-server"))
    ctx.check("LM Studio: a spill is not in its server log", not can_say("lmstudio", "cpu-spill"))


@test
def test_the_window_per_slot_and_the_time_of_a_line(ctx: Ctx):
    from halo_harness.ollama_steward.server_context_hf import Rules
    from halo_harness.ollama_steward.server_rules_hf import line_time
    from tests.helpers.servers_seed import LLAMA_LOG
    r = Rules("llama-server")
    evs = [e for x in LLAMA_LOG.splitlines() for e in r.feed(x, at=1000.0)]
    load = next(e for e in evs if e["kind"] == "load-result")
    ctx.check(f"the slot window, the slots, the layers, got {load['data']}", load["data"]["window"] == 8192
              and load["data"]["n_ctx"] == 16384 and load["data"]["n_slots"] == 2 and load["data"]["offloaded"] == 30)
    trim = next(e for e in evs if e["kind"] == "prompt-trimmed")
    ctx.check("a cut carries the window and the model", trim["data"]["window"] == 8192 and trim["model"] == "qwen3-8b")
    ctx.check("LM Studio's and Python's timestamps read", line_time("[2026-10-30 14:03:02][ERROR] x") and
              line_time('127.0.0.1 - - [30/Oct/2026 14:11:05] "POST / HTTP/1.1" 500 -'))
    ctx.check("llama-server prints none", line_time("slot update_slots: id 0") is None)


def _findings(h):
    from halo_harness.ollama_steward.rules import findings
    return findings(h.state, cards={}, catalogs={})


@test
def test_findings_for_a_server_keyed_by_its_name(ctx: Ctx):
    from halo_harness.ollama_steward.server_log_hf import scan
    with Home(lms=False, mlx=False) as h:
        scan(h.state, h.server("llama-8080"), from_start=True, root=h.root)
        comp = {"tools_schema": 3000, "total": 7000}
        h.calls(*[hf_line(prompt_eval_count=7800, tools_count=30, composition=comp) for _ in range(5)],
                hf_line(done_reason="length", prompt_eval_count=7000, eval_count=512))
        found = _findings(h)
        by = {f["rule"]: f for f in found if f.get("server") == "llama-8080"}
        ctx.check(f"the server's findings, got {sorted(by)}", {"window-small", "reply-cut", "cpu-spill", "tools-heavy"} <= set(by))
        w = by["window-small"]
        ctx.check(f"keyed by the server, got {w['key']}", w["key"] == "llama-8080|qwen3-8b" and w["runtime"] == "llama-server")
        p = w.get("proposal") or {}
        ctx.check(f"Halo's window to the server's 8,192 per slot, got {p}", p.get("field") == "num_ctx" and p.get("to") == 8192)
        st = (w.get("stated") or [{}])[0]
        ctx.check(f"--ctx-size said, never applied, with its revert, got {st}", st.get("set") == "--ctx-size 32768"
                  and st.get("revert") == "--ctx-size 16384" and st.get("applied") is False and "halo local stop" in st.get("how", ""))
        ctx.check("the server hint names it", "--ctx-size" in (w.get("server_hint") or {}).get("line", ""))
        r = by["reply-cut"]
        ctx.check(f"the server's own n_predict said, got {r['finding']}", "--n-predict 512" in r["finding"]
                  and (r.get("stated") or [{}])[0].get("set") == "--n-predict -1")
        ctx.check("a spill: --n-gpu-layers", (by["cpu-spill"].get("stated") or [{}])[0].get("set") == "--n-gpu-layers 37")
        t = by["tools-heavy"]
        ctx.check(f"a tool budget, got {t.get('proposal')}", (t.get("proposal") or {}).get("field") == "tools_max"
                  and t["proposal"]["to"] == 12)


@test
def test_lm_studio_and_mlx_findings_say_their_own_lines(ctx: Ctx):
    from halo_harness.ollama_steward.server_log_hf import scan
    with Home(llama=False) as h:
        scan(h.state, h.server("studio"), from_start=True, root=h.root)
        scan(h.state, h.server("mac-mlx"), from_start=True, root=h.root)
        h.calls(*[hf_line(url="http://127.0.0.1:1234/v1", model="qwen2.5-7b-instruct", prompt_eval_count=3900)
                  for _ in range(3)])
        found = [f for f in _findings(h) if f.get("server") == "studio"]
        w = next((f for f in found if f["rule"] == "window-small"), {})
        st = (w.get("stated") or [{}])[0]
        ctx.check(f"LM Studio's Context Length, got {st}", "Context Length: 16384" in st.get("set", "") and st.get("applied") is False)
        ctx.check("cpu-spill is not asked of LM Studio", "cpu-spill" in w.get("not_asked", []))


@test
def test_a_crash_that_repeats_in_a_servers_log(ctx: Ctx):
    from halo_harness.ollama_steward.fingerprints import read
    from halo_harness.ollama_steward.server_log_hf import scan
    with Home(lms=False, mlx=False, pid=None) as h:
        s = h.server("llama-8080")
        scan(h.state, s, from_start=True, root=h.root)
        h.append(h.llama_log, LLAMA_CRASH)
        scan(h.state, s, root=h.root)
        fps = read(h.state, host="llama-8080")
        ctx.check(f"a fingerprint with the runtime and Halo's launch, got {fps[:1]}", fps and fps[0].get("runtime") ==
                  "llama-server" and "--alias qwen3-8b" in (fps[0].get("load_cmd") or ""))
        import time
        h.append(h.llama_log, LLAMA_CRASH)
        scan(h.state, s, root=h.root, at=time.time() + 600)
        crash = next((f for f in _findings(h) if f["rule"] == "crash-repeats"), {})
        ctx.check(f"crash-repeats for the server, got {crash.get('finding')}", crash.get("server") == "llama-8080"
                  and crash.get("runtime") == "llama-server")
        ctx.check(f"its fixes are the runtime's lines, got {crash.get('fixes')}",
                  any("--cache-type-k" in f["line"] for f in crash.get("fixes") or []))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
