"""tests.test_steward_crash_forensics -- Halo 3.3.6.0 R3 deliverable 4, "crash forensics" (ollama_steward/
fingerprint_facts.py, rules_crash.py; plans/local-model-fit-brief.md D3 item 15 and G11's second half), on the
2026-10-29 shape as a fixture log: flash attention + a q8_0 KV cache + a spill -> CUDA IMA -> exit 0xc0000409.

1. the load block: `load-result` with 59/66 layers, splits = 14, the KV buffers on the GPU and the CPU, the window,
   the KV type and flash attention in force then; the crash events carry that load;
2. the fingerprint: the load command, layers, splits, the KV placement, the settings in force at the crash (not the
   card's now), the Ollama version, the request's num_ctx from the nearest ledger line; one steward note per new one;
3. `halo ollama crashes --why` prints each fact with where it came from;
4. a fingerprint that repeats proposes the fix: a smaller window (the profile's num_ctx, through the steward's apply
   modes), f16 KV, flash attention off, a fitted twin, and on a Windows host with an update staged the restart line.
Run: python -m tests.test_steward_crash_forensics
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.logs_rig import LogsHome, crash_log  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BOX = {"name": "box", "url": "http://127.0.0.1:9"}
CARD = {"server": {"version": "0.40.13", "kv_cache_type": "f16", "flash_attention": "auto or off"}}


def _scan(h, text: str) -> list:
    from halo_harness.ollama_steward.server_context import Rules
    from halo_harness.ollama_steward.server_events import record_events
    rules = Rules()
    evs = [e for line in text.splitlines() for e in rules.feed(line)] + rules.flush()
    return record_events(h.state, evs, host="box")


def _card_seam():
    from halo_harness.ollama_steward import fingerprints
    real = fingerprints._seams
    fingerprints._seams = lambda name: (CARD, None)  # the card NOW: f16, FA off, 0.40.13 (reconfigured since)
    return lambda: setattr(fingerprints, "_seams", real)


@test
def test_the_load_block_and_the_crash_events(ctx: Ctx):
    from halo_harness.ollama_steward.server_context import Rules
    rules = Rules()
    evs = [e for line in crash_log().splitlines() for e in rules.feed(line)] + rules.flush()
    load = next((e for e in evs if e["kind"] == "load-result"), {})
    crash = next((e for e in evs if e["kind"] == "gpu-memory"), {})
    d = load.get("data") or {}
    ctx.check(f"load-result: layers, splits, KV placement, window, KV type, FA, got {d}", d.get("layers") == [59, 66]
              and d.get("splits") == 14 and d.get("kv_gpu_mib") == 1904.0 and d.get("kv_cpu_mib") == 272.0
              and d.get("window") == 65536 and d.get("kv_cache_type") == "q8_0" and d.get("flash_attention") == "on"
              and d.get("version") == "0.40.6" and d.get("spill") is True)
    ctx.check(f"the model from the template line after the load, got {load.get('model')}", load.get("model") == "qwen3.8:27b")
    ctx.check(f"it says the spill, got {load.get('say')!r}", "59/66 layers on the GPU" in str(load.get("say"))
              and "on the CPU" in str(load.get("say")))
    ctx.check(f"the crash event carries the load in force, got {(crash.get('data') or {}).get('load', {}).get('splits')}",
              ((crash.get("data") or {}).get("load") or {}).get("cmd", "").startswith("llama-server.exe --model"))


@test
def test_the_fingerprint_carries_the_load_it_died_in(ctx: Ctx):
    from halo_harness.ollama_steward.fingerprints import read
    from halo_harness.ollama_steward.notes import read as read_notes
    undo = _card_seam()
    try:
        with LogsHome(hosts=[BOX]) as h:
            h.call(BOX, "qwen3.8:27b", time.time() - 100, num_ctx_sent=65536)
            _scan(h, crash_log())
            fps = read(h.state, host="box")
            notes = [n for n in read_notes(h.state) if n.get("stage") == "finding"]
    finally:
        undo()
    fp = fps[0] if fps else {}
    ctx.check(f"one crash, one fingerprint, the most specific signature, got {len(fps)} {fp.get('signature')}",
              len(fps) == 1 and fp.get("signature") == "CUDA IMA")
    ctx.check(f"the load: command, layers, splits, KV placement, got {fp}", str(fp.get("load_cmd")).startswith("llama-server.exe")
              and fp.get("layers") == [59, 66] and fp.get("splits") == 14 and fp.get("kv_cpu_mib") == 272.0
              and fp.get("spill") is True)
    ctx.check(f"the settings in force at the crash, not the card's now, got {fp.get('kv_cache_type')} {fp.get('flash_attention')} "
              f"{fp.get('ollama_version')}", fp.get("kv_cache_type") == "q8_0" and fp.get("flash_attention") == "on"
              and fp.get("ollama_version") == "0.40.6" and fp.get("facts_from") == "the log's load block")
    ctx.check(f"the request's num_ctx from the nearest ledger line, got {fp.get('num_ctx_requested')}",
              fp.get("num_ctx_requested") == 65536 and fp.get("window_used") == 65536)
    ctx.check(f"one plain-language note per new fingerprint, got {[n.get('say') for n in notes]}", len(notes) == 1
              and "qwen3.8:27b crashed on box" in notes[0]["say"] and "halo ollama crashes --why" in notes[0]["say"])


@test
def test_crashes_why(ctx: Ctx):
    from halo_harness.ollama_steward.cli_logs import cmd_ollama_crashes
    undo = _card_seam()
    try:
        with LogsHome(hosts=[BOX]) as h:
            _scan(h, crash_log())
            code, out = h.cli(cmd_ollama_crashes, "--why")
    finally:
        undo()
    ctx.check(f"--why: each fact with its source, got {out!r}", code == 0 and "signature: CUDA IMA" in out
              and "the load: 59/66 layers on the GPU, splits = 14" in out and "in force then: KV q8_0, flash attention on, "
              "Ollama 0.40.6 (from the log's load block)" in out and "the load command: llama-server.exe" in out)


@test
def test_a_repeated_crash_proposes_the_fix(ctx: Ctx):
    from halo_harness.ollama_steward import rules_crash
    from halo_harness.ollama_steward.rules import findings
    from halo_harness.ollama_steward.cli_logs import cmd_ollama_crashes
    undo = _card_seam()
    rules_crash.SEAMS["staged"] = lambda host: "0.40.13"  # an update staged on that Windows machine
    try:
        with LogsHome(hosts=[BOX]) as h:
            _scan(h, crash_log())
            _scan(h, crash_log(at=600.0))  # the same settings, ten minutes on: count 2
            found = [f for f in findings(h.state) if f["rule"] == "crash-repeats"]
            code, out = h.cli(cmd_ollama_crashes, "--why")
    finally:
        undo()
        rules_crash.SEAMS.clear()
    f = found[0] if found else {}
    lines = [x["line"] for x in f.get("fixes") or []]
    ctx.check(f"one error finding for the host and model, got {[(x['key'], x['severity']) for x in found]}",
              len(found) == 1 and f["key"] == "box|qwen3.8:27b" and f["severity"] == "error")
    ctx.check(f"Halo's side: a smaller window through the apply modes, got {f.get('proposal')}",
              (f.get("proposal") or {}).get("field") == "num_ctx" and (f.get("proposal") or {}).get("to") == 32768)
    ctx.check(f"the host's side said, never done: f16 KV, FA off, the twin, got {lines}",
              any("OLLAMA_KV_CACHE_TYPE=f16" in x for x in lines) and any("OLLAMA_FLASH_ATTENTION=0" in x for x in lines)
              and any("halo ollama tune qwen3.8:27b" in x for x in lines))
    ctx.check(f"the staged update on a Windows host, got {lines}",
              "0.40.13 is staged on box; the crash fix is in it -- restart Ollama there" in lines)
    ctx.check(f"crashes --why lists the fixes when it repeats, got {out[-400:]!r}", code == 0 and "fix (Halo): a 32,768 window"
              in out and "fix (on the host): 0.40.13 is staged on box" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
