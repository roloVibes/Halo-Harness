"""tests.test_steward_fingerprints -- Halo 3.3.6.0 R2 "crash fingerprints" (ollama_steward/fingerprints.py; G11's
first half) on fixture events: the server log's own lines through server_rules.classify, written by
server_events.record_events the way the steward's job writes them; the host card through the Ollama panel's
READERS seam (tests/helpers/search_rig.py). No request, no model call:

1. each crash line's signature: the CUDA illegal memory access, a runner that died (exit 0xc0000409), a failed
   load, out of memory; not a crash: a client that closed the connection, an error with no CUDA line, a load;
2. one crash = one fingerprint: the CUDA line, `llama runner terminated` and the 500 within two minutes join; the
   model from the newest load before it, its window and the spill from that load, the KV type and flash attention
   from the card; a second crash with the same settings counts 2;
3. `halo ollama crashes` lists them (`--host`, `--json`); the Models rows carry the mark;
4. the ledger push: a member's fingerprints reach the hub under `<member>:<host>`.
Run: python -m tests.test_steward_fingerprints
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.search_rig import GIB, SearchHome, box_card  # noqa: E402

test, TESTS = new_registry()
T = "2026-10-29T21:14:0{s}.120+01:00"
IMA = "CUDA error: an illegal memory access was encountered"
DIED = 'time={t} level=ERROR source=server.go:1520 msg="llama runner terminated" error="exit status 0xc0000409"'
FAILED = 'time={t} level=INFO source=sched.go:470 msg="Load failed" model=qwen3.8:27b error="unable to allocate CUDA0 buffer"'
ABORT = 'time={t} level=INFO source=sched.go:470 msg="Load failed" model=x error="context canceled"'
OOM = 'time={t} level=ERROR source=runner.go:90 msg="cudaMalloc failed: out of memory"'
OTHER = 'time={t} level=ERROR source=routes.go:12 msg="template not found"'


def _ev(line: str, s: int = 3):
    from halo_harness.ollama_steward.server_rules import classify
    return classify(line.format(t=T.format(s=s)) if "{t}" in line else line)


def _load(model="qwen3.8:27b", ctx=65536, size=20 * GIB, vram=17 * GIB):
    return {"kind": "loaded", "severity": "info", "say": f"{model} loaded", "evidence": "/api/ps", "at": None, "model": model,
            "data": {"size": size, "size_vram": vram, "context_length": ctx}}


@test
def test_each_crash_line_gets_its_signature(ctx: Ctx):
    from halo_harness.ollama_steward.fingerprints import signature_of
    got = {k: signature_of(_ev(v)) for k, v in (("ima", IMA), ("died", DIED), ("failed", FAILED), ("abort", ABORT),
                                                  ("oom", OOM), ("other", OTHER))}
    ctx.check(f"the signatures, got {got}", got == {"ima": "CUDA IMA", "died": "runner died (0xc0000409)", "failed": "load failed",
                                                    "abort": None, "oom": "GPU out of memory", "other": None})
    ctx.check("an IMA line is said as a CUDA error, not a full card", "illegal memory access" in _ev(IMA)["say"])
    ctx.check("a load is no crash", signature_of(_load()) is None)


@test
def test_one_crash_is_one_fingerprint_with_its_settings(ctx: Ctx):
    with SearchHome(card=box_card(kv="q8_0", fa=True)) as h:
        from halo_harness.providers.ollama import resolve_ollama_host
        from halo_harness.studio.ollama_hosts_view import card_of
        card_of(resolve_ollama_host("box"))  # the panel has the card: its KV type and flash attention
        h.events(_load())
        h.events(_ev(IMA), {**_ev(DIED, 4), "at": None}, {"kind": "http-500", "severity": "error", "say": "", "evidence": "| 500 |", "at": None,
                                          "model": None, "data": {}})
        from halo_harness.ollama_steward.fingerprints import read
        one = read(h.state)
        import time
        later = time.time() + 3600
        h.events({**_load(), "at": later - 10}, {**_ev(IMA), "at": later})
        two = read(h.state, host="box")
        lines = (h.state / "ollama" / "fingerprints.jsonl").read_text(encoding="utf-8").splitlines()
    fp = one[0] if one else {}
    ctx.check(f"the three lines of one crash are one fingerprint, got {len(one)}", len(one) == 1)
    ctx.check(f"the most specific signature wins, got {fp.get('signature')}", fp.get("signature") == "CUDA IMA")
    ctx.check(f"the model from the newest load before it, got {fp.get('model')} ({fp.get('model_from')})",
              fp.get("model") == "qwen3.8:27b" and fp.get("model_from") == "the newest load before it")
    ctx.check(f"window, spill, KV, flash attention, family and quant, got {fp}",
              fp.get("window_used") == 65536 and fp.get("spill") is True and fp.get("kv_cache_type") == "q8_0"
              and fp.get("flash_attention") is True and fp.get("family") and len(fp.get("evidence") or []) == 2)
    ctx.check(f"the line, got {fp.get('line')!r}", (fp.get("line") or "").startswith("crashed here on ") and
              "CUDA error (an illegal memory access) after a spill at 65,536 with q8_0 KV, flash attention on" in fp["line"])
    ctx.check(f"a second crash with the same settings counts 2, got {[x.get('count') for x in two]}",
              len(two) == 2 and two[0]["count"] == 2 and "(2 times)" in two[0]["line"] and len(lines) == 2)


@test
def test_halo_ollama_crashes_and_the_models_mark(ctx: Ctx):
    from halo_harness.ollama_cli import cmd_ollama
    with SearchHome(card=box_card()) as h:
        h.events(_load("qwen3.5:9b", 32768, 8 * GIB, 8 * GIB))
        h.events({**_ev(FAILED), "at": None, "model": "qwen3.5:9b"})
        runs = {}
        for key, argv in (("plain", ["crashes"]), ("host", ["crashes", "--host", "elsewhere"]), ("json", ["crashes", "--json"])):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                runs[key] = (cmd_ollama(argv), out.getvalue())
        from halo_harness.studio import local_models_view as M
        rows = M.models(h.state)["hosts"][0]["models"]
    rc, text = runs["plain"]
    ctx.check(f"the list: host, model, the line, family and where the model came from, got {text!r}",
              rc == 0 and text.startswith("box qwen3.5:9b: crashed here on ") and "the load failed" in text and "model from the event" in text)
    ctx.check(f"--host elsewhere: none, said plainly, got {runs['host'][1]!r}", "no crash fingerprints for elsewhere" in runs["host"][1])
    ctx.check(f"--json: one fingerprint a line, got {runs['json'][1][:120]!r}", json.loads(runs["json"][1].splitlines()[0])["signature"] == "load failed")
    ctx.check(f"the Models rows show nothing for a model not in the catalog, got {rows}", rows == [] or all("crashed" in r for r in rows))
    with SearchHome(card=box_card(), catalog={"models": [{"model": "qwen3.5:9b", "name": "qwen3.5:9b", "size": 8 * GIB,
                                                          "details": {"family": "qwen35"}, "capabilities": ["completion"]}]}) as h:
        h.events(_load("qwen3.5:9b", 32768, 8 * GIB, 8 * GIB))
        h.events({**_ev(FAILED), "at": None, "model": "qwen3.5:9b"})
        from halo_harness.studio import local_models_view as M
        row = M.models(h.state)["hosts"][0]["models"][0]
    ctx.check(f"the Models row carries the mark, got {row.get('crashed')}", (row.get("crashed") or {}).get("signature") == "load failed")


@test
def test_the_fingerprint_travels_with_the_ledger_push(ctx: Ctx):
    from halo_harness.fleet.control_probes import read_crashes, take_crashes
    with SearchHome(card=box_card()) as member:
        member.events(_load())
        member.events(_ev(IMA))
        sent = read_crashes(member.state)
    with SearchHome(card=box_card()) as hub:
        n = take_crashes(hub.state, "mac@studio", sent)
        again = take_crashes(hub.state, "mac@studio", sent)
        from halo_harness.ollama_steward.fingerprints import read
        got = read(hub.state)
    ctx.check(f"the member sends its fingerprint, got {sent}", len(sent) == 1 and sent[0]["signature"] == "CUDA IMA")
    ctx.check(f"the hub keeps it once, under <member>:<host> with from, got {n} {again} {got}",
              n == 1 and again == 0 and got[0]["host"] == "mac@studio:box" and got[0]["from"] == "mac@studio")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
