"""tests.test_warming -- Halo 3.3.5.0 R4: warm-up truth. The first call after a
load (Ollama's `load_duration` over 2 s) is "warming": tagged on its ledger
line, the status bar says "warming" instead of a speed, and no speed figure
counts its tok/s (the steward's p50, the slow-box rule, `halo ollama
traffic`'s rollup, the saved last-turn reading). The Local tab's model rows
say "warm" or "cold (~N s to load)". Through the loop rig
(tests/helpers/prompt_budget_rig.py) and fixture ledgers; never a real
server or a model call.
Run: python -m tests.test_warming
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="pb_warm-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.model_switch_rig import ledger_lines  # noqa: E402
from tests.helpers.prompt_budget_rig import Rig, answer  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _say(text: str):
    from halo_harness import events
    return events.Command("user_input", {"text": text})


@test
def test_the_first_call_after_a_load_is_warming(ctx: Ctx):
    from halo_harness.model_display import format_ollama_throughput
    from halo_harness.providers.ollama_calibrate import get_last_turn_throughput
    with Rig() as rig:
        rig.script("wide:14b", answer(load_ns=9_000_000_000))  # a 9 s load
        s = rig.session("ol:wide:14b@lan")
        rig.run(s, [_say("first")])
        line = [x for x in ledger_lines(rig.state_dir) if x.get("kind") == "turn"][-1]
        ctx.check(f"the ledger line is tagged warming, got {line.get('warming')} (load_ms {line.get('load_ms')})",
                  line.get("warming") is True and line.get("load_ms") == 9000.0)
        st = s.status_event().data
        ctx.check(f"the status event: warming, no speed, got {st.get('ollama_warming')} {st.get('ollama_tokens_per_second')}",
                  st.get("ollama_warming") is True and st.get("ollama_tokens_per_second") is None)
        ctx.check("the status bar says warming", format_ollama_throughput(None, 0.05, False, warming=True) == "warming")
        ctx.check("no last-turn speed was kept from it",
                  get_last_turn_throughput(rig.state_dir, host_url=rig.mock.base_url, model="wide:14b") is None)
        rig.script("wide:14b", answer(load_ns=100_000))
        rig.run(s, [_say("second")])
        line = [x for x in ledger_lines(rig.state_dir) if x.get("kind") == "turn"][-1]
        st = s.status_event().data
        ctx.check(f"the next call is timed, got warming {line.get('warming')} speed {st.get('ollama_tokens_per_second')}",
                  line.get("warming") is False and isinstance(st.get("ollama_tokens_per_second"), float) and not st.get("ollama_warming"))
        kept = get_last_turn_throughput(rig.state_dir, host_url=rig.mock.base_url, model="wide:14b") or {}
        ctx.check(f"its speed is kept, got {kept.get('tokens_per_second')}", isinstance(kept.get("tokens_per_second"), float))


@test
def test_no_speed_figure_counts_a_warming_call(ctx: Ctx):
    from halo_harness.ollama_steward.rules import findings, window_stats
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.ollama_steward.traffic import rollup
    from tests.helpers.steward_seed import Home, line
    lines = [line(eval_tok_s=1.5, load_ms=30000.0, warming=True)] + [line(eval_tok_s=40.0) for _ in range(4)]
    ctx.check(f"the steward's p50 leaves the warming call out, got {window_stats(lines)['eval_p50']}",
              window_stats(lines)["eval_p50"] == 40.0)
    with Home() as h:
        h.calls(*[line(eval_tok_s=2.0, load_ms=30000.0, warming=True) for _ in range(4)], line(eval_tok_s=40.0))
        rules = [f["rule"] for f in findings(h.state)]
        ctx.check(f"warming calls never make a slow box, got {rules}", "slow-box" not in rules)
        rows = rollup(read_calls(h.state), [])
        ctx.check(f"the traffic rollup's tok/s leaves them out, got {[r.get('eval_tok_s') for r in rows]}",
                  [r.get("eval_tok_s") for r in rows] == [40.0])


@test
def test_the_local_tab_says_warm_or_cold(ctx: Ctx):
    from halo_harness.studio.local_warm import warm_map, warm_view
    from tests.helpers.steward_seed import Home, line
    with Home() as h:
        h.calls(line(load_ms=24400.0, warming=True), line(load_ms=40.0, cache_reused_pct=55))
        m = warm_map(h.state)
        e = m.get(("pc", "qwen3.8:27b"))
        ctx.check(f"the last load and the cache from the ledger, got {e}", e and e["load_s"] == 24 and e["cache_reused_pct"] == 55)
        cold = warm_view(e, None)
        ctx.check(f"not loaded: cold with the load time, got {cold}", cold["state"] == "cold" and cold["line"] == "cold (~24 s to load)"
                  and cold["cache_line"] == "cache reused 55 %")
        warm = warm_view(e, {"size_vram": 1})
        ctx.check(f"loaded: warm, got {warm['line']}", warm["state"] == "warm" and warm["line"].startswith("warm"))
        ctx.check("never seen: cold, no time", warm_view(None, None)["line"] == "cold (not loaded)")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
