"""tests.test_prompt_cache -- Halo 3.3.5.0 R4: prompt-cache awareness
(ollama_steward/ledger_prompt.py, server_rules `no-prompt-cache`,
providers/model_card_quirks.py). A fresh home; the loop rig
(tests/helpers/prompt_budget_rig.py) for the ledger's fields; never a real
server or a model call:

1. the ledger line's `prefix_tokens` (the system message, the memory in it,
   the tools) on every turn;
2. `cache_reused_pct` from a scripted `prompt_eval_count`: Ollama read 80 % of
   the prompt -> about 20 %; a full read -> 0; a trimmed call -> 0; no count
   -> None; the Ollama panel's "last turn" line says "cache reused N %";
3. the fixture log line "forcing full prompt re-processing due to lack of
   cache data" -> a `no-prompt-cache` event; recorded for a model, its card
   gains the quirk "re-reads the whole prompt every turn" (a `how` line), the
   Local tab's model row carries it, and the steward's knowledge explains it.
Run: python -m tests.test_prompt_cache
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="pb_cache-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.model_switch_rig import ledger_lines  # noqa: E402
from tests.helpers.prompt_budget_rig import Rig, answer  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
LOG_LINE = ('time=2026-10-29T21:14:03.120-04:00 level=WARN source=server.go:1288 msg="forcing full prompt re-processing '
            'due to lack of cache data (likely due to SWA or hybrid/recurrent memory)"')


def _say(text: str):
    from halo_harness import events
    return events.Command("user_input", {"text": text})


@test
def test_prefix_tokens_and_cache_reused_on_the_ledger(ctx: Ctx):
    from tests.helpers.mock_ollama import _real_prompt_count
    with Rig() as rig:
        rig.mock.real_prompt_counts = False
        rig.script("wide:14b", answer(prompt_eval=lambda body: int(_real_prompt_count(body) * 0.8)))
        s = rig.session("ol:wide:14b@lan")
        rig.run(s, [_say("one")])
        line = [x for x in ledger_lines(rig.state_dir) if x.get("kind") == "turn"][-1]
        ctx.check(f"prefix_tokens, got {line.get('prefix_tokens')}", isinstance(line.get("prefix_tokens"), int)
                  and line["prefix_tokens"] == s._prompt_prefix["tokens"] > 1000)
        pct = line.get("cache_reused_pct")
        ctx.check(f"Ollama read about 80 % of the prompt: cache reused about 20 %, got {pct}", isinstance(pct, int) and 15 <= pct <= 26)
        ctx.check("not counted as a trim", line.get("trimmed") is False)


@test
def test_cache_reused_pct_rules(ctx: Ctx):
    from halo_harness.ollama_steward.ledger_prompt import cache_pct, finish
    ctx.check("a full read is 0", cache_pct(9000, 10024, 1024) == 0)
    ctx.check("a count over the estimate is 0", cache_pct(12000, 10024, 1024) == 0)
    ctx.check("a 3 % gap (the estimate's own noise) is 0", cache_pct(8730, 10024, 1024) == 0)
    ctx.check(f"half read is 50, got {cache_pct(4500, 10024, 1024)}", cache_pct(4500, 10024, 1024) == 50)
    line = {"status": 200, "prompt_eval_count": 4500, "estimate_tokens": 10024, "trimmed": True, "load_ms": 10.0}
    finish(line, 1024)
    ctx.check(f"a trimmed call is 0 (the low count is the cut), got {line}", line["cache_reused_pct"] == 0 and line["warming"] is False)
    line = {"status": 500, "prompt_eval_count": None, "estimate_tokens": 10024}
    finish(line, 1024)
    ctx.check("no count: None", line["cache_reused_pct"] is None)


@test
def test_the_ollama_panel_says_cache_reused(ctx: Ctx):
    from halo_harness.providers.ollama_panel import HostAnalysis, ModelFitInfo, format_host_analysis
    fit = ModelFitInfo(name="wide:14b", learned_cap=None, what_fits=32768, source="trained context",
                       throughput={"tokens_per_second": 41.0, "prefill_seconds": 0.4, "offloaded": False, "cache_reused_pct": 62})
    a = HostAnalysis(host_name="lan", host_url="http://127.0.0.1:1", is_local=True, reachable=True, version="0.40.13",
                     loaded=(), gpu=None, catalog_fits=(fit,))
    text = format_host_analysis(a)
    ctx.check(f"the last-turn line, got {[x for x in text.splitlines() if 'last turn' in x]}",
              "last turn: 41.0 tok/s, prefill 0.4 s, cache reused 62 %" in text)


@test
def test_no_prompt_cache_from_the_log_becomes_a_card_quirk(ctx: Ctx):
    from halo_harness.ollama_steward.explain import symptom_rows
    from halo_harness.ollama_steward.server_context import Rules
    from halo_harness.ollama_steward.server_events import record_events
    from halo_harness.ollama_steward.server_rules import classify
    from halo_harness.providers.model_card_quirks import QUIRKS, with_quirks
    ev = classify(LOG_LINE)
    ctx.check(f"the event kind, got {ev and ev['kind']}", bool(ev) and ev["kind"] == "no-prompt-cache" and ev["severity"] == "warn")
    r = Rules()
    r.feed('time=2026-10-29T21:14:00.000-04:00 level=INFO msg="template selection" model=registry.ollama.ai/library/mythos-sec:24b-gpu')
    got = r.feed(LOG_LINE)
    ctx.check(f"the model it belongs to, from the lines before it, got {[e.get('model') for e in got]}",
              [e.get("model") for e in got] == ["mythos-sec:24b-gpu"])
    state = Path(tempfile.mkdtemp(prefix="pb_cache_state-"))
    record_events(state, got, host="lan")
    card = {"name": "mythos-sec:24b-gpu", "kind": "ollama", "how": ["tools: native Ollama format"]}
    out = with_quirks(card, state)
    ctx.check(f"the quirk and its how line, got {out.get('quirks')}",
              [q["kind"] for q in out.get("quirks") or []] == ["no-prompt-cache"] and out["how"][-1] == QUIRKS["no-prompt-cache"])
    ctx.check("another model's card is unchanged", with_quirks({**card, "name": "qwen3.8:27b"}, state) ==
              {**card, "name": "qwen3.8:27b"})
    ctx.check("the steward's knowledge explains it", "no-prompt-cache" in symptom_rows())
    from types import SimpleNamespace
    from halo_harness.providers.model_card import card_of
    host = SimpleNamespace(name="lan", url="http://127.0.0.1:9", max_ctx=None, keep_alive=None, dialect=None)
    row = {"model": "mythos-sec:24b-gpu", "name": "mythos-sec:24b-gpu", "capabilities": ["completion", "tools"],
           "details": {"family": "mistral3"}}
    full = card_of("ol:mythos-sec:24b-gpu@lan", state_dir=state, catalog={"models": [row]}, host=host)
    ctx.check(f"the card the Local tab's model row shows carries it, got {full.get('quirks')}",
              [q["kind"] for q in full.get("quirks") or []] == ["no-prompt-cache"] and QUIRKS["no-prompt-cache"] in full["how"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
