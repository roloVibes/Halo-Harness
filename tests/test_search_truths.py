"""tests.test_search_truths -- Halo 3.3.6.0 R2 "the three truths" (models_library/truths.py, truth_rules.py) on
fixture rows, cards and profiles; no request, no model call:

1. a card `sources` line -> its truth: `/api/show`, the library's chips, the hub's tags = declared; the family rules
   and the name = expected; the battery = verified; "the server does not say" = nothing;
2. every truth per fact: an Ollama library row (declared chips, the name's coder), a hub row (its tags: tools,
   security as a weak signal, languages), an installed card (`/api/show`), a battery profile (verified);
3. the absent case: a capability nothing says about is not in the facts at all;
4. the verified-only facts (agentic-ready, verifier, tool-call accuracy) say "needs a probe" until probed;
5. the fit fields' truths (window, params, size, fits) and the card's blocks marked with all three.
Run: python -m tests.test_search_truths
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.search_rig import profile  # noqa: E402

test, TESTS = new_registry()


def _ollama_row(name="qwen3-coder:30b", caps=("tools",), ctx=262144):
    from halo_harness.models_library.row_builders import ollama_row
    base, size = name.split(":")
    entry = {"name": base, "capabilities": list(caps), "sizes": [size], "description": "", "pulls_n": 10}
    tags = [{"tag": size, "size_bytes": 19 * 10 ** 9, "size_text": "19GB", "context": ctx, "context_text": "256K", "input": ["Text"]}]
    return ollama_row(entry, size, tags, None, "the tags page")


def _hub_row(rid="acme/Sec-Agent-12B-GGUF", tags=("function-calling", "security", "en", "de", "fr", "es", "it"), pipe="text-generation"):
    from halo_harness.models_library.row_builders import hf_repo_row
    return hf_repo_row({"id": rid, "kind": "gguf", "tags": list(tags), "pipeline_tag": pipe, "downloads": 5, "license": "apache-2.0"})


def _facts(row, p=None):
    from halo_harness.models_library.rows import card_for_row
    from halo_harness.models_library.truths import facts_for_row
    return facts_for_row(row, card_for_row(row), p)


@test
def test_a_source_line_says_its_truth(ctx: Ctx):
    from halo_harness.models_library.truths import source_truth
    cases = {"/api/show capabilities": "declared", "the library's chips: tools": "declared",
             "the hub's pipeline tag": "declared", "the repo's gguf metadata (context_length)": "declared",
             "the name (-coder)": "expected", "a chat model (no purpose word in its name)": "expected",
             "estimate: the library's default quantization": "expected", "the battery made a call": "verified",
             "the tool-call probe got no call": "verified", "the name (no thinking word): the server does not say": None,
             "unknown": None, "": None}
    got = {k: source_truth(k) for k in cases}
    ctx.check(f"each line's truth, got {got}", got == cases)


@test
def test_every_truth_per_fact_on_rows_cards_and_profiles(ctx: Ctx):
    f = _facts(_ollama_row())
    ctx.check(f"the library's tools chip: declared, got {f.get('tools')}", f["tools"]["value"] is True and f["tools"]["truth"] == "declared")
    ctx.check(f"the chips say no thinking: declared False, got {f.get('thinking')}", f["thinking"] == {**f["thinking"], "value": False, "truth": "declared"})
    ctx.check(f"coder from the name: expected, got {f.get('coder')}", f["coder"]["value"] is True and f["coder"]["truth"] == "expected")
    ctx.check(f"a 262,144 claim is expected recall, got {f.get('long-context')}", f["long-context"]["truth"] == "expected" and "needle" in f["long-context"]["why"])
    h = _facts(_hub_row())
    ctx.check(f"the hub's function-calling tag: tools declared, got {h.get('tools')}", h["tools"]["truth"] == "declared")
    ctx.check(f"security from a tag, said to be a weak signal, got {h.get('security')}",
              h["security"]["truth"] == "declared" and "weak signal" in h["security"]["why"])
    ctx.check(f"five language tags: multilingual declared, got {h.get('multilingual')}", h["multilingual"]["truth"] == "declared")
    a = _facts(_hub_row("acme/Qwen3-8B-abliterated-GGUF", tags=()))
    ctx.check(f"abliterated from the name: expected, got {a.get('abliterated')}", a["abliterated"]["truth"] == "expected")
    ctx.check(f"a qwen3 hub repo with no tags: tools expected from the family, got {a.get('tools')}", a["tools"]["truth"] == "expected")
    from halo_harness.providers.model_card import card_of
    from halo_harness.models_library.truths import facts_for_row
    cat = {"models": [{"model": "qwen3.5:9b", "name": "qwen3.5:9b", "capabilities": ["completion", "tools", "thinking", "vision"],
                       "details": {"family": "qwen35", "parameter_size": "9.7B", "quantization_level": "Q4_K_M"}}]}
    card = card_of("ol:qwen3.5:9b@box", catalog=cat)
    c = facts_for_row({"name": "qwen3.5:9b"}, card, None)
    ctx.check(f"an installed card: /api/show declares tools, thinking, vision, got {[(k, c[k]['truth']) for k in ('tools', 'thinking', 'vision') if k in c]}",
              all(c.get(k, {}).get("truth") == "declared" for k in ("tools", "thinking", "vision")))
    p = profile("qwen3-coder:30b", tools="no", agentic_ready=False, identifiers="unverified", speed={"tok_s": 220.0})
    v = _facts(_ollama_row(), p)
    ctx.check(f"the profile wins: tools verified False, got {v.get('tools')}", v["tools"]["value"] is False and v["tools"]["truth"] == "verified")
    ctx.check(f"agentic-ready verified and why it misses, got {v.get('agentic-ready')}",
              v["agentic-ready"]["truth"] == "verified" and "tool calls" in v["agentic-ready"]["why"])
    ctx.check(f"verifier verified False (invented ids), got {v.get('verifier')}", v["verifier"]["value"] is False and v["verifier"]["truth"] == "verified")
    ctx.check(f"bulk from the measured speed, got {v.get('bulk')}", v["bulk"]["truth"] == "verified" and v["bulk"]["value"] is True)


@test
def test_a_capability_with_no_source_is_absent(ctx: Ctx):
    f = _facts(_hub_row("acme/Plain-7B-GGUF", tags=()))
    ctx.check(f"nothing says tools, math, audio, security or multilingual: absent, got {sorted(f)}",
              not any(k in f for k in ("tools", "math", "audio", "security", "multilingual", "abliterated")))
    ctx.check(f"the thinking of a model the server says nothing about is absent, got {f.get('thinking')}", "thinking" not in f)


@test
def test_the_verified_only_facts_need_a_probe(ctx: Ctx):
    f = _facts(_ollama_row())
    for cap in ("agentic-ready", "verifier", "tool-accuracy"):
        ctx.check(f"{cap}: needs a probe, got {f.get(cap)}", f[cap]["probe"] is True and f[cap]["truth"] is None and
                  f[cap]["value"] is None and "needs a probe" in f[cap]["why"] and "download and verify" in f[cap]["why"])
    v = _facts(_ollama_row(), profile("qwen3-coder:30b"))
    ctx.check(f"probed: agentic-ready and verifier verified, got {v['agentic-ready']} {v['verifier']}",
              v["agentic-ready"]["truth"] == "verified" and v["verifier"]["truth"] == "verified")
    ctx.check(f"tool-call accuracy needs the multi-tool probe on a profile made before it, got {v['tool-accuracy']}",
              v["tool-accuracy"]["probe"] and "multi-tool" in v["tool-accuracy"]["why"])
    a = _facts(_ollama_row(), {**profile("qwen3-coder:30b"), "tool_call_accuracy": 1.0, "tool_call_why": "find_user right"})
    ctx.check(f"3.3.6.0 R4: the multi-tool probe's score makes it verified, got {a['tool-accuracy']}",
              a["tool-accuracy"]["truth"] == "verified" and a["tool-accuracy"]["value"] is True
              and "100%" in a["tool-accuracy"]["why"])


@test
def test_the_fit_fields_and_the_blocks_carry_the_three_marks(ctx: Ctx):
    from halo_harness.models_library.rows import card_for_row
    from halo_harness.models_library.truths import truth_of
    row = _ollama_row()
    card = card_for_row(row)
    got = {k: truth_of(k, card, None, {**row, "fit": {"level": "fits", "estimate": True}}) for k in ("window", "params", "size", "fits", "speed")}
    ctx.check(f"window from the tags page and params from the size chip declared; size unknown; fits and speed expected, got {got}",
              got == {"window": "declared", "params": "declared", "size": "declared", "fits": "expected", "speed": "expected"})
    hub = _hub_row()
    ctx.check(f"a hub repo's size is an estimate: expected, got {truth_of('size', card_for_row(hub), None, hub)}",
              truth_of("size", card_for_row(hub), None, hub) == "expected")
    p = profile("qwen3-coder:30b")
    ctx.check("a profile's verified window makes fits verified",
              truth_of("fits", card, p, {**row, "fit": {"level": "fits"}}) == "verified")
    from halo_harness.providers.model_card import card_of
    from halo_harness.providers.model_card_blocks import block_lines
    cat = {"models": [{"model": "qwen3-coder:30b", "capabilities": ["completion", "tools"], "details": {"family": "qwen3moe",
                       "parameter_size": "30.5B", "quantization_level": "Q4_K_M"}}]}
    c = card_of("ol:qwen3-coder:30b@box", catalog=cat)
    marks = {x["mark"] for k in ("use_for", "limits") for x in c["blocks"][k]}
    ctx.check(f"before a probe: declared and expected, never verified, got {marks}", marks == {"declared", "expected"})
    ctx.check(f"the lines say (declared), got {block_lines(c['blocks'])}", any("(declared)" in x for x in block_lines(c["blocks"])))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
