"""tests.test_steward_hotfix -- Halo 3.3.13.1, the steward hotfix (plans/ROADMAP.md F1, the brief's (a)-(c)):

(a) the reply reserve is bounded (ollama_steward/rules_reply_bound.py): its target comes from the measured cut,
    never from the profile's current value; never above the model's own context minus the prompt; one an hour per
    model, whatever the session; never twice for one cut; the runaway the owner's PC showed (auto mode doubling num_predict
    at each cut) stops after one change, and a `reserve-loop` finding says the loop would have happened;
(b) the steward's own calls are tagged `by: "steward"` (agent.live_call) and never read back by its rules, its
    "calls flow" timer or the traffic it reads;
(c) quiet when idle: a note only when a finding, a server or a profile changed since the last one.
A fresh home, fixture ledger lines, a loopback mock for the one live call. Never a real server or model.
Run: python -m tests.test_steward_hotfix
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home, line  # noqa: E402

test, TESTS = new_registry()
KEY = "pc|qwen3.8:27b"
NO_READS = {"card_reader": None, "catalog_reader": None}


def _trained(n: int = 262144) -> dict:
    return {"pc": {"qwen3.8:27b": {"model": "qwen3.8:27b", "model_info": {"qwen35.context_length": n}}}}


def _found(h, **kw) -> list:
    from halo_harness.ollama_steward.rules import findings
    return findings(h.state, **{**NO_READS, "catalogs": _trained(), **kw})


def _rule(found, rule) -> dict:
    return next((f for f in found if f["rule"] == rule), {})


def _profile() -> dict:
    from halo_harness.ollama_steward.profiles import all_profiles
    return all_profiles().get(KEY) or {}


@test
def test_the_target_comes_from_the_cut_never_from_the_current_value(ctx: Ctx):
    from halo_harness.ollama_steward.profiles import set_field
    with Home() as h:
        h.calls(line(done_reason="length", prompt_eval_count=12000, eval_count=3000))
        p = (_rule(_found(h), "reply-cut").get("proposal") or {})
        ctx.check(f"twice the cut reply, rounded to 1,024: 6,144, got {p}", p.get("to") == 6144)
    with Home() as h:  # an 8,192 window: the rule before 3.3.13.1 had no window clamp under 16,384
        h.calls(line(done_reason="length", num_ctx_sent=8192, prompt_eval_count=5000, eval_count=3000))
        p = (_rule(_found(h), "reply-cut").get("proposal") or {})
        ctx.check(f"held to half the window in use: 4,096, got {p}", p.get("to") == 4096)
        set_field(KEY, "num_predict", 8192)
        found = _found(h)
        ctx.check(f"a reserve of 8,192 already covers the cut: no proposal, got {_rule(found, 'reply-cut')}",
                  not (_rule(found, "reply-cut").get("proposal")))
        loop = _rule(found, "reserve-loop")
        ctx.check(f"the loop is said: 8,192 -> 16,384 held, got {loop.get('finding')}",
                  "8,192 -> 16,384" in loop.get("finding", "") and loop.get("proposal") is None)


@test
def test_never_above_the_model_context_minus_the_prompt(ctx: Ctx):
    with Home() as h:
        h.calls(line(done_reason="length", num_ctx_sent=8192, prompt_eval_count=6000, eval_count=2100))
        f = _rule(_found(h, catalogs=_trained(8192)), "reply-cut")
        ctx.check(f"8,192 - 6,000 leaves 2,192: no reserve, the prompt compacts, got {f.get('finding')}",
                  f and f.get("proposal") is None and "the prompt has to compact" in f["finding"])
    with Home() as h:
        h.calls(line(done_reason="length", num_ctx_sent=16384, prompt_eval_count=6000, eval_count=2100))
        f = _rule(_found(h, catalogs=_trained(16384)), "reply-cut")
        ctx.check(f"16,384 - 6,000: the 5,120 target fits under 10,240, got {f.get('proposal')}",
                  (f.get("proposal") or {}).get("to") == 5120)


@test
def test_one_an_hour_and_never_twice_for_one_cut(ctx: Ctx):
    from halo_harness.ollama_steward import steward
    with Home() as h:
        cut = line(done_reason="length", prompt_eval_count=20000, eval_count=3000, ago=700)
        h.calls(cut, line(prompt_eval_count=23100, ago=690))
        f = _rule(_found(h), "cut-resent")
        ctx.check(f"the cut is named in the evidence, got {f.get('evidence')}",
                  f["evidence"]["numbers"].get("cut") == f"s1|{cut['at']}" and f.get("proposal"))
        steward._append(h.state, {"id": "c-old", "kind": "apply", "key": KEY, "field": "num_predict", "from": None,
                                  "to": 4096, "evidence": {"numbers": {"cut": f"s1|{cut['at']}"}},
                                  "_now": time.time() - 7200})
        f = _rule(_found(h), "cut-resent")
        ctx.check(f"the same cut two hours later: held, got {f.get('finding')}",
                  f.get("proposal") is None and "already proposed for this cut" in f["finding"])
    with Home() as h:
        h.calls(line(done_reason="length", prompt_eval_count=20000, eval_count=3000, ago=700, session="s9"),
                line(prompt_eval_count=23100, ago=690, session="s9"))
        steward._append(h.state, {"id": "c-new", "kind": "proposal", "key": KEY, "field": "num_predict", "from": None,
                                  "to": 4096, "evidence": {"numbers": {"session": "s9"}}, "_now": time.time() - 600})
        f = _rule(_found(h), "cut-resent")
        ctx.check(f"a proposal ten minutes ago for this session and model: held, got {f.get('finding')}",
                  f.get("proposal") is None and "less than an hour ago" in f["finding"])


@test
def test_the_runaway_stops_after_one_change(ctx: Ctx):
    """The owner's loop: auto mode, each pass a reply cut (a new session each time, as the steward's own ten-minute
    runs were), the next call carrying it. Before 3.3.13.1 the reserve doubled from its own value without end."""
    from halo_harness.ollama_steward import steward
    from halo_harness.ollama_steward.rules import findings
    from halo_harness.theme import set_config_value

    def passes(gap_s: float, n: int, *, sent: int = 32768, prompt: int = 3000, reply=None) -> list:
        seen, t0 = [], time.time()
        for i in range(n):
            r = reply or _profile().get("num_predict") or 1000  # cut at the reserve in force
            h.calls(line(done_reason="length", num_ctx_sent=sent, prompt_eval_count=prompt, eval_count=r,
                         session=f"run{i}", ago=60 - i),
                    line(num_ctx_sent=sent, prompt_eval_count=prompt + r, session=f"run{i}", ago=59 - i))
            now = t0 + i * gap_s
            found = findings(h.state, now=now, catalogs=_trained(32768), **NO_READS)
            steward.run(h.state, mode_name="auto", found=found, say=lambda _s: None, now=now)
            seen.append(_profile().get("num_predict"))
        return seen

    with Home() as h:
        seen = passes(700.0, 6)
        ctx.check(f"passes ten minutes apart: one change in the hour, got {seen}", seen == [4096] * 6)
    with Home() as h:
        seen = passes(4000.0, 6)
        ctx.check(f"passes an hour apart: once a pass, held at half the 32,768 window, got {seen}",
                  seen == [4096, 8192, 16384, 16384, 16384, 16384])
    with Home() as h:  # the owner's PC: a 4,096-token window, a profile the old loop had already blown up
        set_config_value("ollama.profiles", {KEY: {"num_predict": 2 ** 160, "by": "steward"}})
        h.calls(line(done_reason="length", num_ctx_sent=4096, prompt_eval_count=3000, eval_count=1096, ago=90))
        loop = _rule(findings(h.state, catalogs=_trained(32768), **NO_READS), "reserve-loop")
        ctx.check(f"a finding says the loop would have gone on, got {loop.get('finding')}",
                  "would have grown again" in loop.get("finding", "") and "49 digits" in loop.get("finding", ""))
        seen = passes(4000.0, 6, sent=4096, prompt=3000, reply=1096)
        applied = [r for r in steward.read_journal(h.state) if r.get("kind") == "apply" and r.get("field") == "num_predict"]
        ctx.check(f"no reserve change: the window is too small for one, got {len(applied)} applies",
                  not applied)
        ctx.check(f"the 2^160 value never grew, and the next profile write dropped it (a value is checked on write), "
                  f"got {[None if v is None else len(str(v)) for v in seen]}", all(v in (2 ** 160, None) for v in seen)
                  and seen[-1] is None)


@test
def test_the_stewards_own_calls_are_never_read_back(ctx: Ctx):
    from halo_harness.ollama_steward import job_state
    from halo_harness.ollama_steward.ledger import read_calls
    with Home() as h:
        h.calls(*[line(done_reason="length", prompt_eval_count=3000, eval_count=1000, session=f"st{i}", by="steward",
                       ago=30 - i) for i in range(4)])
        ctx.check("read_calls skips them", read_calls(h.state) == [] and len(read_calls(h.state, own=True)) == 4)
        ctx.check(f"no finding from them, got {[f['rule'] for f in _found(h)]}", _found(h) == [])
        ctx.check("the job's 'calls flow' does not see them", job_state.last_call_at(h.state) is None)
        h.calls(line(ago=500))
        t = job_state.last_call_at(h.state)
        ctx.check(f"a real call still counts, got {t}", t is not None and abs(time.time() - 500 - t) < 5)


@test
def test_the_live_call_tags_its_ledger_line(ctx: Ctx):
    import os
    from halo_harness.ollama_steward.agent import live_call
    from halo_harness.ollama_steward.ledger import read_calls
    from tests.helpers.mock_ollama import MockUpstream, _finish_chat

    def scn(handler, body):
        _finish_chat(handler, [{"message": {"role": "assistant", "content": "all quiet"}, "done": False},
                               {"message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop",
                                "prompt_eval_count": 900, "eval_count": 5, "eval_duration": 1000}])

    tags = {"models": [{"name": "steward-mock:1b", "model": "steward-mock:1b", "size": 1000, "digest": "sha256:ab",
                        "details": {"family": "qwen3", "parameter_size": "1B", "quantization_level": "Q4_0"}}]}
    show = {"steward-mock:1b": {"capabilities": ["completion"], "model_info": {"qwen3.context_length": 32768}}}
    mock = MockUpstream(scenarios={"steward-mock:1b": scn}, tags_response=tags, show_responses=show).start()
    url = f"http://127.0.0.1:{mock.port}"
    try:
        with Home(hosts=[{"name": "loop", "url": url}], extra={"ollama": {"auto_calibrate": False}}) as h:
            os.environ["OLLAMA_HOST"] = url
            live_call("ol:steward-mock:1b", "the guide", "the context", state_dir=h.state)
            own, seen = read_calls(h.state, own=True), read_calls(h.state)
    finally:
        mock.stop()
    ctx.check(f"one line, tagged by the steward, got {[x.get('by') for x in own]}",
              len(own) >= 1 and all(x.get("by") == "steward" for x in own))
    ctx.check("and not in the traffic the rules read", seen == [])


@test
def test_quiet_when_nothing_changed(ctx: Ctx):
    from halo_harness.ollama_steward import agent
    from halo_harness.ollama_steward.profiles import set_field
    from halo_harness.ollama_steward.rules import gather, run_rules
    with Home() as h:
        h.calls(line(done_reason="length", prompt_eval_count=12000, eval_count=3000))
        c = gather(h.state, catalogs=_trained(), **NO_READS)
        done = {"mode": "off", "findings": run_rules(c), "applied": [], "proposed": [], "rolled_back": []}
        go, why = agent.due(h.state, done, ctx=c, every_s=0)
        ctx.check(f"the first note is due, got {why}", go)
        row, _ = agent.write_note(h.state, c, done, model="ol:x", caller=lambda *a, **k: {"text": "a note", "local": True})
        ctx.check("the note keeps its signature", "sig" in (row or {}).get("data", {}))
        for f in done["findings"]:
            f["id"] += "-moved"  # a proposal number moved: the same finding
        go, why = agent.due(h.state, done, ctx=c, every_s=0)
        ctx.check(f"the same findings, servers, profiles: nothing, got {why}", not go and "nothing changed" in why)
        set_field(KEY, "keep_alive", "30m", by="user")
        go, why = agent.due(h.state, done, ctx=c, every_s=0)
        ctx.check(f"a profile changed: due, got {why}", go)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
