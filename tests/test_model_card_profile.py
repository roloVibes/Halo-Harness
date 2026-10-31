"""tests.test_model_card_profile -- Halo 3.3.6.0 R1: the model card with the
battery's profile (providers/model_card_blocks.py, model_card.py,
model_card_words.py, studio/model_card_api.view, providers/fit_meter.py):

1. Use it for / Don't use it for / Where it sits / Limits from a probed
   profile, every value marked verified; the same blocks from the declared
   facts before a probe, every value marked expected;
2. `fit_for` becomes the profile's verdicts (orchestrator, coder, reviewer),
   each role's mark; the card's tools follow the probe; `system_role`;
3. the words: `halo models show`'s lines ("where it sits", "probed <date>",
   "(expected)"), Studio's view (blocks, probe, fit_source), the fit meter's
   word with the measured speed ("fits, ~188 tok/s at 32k").
Run: python -m tests.test_model_card_profile
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers import mock_ollama_battery as MB  # noqa: E402
from tests.helpers.battery_rig import BatteryRig, gpu_card  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _card(rig, name, hc=None):
    from halo_harness.providers.model_card import card_of
    row = {**MB.row(name), "capabilities": MB.KINDS[name]["caps"], "model_info": MB.KINDS[name]["info"]}
    return card_of(rig.ref(name), state_dir=rig.state, catalog=row, host=rig.host, host_card=hc)


def _marks(blocks) -> set:
    return {x["mark"] for k in ("use_for", "dont_use_for", "limits") for x in blocks.get(k) or []} | {blocks["sits"]["mark"]}


@test
def test_before_a_probe_every_block_is_expected(ctx: Ctx):
    with BatteryRig(["bt-mute:24b"]) as rig:
        c = _card(rig, "bt-mute:24b")
        b = c["blocks"]
        ctx.check(f"no profile on the card, got {c['profile']}", c["profile"] is None and c["system_role"] is None)
        ctx.check(f"the four blocks, all expected, got {_marks(b)}", _marks(b) == {"expected"} and b["sits"]["chip"])
        ctx.check(f"the limits say nothing is measured yet, got {b['limits']}", any("not measured" in x["text"] for x in b["limits"]))
        ctx.check(f"every role marked expected, got {c['fit_source']}", set(c["fit_source"].values()) == {"expected"})


@test
def test_a_probed_no_tools_model_says_what_it_is_for(ctx: Ctx):
    with BatteryRig(["bt-mute:24b", "bt-coder:30b"]) as rig:
        rig.probe("bt-mute:24b", card=gpu_card(24.0))
        rig.probe("bt-coder:30b", card=gpu_card(24.0))
        c = _card(rig, "bt-mute:24b", gpu_card(24.0))
        b = c["blocks"]
        ctx.check(f"where it sits: bulk worker, not interactive, verified, got {b['sits']}",
                  b["sits"]["chip"] == "bulk worker · non-agentic" and "not interactive" in b["sits"]["chips"]
                  and b["sits"]["mark"] == "verified")
        ctx.check(f"use it for: single-shot work, got {b['use_for']}", any("single-shot" in x["text"] for x in b["use_for"]))
        dont = " | ".join(x["text"] for x in b["dont_use_for"])
        ctx.check(f"don't use it for: tool-using sub-agents, chat, authoritative ids, got {dont}",
                  "tool-using sub-agent" in dont and "chat or /model" in dont and "authoritative ids" in dont)
        lim = " | ".join(x["text"] for x in b["limits"])
        ctx.check(f"limits: the window, the size, tok/s, the cold load, got {lim}", "window trained 131,072" in lim
                  and "14.3 GB" in lim and "300 tok/s" in lim and "cold load 6.5 s" in lim)
        ctx.check(f"the card's tools follow the probe, got {c['tools']} ({c['sources']['tools']})", c["tools"] == "none")
        ctx.check(f"fit_for is the profile's: no orchestrator, coder or reviewer, got {c['fit_for']}",
                  not c["fit_for"]["orchestrator"] and not c["fit_for"]["coder"] and not c["fit_for"]["reviewer"])
        ctx.check(f"those roles marked verified, got {c['fit_source']}", c["fit_source"]["coder"] == "verified")
        ctx.check(f"the weak system role on the card, got {c['system_role']}", c["system_role"] == "weak")
        ctx.check(f"a how line per placement note, got {c['how']}", any("authoritative IDs" in h for h in c["how"]))
        coder = _card(rig, "bt-coder:30b", gpu_card(24.0))
        ctx.check(f"the full agent can orchestrate (verified over the declared 'coding model'), got {coder['fit_for']}",
                  coder["fit_for"]["orchestrator"] and coder["fit_source"]["orchestrator"] == "verified")


@test
def test_the_words_the_view_and_the_speed_word(ctx: Ctx):
    from halo_harness.providers.fit_meter import fit_meter, speed_word
    from halo_harness.providers.model_card_words import card_line, card_lines
    from halo_harness.studio.model_card_api import view
    with BatteryRig(["bt-coder:30b"]) as rig:
        before = card_lines(_card(rig, "bt-coder:30b"))
        ctx.check(f"not probed: the line that probes it, got {before}", any("not probed yet: halo models probe" in x for x in before)
                  and any("(expected)" in x for x in before))
        rig.probe("bt-coder:30b", card=gpu_card(24.0))
        c = _card(rig, "bt-coder:30b", gpu_card(24.0))
        lines = card_lines(c)
        ctx.check(f"halo models show: where it sits, probed, the blocks, got {lines[-14:]}",
                  "  where it sits: full agent" in lines and any(x.startswith("  probed ") for x in lines)
                  and "  use it for:" in lines and "  limits:" in lines)
        row = {**MB.row("bt-coder:30b"), "model_info": MB.KINDS["bt-coder:30b"]["info"]}
        meter = fit_meter(c, gpu_card(24.0), row=row)
        ctx.check(f"the fit meter's word carries the speed, got {meter.get('word')!r}",
                  meter["word"] == f"{meter['level']}, ~188 tok/s at 32k")
        ctx.check(f"--cards' line shows it, got {card_line(c, meter)!r}", "~188 tok/s" in card_line(c, meter))
        v = view(c, meter)["card"]
        ctx.check(f"Studio's view: blocks, probe, fit_source, speed, got {sorted(v)}",
                  v["blocks"]["sits"]["chip"] == "full agent" and v["probe"]["agentic_ready"] is True
                  and v["fit_source"]["coder"] == "verified" and v["speed"]["tok_s"] == 187.5)
    ctx.check("no speed: the level alone", speed_word("fits", None) == "fits")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
