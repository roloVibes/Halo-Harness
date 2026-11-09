"""tests.test_server_rules_body -- a request's text in a server log is no server event (Halo 3.3.14.0 R2, REVIEW #23
LOCAL-3; ollama_steward/body_lines.py, server_rules.py, server_rules_hf.py, engines/steward.py, server_log_hf.scan):

1. a body-shaped line (Ollama's `prompt="..."`, a `"content":` member, a pretty-printed body) that says "CUDA out of
   memory" / "exited with code 1" / "Segmentation fault" classifies to None in every classifier; the same text as the
   server's own line still raises its event;
2. a scan of a log holding a prompt that says "CUDA out of memory" writes no event and counts the skipped line in the
   server's read state (`body_lines_skipped`); the server's own OOM line in the same log is written.
Run: python -m tests.test_server_rules_body"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.config_seed import ConfigHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BODY = ['      "content": "the build failed: CUDA error: out of memory, then Process exited with code 1"',
        'time=2026-11-09T10:00:00.000Z level=DEBUG source=routes.go msg="chat request" prompt="Segmentation fault '
        'CUDA error out of memory"',
        '{"messages": [{"role": "user", "content": "cudaMalloc failed: out of memory"}]}',
        '    "role": "user", "content": "GGML_ASSERT failed"']


@test
def test_body_lines_classify_to_none(ctx: Ctx):
    from halo_harness.engines.steward import classify as engine
    from halo_harness.ollama_steward.server_rules import classify as ollama
    from halo_harness.ollama_steward.server_rules_hf import classify as hf
    for line in BODY:
        got = [ollama(line), hf(line, runtime="llama-server"), hf(line, runtime="lmstudio"),
               engine(line, runtime="tensorfold"), engine(line, runtime="strata")]
        ctx.check(f"no event from {line[:50]!r}, got {[g and g['kind'] for g in got]}", got == [None] * 5)
    real = ollama("ggml_backend_cuda_buffer_type_alloc_buffer: allocating 4096.00 MiB on device 0: cudaMalloc failed: "
                  "out of memory")
    ctx.check(f"Ollama's own OOM line is an event, got {real and real['kind']}", real and real["kind"] == "gpu-memory")
    seg = hf("Segmentation fault (core dumped)", runtime="llama-server")
    ctx.check(f"llama-server's own death line is an event, got {seg and seg['kind']}", seg and seg["data"].get("death"))
    tf = engine("2026-11-09T10:00:00Z ERROR CUDA_ERROR_OUT_OF_MEMORY while allocating the cache", runtime="tensorfold")
    ctx.check(f"an engine's own OOM line is an event, got {tf and tf['kind']}", tf is not None)


@test
def test_a_scan_skips_the_prompt_and_counts_it(ctx: Ctx):
    from halo_harness.ollama_steward.server_events import read_events
    from halo_harness.ollama_steward.server_log_hf import load_state, scan
    from halo_harness.ollama_steward.servers_hf import Server
    with ConfigHome() as h:
        state = h.home / ".halo"
        log = h.home / "llama-6000.log"
        log.write_text("\n".join(BODY[:1] + BODY[2:]) + "\n", encoding="utf-8")
        srv = Server(name="llama-6000", url="http://127.0.0.1:6000/v1", runtime="llama-server", log=str(log))
        written, why = scan(state, srv, from_start=True)
        ctx.check(f"no event from the prompt, got {written} {why}", not written)
        st = load_state(state).get("llama-6000") or {}
        ctx.check(f"the read state counts the skipped lines, got {st}", st.get("body_lines_skipped") == 3)
        with open(log, "a", encoding="utf-8") as f:
            f.write("Segmentation fault (core dumped)\n")
        written, _why = scan(state, srv)
        kinds = [e.get("kind") for e in read_events(state)]
        ctx.check(f"the server's own line is written, got {kinds}", "other-error" in kinds)
        ctx.check("the count holds", (load_state(state).get("llama-6000") or {}).get("body_lines_skipped") == 3)
        ctx.check("the events file is JSON lines", all(json.loads(x) for x in (state / "ollama" / "events.jsonl")
                                                       .read_text(encoding="utf-8").splitlines() if x.strip()))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
