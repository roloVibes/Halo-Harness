"""tests.test_ollama_precedence_5b -- Halo 2.0.3 round 5b: `providers.
ollama.resolve_num_ctx_and_source`'s learned-cap/host-max_ctx/live-fit/
remote-default precedence chain (brief item 3, the MUST-FIX from the
LAN-host live run), plus the stable-request-prefix pinning test (brief's
own "Stable request prefix" bullet). Pure functions and `providers.
ollama_request.build_ollama_request_body` only -- no network, no mock
server needed here (see tests/test_ollama_calibrate.py for the parts that
DO need mock_ollama).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


# ---- resolve_num_ctx_and_source / compute_num_ctx precedence -------------

@test
def test_every_pre_5b_pinned_case_is_unchanged(ctx: Ctx):
    """The exact assertions tests/test_providers_ollama.py and
    tests/test_providers_ollama_hw.py already pin for `compute_num_ctx`'s
    three-positional-arg (pre-5b) call shape -- re-pinned here as a single
    regression sentinel for the round-5b rewrite, which MUST produce
    identical numbers for every one of these when `learned_cap`/`remote`
    are left at their defaults.

    Review fix pass (finding 5): TWO of these are no longer "unchanged" --
    see the inline notes below for why each one's expected value moved,
    and tests/test_providers_ollama.py's own
    test_compute_num_ctx_clamps_to_minimum_of_every_candidate /
    tests/test_providers_ollama_hw.py's own
    test_compute_num_ctx_weights_do_not_fit_uses_conservative_fallback_
    not_hard_cap for the matching updates to THOSE files' copies."""
    from halo_harness.providers.ollama import FALLBACK_NUM_CTX, HARD_CONTEXT_CAP, \
        REMOTE_UNKNOWN_DEFAULT_NUM_CTX, compute_num_ctx
    from halo_harness.providers.ollama_fit import WEIGHTS_DO_NOT_FIT
    ctx.check("nothing known -> fallback", compute_num_ctx(None, None, None) == FALLBACK_NUM_CTX)
    ctx.check("trained context wins when smallest", compute_num_ctx(16384, 32768, None) == 16384)
    ctx.check("host.max_ctx wins when smallest", compute_num_ctx(131072, 32768, None) == 32768)
    ctx.check("a fit estimate wins when smallest", compute_num_ctx(131072, 65536, 8000) == 8000)
    # Finding 5: a LOCAL host with nothing known is no longer treated as
    # "always has an OS probe to fall back on" -- it gets the SAME
    # conservative default a remote host with nothing known always has
    # (see test_remote_host_nothing_known_gets_32768_never_131072 below),
    # never the hard cap just because a huge trained context is known.
    ctx.check("a local host with nothing known gets the conservative default, never the bare hard cap",
              compute_num_ctx(1_000_000, None, None) == REMOTE_UNKNOWN_DEFAULT_NUM_CTX == 32768)
    # FALLBACK_NUM_CTX itself moved 8192 -> 16384 this same fix pass
    # (finding 4: the old 8192 placeholder sat below Halo's own measured
    # ~10.2k-token minimum prompt cost) -- unrelated to finding 5, but
    # this exact assertion needs the symbol now, not the stale literal.
    ctx.check("weights-do-not-fit -> fallback, not the hard cap",
              compute_num_ctx(262144, None, WEIGHTS_DO_NOT_FIT) == FALLBACK_NUM_CTX)
    ctx.check("weights-do-not-fit + a smaller host.max_ctx -> that override",
              compute_num_ctx(262144, 4096, WEIGHTS_DO_NOT_FIT) == 4096)
    ctx.check("plain unknown fit on a local host -> the conservative default, not the hard cap",
              compute_num_ctx(262144, None, None) == 32768)


@test
def test_learned_cap_never_beats_a_smaller_live_fit_estimate(ctx: Ctx):
    """Review fix pass (finding 6): a learned cap used to REPLACE the
    live fit estimate outright ("ground truth beats a computed guess") --
    renamed and rewritten from this test's own pre-fix name/assertions,
    which pinned EXACTLY the bug finding 6 reports: a cap measured on an
    idle GPU kept winning once something else (an image server, a media
    transcoder) later held some of that VRAM, loading the session
    partially offloaded. The smaller of the two numbers must win now,
    whichever one that is -- never an override chain keyed on WHICH
    candidate is "more ground-truth-y"."""
    from halo_harness.providers.ollama import resolve_num_ctx_and_source
    from halo_harness.providers.ollama_fit import WEIGHTS_DO_NOT_FIT
    num_ctx, source = resolve_num_ctx_and_source(262144, None, 8192, learned_cap=65536)
    ctx.check(f"the SMALLER live estimate (8192) wins over the bigger stale cap (65536), got {num_ctx}",
              num_ctx == 8192)
    ctx.check(f"source names the fit estimate, got {source!r}", source == "fit estimate")
    num_ctx1b, source1b = resolve_num_ctx_and_source(262144, None, 65536, learned_cap=8192)
    ctx.check(f"and the direction is symmetric -- a smaller cap wins over a bigger live estimate too, "
              f"got {num_ctx1b}", num_ctx1b == 8192)
    ctx.check(f"source names the learned cap this time, got {source1b!r}", source1b == "learned cap")
    # WEIGHTS_DO_NOT_FIT is not a usable int -- there is no live NUMBER to
    # compare the cap against, so the cap still stands alone (a measured
    # fact that the model DOES fit at some size, unlike an ordinary
    # smaller live reading, is never second-guessed by the sentinel).
    num_ctx2, source2 = resolve_num_ctx_and_source(262144, None, WEIGHTS_DO_NOT_FIT, learned_cap=65536)
    ctx.check(f"learned cap still overrides WEIGHTS_DO_NOT_FIT (no live number to compare against), "
              f"got {num_ctx2}", num_ctx2 == 65536)
    ctx.check(f"source2 names the learned cap, got {source2!r}", source2 == "learned cap")
    from halo_harness.providers.ollama import FALLBACK_NUM_CTX
    ctx.check("the fallback is NOT invoked once a learned cap is known", num_ctx2 != FALLBACK_NUM_CTX)


@test
def test_learned_cap_still_bounded_by_trained_context_and_hard_cap(ctx: Ctx):
    """A learned cap never lets `num_ctx` exceed the model's own trained
    context or the 131072 hard cap -- it competes in the SAME min(), it
    never bypasses them."""
    from halo_harness.providers.ollama import resolve_num_ctx_and_source
    num_ctx, source = resolve_num_ctx_and_source(16384, None, None, learned_cap=65536)
    ctx.check(f"trained context (16384) still wins over a bigger learned cap, got {num_ctx}", num_ctx == 16384)
    ctx.check(f"source names trained context, got {source!r}", source == "trained context")
    # trained_context must be KNOWN (not None) here -- an unknown trained
    # context is a SEPARATE, pre-5b-documented reason the fallback joins
    # the candidate pool (see resolve_num_ctx_and_source's own docstring:
    # "still clamped... like any other candidate" -- it is just one more
    # min() entry, not a special override), so pairing an absurd
    # learned_cap with trained_context=None would correctly yield the
    # fallback via that unrelated rule, not what THIS test means to
    # isolate.
    num_ctx2, source2 = resolve_num_ctx_and_source(999_999_999, None, None, learned_cap=999_999_999)
    ctx.check(f"the 131072 hard cap still wins over an absurd learned cap, got {num_ctx2}", num_ctx2 == 131072)
    ctx.check(f"source2 names the hard cap, got {source2!r}", source2 == "hard cap")


@test
def test_remote_host_nothing_known_gets_32768_never_131072(ctx: Ctx):
    """The LAN-host live-run MUST FIX: a remote host with no host.max_ctx,
    no learned cap, and no live fit estimate gets the conservative 32768
    default -- never the 131072 hard cap."""
    from halo_harness.providers.ollama import REMOTE_UNKNOWN_DEFAULT_NUM_CTX, resolve_num_ctx_and_source
    num_ctx, source = resolve_num_ctx_and_source(262144, None, None, remote=True)
    ctx.check(f"32768, not 131072, got {num_ctx}", num_ctx == REMOTE_UNKNOWN_DEFAULT_NUM_CTX == 32768)
    ctx.check(f"source names the remote default, got {source!r}", source == "remote default")


@test
def test_local_host_nothing_known_also_gets_a_conservative_default_never_131072(ctx: Ctx):
    """Review fix pass (finding 5): this test's own name used to be
    "...still gets the ordinary hard cap", with a comment arguing a local
    host "always has an OS probe to fall back on well before 'nothing
    known' would apply" -- exactly the assumption the review found false
    (a CPU-only box, a VM, AMD on Windows with no rocm-smi, Intel, Linux
    AMD via sysfs all read as "nothing known" too, same as a remote host
    with no GPU access). A local host with nothing known now gets the
    SAME 32768 default a remote host gets; a POSITIVELY-known CPU-only
    box (no GPU hardware at all, `cpu_only=True`) tightens that further
    to 8192 -- a CPU-only box's KV cache comes out of system RAM, not a
    GPU's own budget."""
    from halo_harness.providers.ollama import resolve_num_ctx_and_source
    num_ctx, source = resolve_num_ctx_and_source(262144, None, None, remote=False)
    ctx.check(f"local host, nothing known -> the conservative default (32768), not the hard cap, got {num_ctx}",
              num_ctx == 32768)
    ctx.check(f"source names the conservative default, got {source!r}", source == "conservative default")
    num_ctx_cpu, source_cpu = resolve_num_ctx_and_source(262144, None, None, remote=False, cpu_only=True)
    ctx.check(f"a CPU-only box gets the tighter 8192 instead, got {num_ctx_cpu}", num_ctx_cpu == 8192)
    ctx.check(f"source still names the conservative default, got {source_cpu!r}", source_cpu == "conservative default")
    # host_max_ctx/a live fit estimate/a learned cap still mean "not
    # nothing known" for a local host too, same as remote -- unaffected
    # by this fix (already covered for remote by the sibling tests
    # below; re-pinned once here for the local path specifically).
    num_ctx_known, _ = resolve_num_ctx_and_source(262144, 4096, None, remote=False)
    ctx.check(f"a configured host.max_ctx still wins, got {num_ctx_known}", num_ctx_known == 4096)


@test
def test_recorded_does_not_fit_routes_to_the_fallback_like_a_live_sentinel(ctx: Ctx):
    """Review fix pass (finding 5): `recorded_does_not_fit=True` (a prior
    calibration attempt measured this model does NOT fit, recorded on
    disk) must be treated like a live `WEIGHTS_DO_NOT_FIT` reading --
    the fallback joins the pool instead of the "nothing known" default
    (or trained_context/hard_cap) being left to win, UNLESS a learned_
    cap is ALSO known (proof it DOES fit at some size), which still
    overrides a stale does-not-fit record exactly like it overrides the
    live sentinel."""
    from halo_harness.providers.ollama import FALLBACK_NUM_CTX, resolve_num_ctx_and_source
    num_ctx, source = resolve_num_ctx_and_source(262144, None, None, remote=False, recorded_does_not_fit=True)
    ctx.check(f"routes to the fallback, not the conservative default or the hard cap, got {num_ctx}",
              num_ctx == FALLBACK_NUM_CTX)
    ctx.check(f"source names the fallback, got {source!r}", source == "fallback")
    num_ctx2, source2 = resolve_num_ctx_and_source(262144, None, None, remote=False, recorded_does_not_fit=True,
                                                     learned_cap=65536)
    ctx.check(f"a learned cap still overrides a stale does-not-fit record, got {num_ctx2}", num_ctx2 == 65536)
    ctx.check(f"source2 names the learned cap, got {source2!r}", source2 == "learned cap")


@test
def test_remote_host_max_ctx_is_the_documented_explicit_override(ctx: Ctx):
    """`ollama.hosts[].max_ctx` is the documented override for the remote-
    unknown-default case (release-notes-for-fix-pass.md) -- once it is
    SET, "nothing known" is no longer true, so the operator's own number
    wins (still bounded by the hard cap -- see the next test)."""
    from halo_harness.providers.ollama import resolve_num_ctx_and_source
    num_ctx, source = resolve_num_ctx_and_source(262144, 16384, None, remote=True)
    ctx.check(f"host.max_ctx (16384) wins, not 32768, got {num_ctx}", num_ctx == 16384)
    ctx.check(f"source names host max_ctx, got {source!r}", source == "host max_ctx")


@test
def test_remote_host_max_ctx_still_never_exceeds_hard_cap(ctx: Ctx):
    from halo_harness.providers.ollama import HARD_CONTEXT_CAP, resolve_num_ctx_and_source
    num_ctx, source = resolve_num_ctx_and_source(262144, 500_000, None, remote=True)
    ctx.check(f"the hard cap still wins over an oversized host.max_ctx, got {num_ctx}", num_ctx == HARD_CONTEXT_CAP)
    ctx.check(f"source names the hard cap, got {source!r}", source == "hard cap")


@test
def test_remote_with_a_live_fit_estimate_does_not_need_the_default(ctx: Ctx):
    """"nothing known" specifically means no host.max_ctx AND no usable
    fit signal -- a remote host that DOES have a live fit estimate (e.g.
    its own already-loaded /api/ps context, or an ssh GPU read) never
    falls back to the 32768 default at all."""
    from halo_harness.providers.ollama import resolve_num_ctx_and_source
    num_ctx, source = resolve_num_ctx_and_source(262144, None, 16384, remote=True)
    ctx.check(f"the live fit estimate (16384) wins, got {num_ctx}", num_ctx == 16384)
    ctx.check(f"source names the fit estimate, got {source!r}", source == "fit estimate")


# ---- stable request prefix (brief's own "Stable request prefix" bullet) --

def _route_profile(model="qwen3:30b"):
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.routing import Route
    route = Route(provider="ollama", upstream_model=model, dialect="ollama")
    return route, resolve_profile(route)


@test
def test_prefix_byte_stable_across_two_consecutive_turns(ctx: Ctx):
    """Builds two bodies simulating turn 1 and turn 2 of the SAME `ol:`
    session (identical system_text/tools/host/trained_context/fit_
    estimate -- the ordinary case once a model is loaded, per round 3's
    own fix pass: a loaded model's fit estimate is read from `/api/ps`'s
    own context_length and does not fluctuate turn to turn) and asserts
    the PREFIX -- the leading system message, the tools array, and
    `options` -- is byte-identical. Tool list passed in a DIFFERENT
    order between the two calls on purpose: `convert_tools`'s own
    alphabetical sort (not this test) is what makes tool order stable
    regardless of the caller's own list order."""
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_request import build_ollama_request_body
    route, profile = _route_profile()
    host = OllamaHost(name="default", url="http://127.0.0.1:11434")
    tools_turn1 = [
        {"name": "Read", "description": "Read a file", "input_schema": {"type": "object", "properties": {}}},
        {"name": "Bash", "description": "Run a command", "input_schema": {"type": "object", "properties": {}}},
    ]
    tools_turn2 = list(reversed(tools_turn1))  # same SET, deliberately different order

    turn1_messages = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
    body1 = build_ollama_request_body(system_text="You are Halo.", messages=turn1_messages, tools=tools_turn1,
                                       tool_choice=None, route=route, profile=profile, effort="medium", host=host,
                                       trained_context=40960, fit_estimate=16384)
    turn2_messages = turn1_messages + [
        {"role": "assistant", "content": [{"type": "text", "text": "hi there"}]},
        {"role": "user", "content": [{"type": "text", "text": "again"}]},
    ]
    body2 = build_ollama_request_body(system_text="You are Halo.", messages=turn2_messages, tools=tools_turn2,
                                       tool_choice=None, route=route, profile=profile, effort="medium", host=host,
                                       trained_context=40960, fit_estimate=16384)
    ctx.check(f"leading system message identical, got {body1['messages'][0]!r} vs {body2['messages'][0]!r}",
              body1["messages"][0] == body2["messages"][0])
    ctx.check(f"system message is actually the leading one (role=system)",
              body1["messages"][0]["role"] == "system")
    ctx.check(f"tools array identical (order-independent input), got {body1.get('tools')} vs {body2.get('tools')}",
              body1.get("tools") == body2.get("tools"))
    ctx.check(f"options identical, got {body1['options']} vs {body2['options']}",
              body1["options"] == body2["options"])
    # The part that's VOLATILE BY DESIGN: the full messages list grows
    # (turn 2 carries turn 1's own reply plus the new user turn) -- never
    # claimed stable, only the prefix (system/tools/options) is.
    ctx.check("the full messages list legitimately GROWS turn to turn (not part of the stable prefix)",
              len(body2["messages"]) > len(body1["messages"]))


@test
def test_prefix_stable_even_when_learned_cap_and_remote_are_set(ctx: Ctx):
    """The round-5b additions (`learned_cap`/`remote`) must not themselves
    introduce volatility -- same two-turn shape, now also passing a
    learned cap and remote=True, still byte-stable."""
    from halo_harness.providers.ollama import OllamaHost
    from halo_harness.providers.ollama_request import build_ollama_request_body
    route, profile = _route_profile()
    host = OllamaHost(name="remote", url="http://gpu-box.example:11434")
    tools = [{"name": "Read", "description": "Read a file", "input_schema": {"type": "object", "properties": {}}}]
    turn1_messages = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
    kwargs = dict(system_text="You are Halo.", tools=tools, tool_choice=None, route=route, profile=profile,
                  effort="medium", host=host, trained_context=131072, fit_estimate=None,
                  learned_cap=32768, remote=True)
    body1 = build_ollama_request_body(messages=turn1_messages, **kwargs)
    turn2_messages = turn1_messages + [
        {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
        {"role": "user", "content": [{"type": "text", "text": "again"}]},
    ]
    body2 = build_ollama_request_body(messages=turn2_messages, **kwargs)
    ctx.check("system message stable with learned_cap/remote set", body1["messages"][0] == body2["messages"][0])
    ctx.check(f"options stable (num_ctx from the learned cap both times), got {body1['options']} "
              f"vs {body2['options']}", body1["options"] == body2["options"])
    ctx.check(f"num_ctx is actually the learned cap (32768), got {body1['options'].get('num_ctx')}",
              body1["options"].get("num_ctx") == 32768)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
