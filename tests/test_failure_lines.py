"""tests.test_failure_lines -- Halo 3.3.6.0 R1: when a local model fails in a
role, Halo says why with the fix (agent/local_failure.py through the loop rig,
tests/helpers/model_switch_rig.py: a real Session over a fake Ollama on
127.0.0.1:0; ollama_steward/failure_lines.py through `record_events`):

1. an empty reply with no tool call on a model the battery found with no tool
   calling: one line naming the probe date and a model with tools, no retry,
   never "provider failure";
2. the same on a model with no profile: retried once, then a plain line;
3. empty `content` with `thinking` and the budget cut: retried once with a
   raised reserve, the line says so, the answer lands;
4. a cold load past 10 s: the pin / pre-warm line, once;
5. an identifier from a model whose ids are unverified: the quirk line;
6. a spill event: "it didn't fit (59/66 layers on GPU): lower the window to
   ... or use ..."; a slow load: the cold-load line; two models that cannot
   co-reside: the swap line.
Run: python -m tests.test_failure_lines
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.mock_ollama import _finish_chat  # noqa: E402
from tests.helpers.model_switch_rig import Rig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _seed(state, model: str, *, host: str = "lan", **fields) -> dict:
    from halo_harness.providers.battery_probes import PROBE_SET
    from halo_harness.providers.battery_profile import finish
    from halo_harness.providers.ollama_capability import save_profile
    p = {"model": model, "host": host, "digest": f"sha256:seed-{model}", "ollama_version": "0.1.0-mock",
         "probe_set": PROBE_SET, "probed_at": time.time(), "tools": "yes", "system_role": "honoured",
         "instruction": "strict", "output": "json", "output_why": "", "identifiers": "trusted", "reasoning": "none",
         "window": {"trained": 65536, "used": 32768, "usable": 65536, "verified": True}, "kv_per_token": 40960,
         "size_gb": 17.3, "speed": {"tok_s": 150.0, "ttft_ms": 90, "cold_load_s": 25.0, "at_window": 32768},
         "resident": {"co_resides_with": [], "pivot_only": None}, "evidence": {"instruction": {"content": "BANANA"}}}
    p.update(fields)
    save_profile(state, finish(p))
    return p


def _say(text):
    from halo_harness import events
    return events.Command("user_input", {"text": text})


def _scn(steps):
    calls = {"n": 0, "bodies": []}

    def fn(h, body):
        calls["bodies"].append(body)
        i = min(calls["n"], len(steps) - 1)
        calls["n"] += 1
        _finish_chat(h, [steps[i]])
    fn.calls = calls
    return fn


def _reply(content="", thinking=None, *, done="stop", load=100_000, ev=3):
    msg = {"role": "assistant", "content": content}
    if thinking:
        msg["thinking"] = thinking
    return {"message": msg, "done": True, "done_reason": done, "prompt_eval_count": 50, "eval_count": ev,
            "load_duration": load, "eval_duration": 30_000_000, "prompt_eval_duration": 40_000_000}


def _lines(evs):
    return [e.data.get("text") or e.data.get("message") or "" for e in evs if e.kind in ("turn_marker", "error")]


def _ladder_off() -> None:
    """3.3.6.0 R4: with the degradation ladder on (agent/degrade.py) these failures walk its rungs first
    (tests/test_degrade.py); off, R1's own line is the answer, as pinned here."""
    from halo_harness.theme import set_config_value
    set_config_value("local.ladder", "off")


@test
def test_no_tool_calling_says_why_and_names_a_model(ctx: Ctx):
    with Rig() as rig:
        _ladder_off()
        _seed(rig.state_dir, "mid:14b", tools="no", interactive="no")
        _seed(rig.state_dir, "big:30b")
        scn = _scn([_reply("")])
        rig.mock.scenarios["mid:14b"] = scn
        evs = rig.run(rig.session("ol:mid:14b@lan"), [_say("list the files")])
        errs = [e.data for e in evs if e.kind == "error"]
        text = " ".join(str(e.get("message") or e.get("text") or "") for e in errs)
        ctx.check(f"one plain line with the fix, got {errs}", "no tool calling on this model (probed" in text
                  and "single-shot extraction" in text and "ol:big:30b@lan" in text)
        ctx.check(f"never the raw provider line, got {text!r}", "provider failure" not in text)
        ctx.check(f"no retry, got {scn.calls['n']} calls", scn.calls["n"] == 1)


@test
def test_an_empty_reply_twice_on_an_unprobed_model(ctx: Ctx):
    with Rig() as rig:
        _ladder_off()
        scn = _scn([_reply("")])
        rig.mock.scenarios["mid:14b"] = scn
        evs = rig.run(rig.session("ol:mid:14b@lan"), [_say("list the files")])
        text = " ".join(_lines(evs))
        ctx.check(f"retried once, then the plain line, got {scn.calls['n']} calls: {text!r}", scn.calls["n"] == 2
                  and "returned an empty reply twice" in text and "halo models probe ol:mid:14b@lan" in text
                  and "provider failure" not in text)


@test
def test_a_thinking_model_retried_with_a_bigger_reserve(ctx: Ctx):
    with Rig() as rig:
        scn = _scn([_reply("", "thinking it through " * 20, done="length", ev=64), _reply("the answer is 4")])
        rig.mock.scenarios["big:30b"] = scn
        evs = rig.run(rig.session("ol:big:30b@lan"), [_say("what is 2+2")])
        first, second = (b["options"]["num_predict"] for b in scn.calls["bodies"][:2])
        lines = _lines(evs)
        ctx.check(f"the second call's reserve raised, got {first} -> {second}", second == max(300, first * 2))
        ctx.check(f"the line says it, got {lines}", any(f"it answered in thinking; the reply budget was too small: "
                                                        f"retried with {second:,} tokens" in x for x in lines))
        texts = [e.data.get("text") for e in evs if e.kind in ("text_delta", "text_chunk", "message_end")]
        ctx.check(f"the answer lands, got {texts}", any("the answer is 4" in (t or "") for t in texts))


@test
def test_a_cold_load_and_an_unverified_id(ctx: Ctx):
    with Rig() as rig:
        _seed(rig.state_dir, "big:30b", identifiers="unverified", identifiers_why="answered CWE-20 (right: CWE-284)")
        rig.mock.scenarios["big:30b"] = _scn([_reply("That is CWE-20, improper input validation.", load=25_000_000_000)])
        s = rig.session("ol:big:30b@lan")
        evs = rig.run(s, [_say("which CWE?"), _say("again?")])
        lines = _lines(evs)
        cold = [x for x in lines if "cold load of 17.3 GB, ~25 s: pin it (`keep_alive -1`) or pre-warm" in x]
        ctx.check(f"the cold-load line, once a session, got {lines}", len(cold) == 1)
        ids = [x for x in lines if "its reference IDs are unverified (probed" in x and "CWE-20" in x]
        ctx.check(f"the unverified-id line, got {lines}", len(ids) == 1)


@test
def test_the_steward_events_say_their_fix(ctx: Ctx):
    from halo_harness.ollama_steward.failure_lines import swap_line
    from halo_harness.ollama_steward.server_events import read_events, record_events
    from halo_harness.ollama_steward.server_rules import event
    with Rig() as rig:
        _seed(rig.state_dir, "big:30b", size_gb=40.0, window={"trained": 65536, "used": 65536, "usable": 24576,
                                                               "verified": False},
              resident={"co_resides_with": [], "pivot_only": True})
        _seed(rig.state_dir, "small:9b", size_gb=6.6)
        record_events(rig.state_dir, [
            event("cpu-spill", "59 of 66 layers are on the GPU", "offloaded 59/66 layers", model="big:30b", offloaded=59, layers=66),
            event("slow-load", "a load took 200 s", "llama-server started in 200 seconds", model="big:30b", seconds=200.0)],
            host="lan")
        evs = {e["kind"]: e for e in read_events(rig.state_dir)}
        ctx.check(f"the spill line, got {evs['cpu-spill']['say']!r}", "it didn't fit (59/66 layers on GPU): lower the "
                  "window to 24,576 or use ol:small:9b" in evs["cpu-spill"]["say"])
        ctx.check(f"the slow load's line, got {evs['slow-load']['say']!r}",
                  "cold load of 40 GB, ~200 s: pin it (keep_alive -1) or pre-warm" in evs["slow-load"]["say"])
        line = swap_line(["big:30b", "small:9b"], "lan", rig.state_dir)
        ctx.check(f"the swap line, got {line!r}", "can't co-reside on this card" in line and "pivot explicitly" in line)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
