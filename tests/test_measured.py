"""tests.test_measured -- Halo 3.3.6.0 R4 deliverable 1, the measured card (providers/measured.py; the server log's
`timing` and `spec-decode` lines, ollama_steward/server_rules.py + server_context.py), on fixture ledger lines,
server events and a battery profile (no server, no model call):

1. the medians over the newest answered calls, never a `warming` one, each fact with its source, date and n;
2. the fallbacks: the log's print_timing when the ledger has no rate, the battery's speed when neither has;
   load from the log's `load-result`, the window verified by the fit evidence vs assumed, KV per token, modality,
   speculative decoding from the log, tool-call accuracy from the multi-tool probe, the quirks (ignores system
   prompt, answers in thinking, loops, no prompt cache);
3. the print_timing pair and the draft lines become one `timing` event and a `spec-decode` event;
4. kept under the capability cache's record (cache[digest]["measured"][host]); `lines()`, the speed chip, the card's
   Measured block, `halo models show` and `halo models measured`.
Run: python -m tests.test_measured
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.logs_rig import LogsHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BOX = {"name": "box", "url": "http://127.0.0.1:9"}


def profile(model: str = "coder:30b", **kw) -> dict:
    from halo_harness.providers.battery_probes import PROBE_SET
    from halo_harness.providers.battery_profile import finish
    p = {"model": model, "host": "box", "digest": f"sha256:{model.replace(':', '-')}", "ollama_version": "0.40.13",
         "probe_set": PROBE_SET, "probed_at": time.time() - 3600, "tools": "yes", "system_role": "weak",
         "instruction": "strict", "output": "json", "identifiers": "trusted", "reasoning": "thinking",
         "window": {"trained": 262144, "usable": 65536, "used": 32768, "verified": True}, "kv_per_token": 52224,
         "size_gb": 18.6, "speed": {"tok_s": 187.5, "ttft_ms": 121, "cold_load_s": 6.5, "at_window": 32768},
         "resident": {"co_resides_with": [], "pivot_only": False}, "evidence": {}, "capabilities": ["completion", "tools", "vision"],
         "tool_call_accuracy": 0.75, "tool_call_why": "find_user right; get_orders right, its user_id wrong", **kw}
    return finish(p)


def _seed(state, p: dict) -> None:
    from halo_harness.providers.ollama_capability import save_profile
    save_profile(state, p)


def _fresh():
    from halo_harness.providers import fit_evidence, measured
    measured._ROWS.clear()
    fit_evidence._CACHE.clear()


@test
def test_medians_never_a_warming_call_each_with_its_source(ctx: Ctx):
    from halo_harness.providers.measured import lines, measured_for, speed_chip
    now = time.time()
    with LogsHome(hosts=[BOX]) as h:
        _seed(h.state, profile())
        for i, (tok, pe, cache) in enumerate([(200.0, 300.0, 80), (210.0, 320.0, 90), (190.0, 280.0, 92)]):
            h.call(BOX, "coder:30b", now - 300 + i, eval_tok_s=tok, eval_count=120, prompt_eval_ms=pe, load_ms=20.0,
                   cache_reused_pct=cache, kind="turn")
        h.call(BOX, "coder:30b", now - 200, eval_tok_s=5.7, eval_count=120, prompt_eval_ms=9000.0, load_ms=9500.0,
               warming=True, kind="turn")
        h.call(BOX, "coder:30b", now - 100, eval_tok_s=999.0, eval_count=2, prompt_eval_ms=310.0, load_ms=20.0)  # tiny
        from halo_harness.ollama_steward.ledger import blank_line, now_iso, record_call
        record_call(h.state, blank_line(host=BOX, model="coder:30b", at=now_iso(now - 90), status=500, eval_tok_s=1.0,
                                        eval_count=200))
        h.call(BOX, "other:7b", now - 80, eval_tok_s=50.0, eval_count=100)
        _fresh()
        m = measured_for("box", "coder:30b", state_dir=h.state)
        ctx.check(f"tok/s: the median of the three answered, the warming and the tiny reply left out, got {m['tok_s']}",
                  m["tok_s"]["value"] == 200.0 and m["tok_s"]["n"] == 3 and m["tok_s"]["source"] == "the ledger")
        ctx.check(f"first token: prompt eval + load over the answered (warm) calls, got {m['ttft_ms']}",
                  m["ttft_ms"]["value"] == 325 and m["ttft_ms"]["n"] == 4)
        ctx.check(f"cache reuse median, got {m['cache_reused_pct']}", m["cache_reused_pct"]["value"] == 90)
        ctx.check(f"n_calls counts the answered, never the warming, got {m['n_calls']}", m["n_calls"] == 4)
        ctx.check(f"each fact has a date, got {m['tok_s']['at']}", m["tok_s"]["at"] == time.strftime("%Y-%m-%d"))
        ctx.check(f"the load from the warming call when the log has none, got {m['load_s']}",
                  m["load_s"]["value"] == 9.5 and "first call after a load" in m["load_s"]["source"])
        ctx.check(f"tool-call accuracy from the multi-tool probe, got {m['tool_call_accuracy']}",
                  m["tool_call_accuracy"]["value"] == 0.75 and "multi-tool" in m["tool_call_accuracy"]["source"])
        ctx.check(f"KV per token and modality from the battery, got {m['kv_per_token']} {m['modality']}",
                  m["kv_per_token"]["value"] == 52224 and m["modality"]["value"] == "text + images")
        q = [x["value"] for x in m["quirks"]]
        ctx.check(f"the battery's quirks, got {q}", q == ["ignores system prompt", "answers in thinking"])
        ls = lines(m)
        ctx.check(f"each line 'value (source, date, n)', got {ls[:2]}",
                  ls[0].startswith("200 tok/s (the ledger, ") and ls[0].endswith(", 3 calls)"))
        ctx.check(f"the speed chip, got {speed_chip(m)!r}", speed_chip(m) == "200 tok/s")
        cache = __import__("json").loads((h.state / "ollama-capabilities.json").read_text(encoding="utf-8"))
        kept = cache["sha256:coder-30b"]["measured"]["box"]["facts"]
        ctx.check("kept under cache[digest]['measured'][host]", kept["tok_s"]["value"] == 200.0)


@test
def test_the_fallbacks_and_the_log_sources(ctx: Ctx):
    from halo_harness.ollama_steward.server_rules import event
    from halo_harness.providers.measured import measured_for
    now = time.time()
    with LogsHome(hosts=[BOX]) as h:
        _seed(h.state, profile("hybrid:9b", system_role="honoured", reasoning="none", capabilities=["completion"]))
        h.events(event("timing", "a reply", "eval time", at=now - 50, model="hybrid:9b", eval_ms=1000.0, eval_n=150,
                       eval_tok_s=150.0, prompt_ms=420.0, prompt_n=900, prompt_tok_s=2142.0),
                 event("timing", "a reply", "eval time", at=now - 40, model="hybrid:9b", eval_ms=1000.0, eval_n=170,
                       eval_tok_s=170.0, prompt_ms=380.0, prompt_n=900, prompt_tok_s=2300.0),
                 event("load-result", "loaded", "started", at=now - 60, model="hybrid:9b", layers=[33, 33], splits=2,
                       window=32768, load_s=12.0),
                 event("spec-decode", "draft", "draft acceptance rate", at=now - 30, model="hybrid:9b", on=True,
                       accept_rate=0.6, accepted=12, generated=20),
                 event("no-prompt-cache", "re-reads", "forcing full prompt re-processing", at=now - 20, model="hybrid:9b"))
        h.call(BOX, "hybrid:9b", now - 10, eval_count=None, eval_tok_s=None, prompt_eval_ms=None, loop=True)
        _fresh()
        m = measured_for("box", "hybrid:9b", state_dir=h.state)
        ctx.check(f"tok/s from the log's print_timing when the ledger has no rate, got {m['tok_s']}",
                  m["tok_s"]["value"] == 160.0 and m["tok_s"]["source"] == "the server log" and m["tok_s"]["n"] == 2)
        ctx.check(f"first token from print_timing's prompt line, got {m['ttft_ms']}", m["ttft_ms"]["value"] == 400)
        ctx.check(f"load from the log's load-result, got {m['load_s']}", m["load_s"]["value"] == 12.0
                  and m["load_s"]["source"] == "the server log")
        ctx.check(f"the window verified by the fit evidence (the log), assumed from the battery, got {m['window']}",
                  m["window"]["value"] == {"verified": 32768, "assumed": 32768} and "fit evidence" in m["window"]["source"])
        ctx.check(f"speculative decoding on, from the log, got {m['spec_decode']}",
                  m["spec_decode"]["value"] == {"on": True, "accept_rate": 0.6})
        q = [x["value"] for x in m["quirks"]]
        ctx.check(f"loops (the ledger) and no prompt cache (the log), got {q}", q == ["loops", "no prompt cache"])
        _seed(h.state, profile("plain:3b"))
        _fresh()
        p = measured_for("box", "plain:3b", state_dir=h.state)
        ctx.check(f"nothing in the ledger or the log: the battery's warm speed, got {p['tok_s']}",
                  p["tok_s"]["value"] == 187.5 and p["tok_s"]["source"] == "the battery")
        none = measured_for("box", "unknown:1b", state_dir=h.state)
        ctx.check(f"a model nothing measured: every value None, got {none['tok_s']}", none["tok_s"]["value"] is None
                  and none["n_calls"] == 0 and none["quirks"] == [])


@test
def test_print_timing_and_draft_lines_become_events(ctx: Ctx):
    from halo_harness.ollama_steward.server_context import Rules
    lines = ['time=2026-10-30T10:00:00.000Z level=INFO msg="template selection" model=coder:30b',
             "slot print_timing: id  0 | task 7 | ",
             "prompt eval time =     456.78 ms /  1234 tokens (    0.37 ms per token,  2701.89 tokens per second)",
             "       eval time =    2345.67 ms /   456 tokens (    5.14 ms per token,   194.40 tokens per second)",
             "      total time =    2802.45 ms /  1690 tokens",
             "slot      release: id  0 | task 7 | draft acceptance rate = 0.57143 (   12 accepted /    21 generated)",
             "srv    load_model: loading draft model 'blobs/sha256-d'"]
    r = Rules()
    evs = [e for x in lines for e in r.feed(x)] + r.flush()
    kinds = [e["kind"] for e in evs]
    ctx.check(f"one timing event per request and two spec-decode events, got {kinds}",
              kinds == ["timing", "spec-decode", "spec-decode"])
    t = evs[0]["data"]
    ctx.check(f"the reply's and the prompt's numbers on the one event, got {t}", t["eval_tok_s"] == 194.4
              and t["eval_n"] == 456 and t["prompt_ms"] == 456.78 and t["prompt_n"] == 1234 and evs[0]["model"] == "coder:30b")
    ctx.check(f"the acceptance rate, got {evs[1]['data']}", evs[1]["data"]["accept_rate"] == 0.57143
              and evs[1]["severity"] == "info")


@test
def test_the_card_the_show_and_the_cli(ctx: Ctx):
    import json
    from halo_harness.catalog_cli import cmd_models
    from halo_harness.providers.model_card_blocks import block_lines
    from halo_harness.providers.model_card_measured import with_measured
    now = time.time()
    with LogsHome(hosts=[BOX]) as h:
        _seed(h.state, profile())
        for i in range(3):
            h.call(BOX, "coder:30b", now - 100 + i, eval_tok_s=250.0 + i, eval_count=100, prompt_eval_ms=200.0, load_ms=1.0)
        _fresh()
        card = with_measured({"kind": "ollama", "host": "box", "name": "coder:30b", "blocks": {}}, h.state)
        ctx.check(f"the card's Measured block, got {card['blocks'].get('measured')}",
                  card["blocks"]["measured"][0]["text"].startswith("251 tok/s (the ledger"))
        out = "\n".join(block_lines(card["blocks"]))
        ctx.check(f"halo models show prints it under 'measured:', got {out[:120]!r}", "  measured:\n    251 tok/s" in out)
        code, text = h.cli(cmd_models, "measured", "ol:coder:30b@box")
        ctx.check(f"halo models measured: exit 0, the lines, got {code} {text!r}", code == 0
                  and "coder:30b on box: measured over its last 3 answered calls" in text and "251 tok/s" in text
                  and "tool-call accuracy 75%" in text)
        code, text = h.cli(cmd_models, "measured", "coder:30b", "--host", "box", "--json")
        ctx.check("--json", code == 0 and json.loads(text)["tok_s"]["value"] == 251.0)
        code, text = h.cli(cmd_models, "measured", "coder:30b", "--host", "nope")
        ctx.check(f"an unknown host says so, got {code} {text!r}", code == 1 and "no Ollama host" in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
