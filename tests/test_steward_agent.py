"""tests.test_steward_agent -- Halo 3.3.4.0 R4: the steward's model
(ollama_steward/agent.py, agent_prompt.py, agent_proposals.py):

- the prompt's guide is built from the knowledge files (every symptoms.md
  kind, the "never a smaller window for an outgrown conversation" rule, no
  source tags) and stays under 2,000 tokens; the context names the findings,
  the changes and the machines;
- a fake model answers a note and a proposals block: the note lines land in
  steward.jsonl (the first is the status line, the cost line last); a bounded
  proposal applies in `auto`, becomes a proposal line in `review` (and
  `halo ollama steward apply <id>` takes it), is only reported in `off`; an
  out-of-bounds one (above the cap, a smaller window for a model whose
  prompts were trimmed, an unknown key, not a profile field) is dropped with
  a `say`;
- no call when nothing is new, and at most one per note_every_s;
- the default model: ollama.steward.model, else a local compactionModel, else
  the smallest local model, else none; the cost line;
- the live call (`live_call`: the pong's session builder and one
  `call_small_model`) against a fake Ollama on 127.0.0.1:0.
Never a real server or a real model.
Run: python -m tests.test_steward_agent
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
NO_READS = {"card_reader": None, "catalog_reader": None}
KEY = "pc|qwen3.8:27b"
NOTE = ("The 27B on pc ran out of room: its prompts reached 31k of the 32k window it was sent.\n"
        "The steward raised the window to 65,536, the most this card measured.\n")


def _answer(*props) -> str:
    import json
    return NOTE + ("```proposals\n" + json.dumps(list(props)) + "\n```\n" if props else "")


def _ctx(h, trims: bool = False):
    from halo_harness.ollama_steward.rules import gather, run_rules
    h.cap("qwen3.8:27b", 65536)
    h.calls(*[line(prompt_eval_count=31000, ago=300 - i, session=None, trimmed=trims) for i in range(5)])
    ctx = gather(h.state, **NO_READS)
    found = run_rules(ctx)
    return ctx, {"mode": "auto", "findings": found, "applied": [], "proposed": [], "rolled_back": [], "skipped": []}


def _write(h, ctx, done, *props, mode="auto"):
    from halo_harness.ollama_steward import agent
    said: list = []
    row, outcomes = agent.write_note(h.state, ctx, {**done, "mode": mode}, model="ol:qwen3.5:9b",
                                     caller=lambda *a, **k: {"text": _answer(*props), "local": True}, say=said.append)
    return row, outcomes, said


def _profile(key=KEY):
    from halo_harness.ollama_steward.profiles import all_profiles
    return all_profiles().get(key) or {}


@test
def test_the_guide_comes_from_the_knowledge_under_the_budget(ctx: Ctx):
    from halo_harness.ollama_steward.agent_prompt import GUIDE_TOKENS, guide, tokens
    from halo_harness.ollama_steward.explain import symptom_rows
    g = guide()
    ctx.check(f"under {GUIDE_TOKENS} tokens, got {tokens(g)}", tokens(g) <= GUIDE_TOKENS)
    missing = [k for k in symptom_rows() if f"- {k}" not in g]
    ctx.check(f"every symptoms.md kind is in it, missing {missing}", not missing)
    ctx.check("the outgrown-conversation rule, in the knowledge's words",
              "a smaller window is the answer to a spill, never to an outgrown conversation" in g)
    ctx.check("no source tags", "[S" not in g)
    ctx.check("the note's shape and the proposals block are asked for", "at most 6 lines" in g and "```proposals" in g)
    small = guide(budget=1200)
    ctx.check(f"a smaller budget shortens the cells, got {tokens(small)}", tokens(small) < tokens(g))


@test
def test_the_context_names_the_findings_the_changes_and_the_machines(ctx: Ctx):
    from halo_harness.ollama_steward.agent_prompt import context
    with Home() as h:
        c, done = _ctx(h)
        done["applied"] = [{"say": "steward: num_ctx 65536 for qwen3.8:27b on pc (raised)"}]
        text = context(c, done)
    ctx.check("the finding line", "window-small" in text and "qwen3.8:27b" in text)
    ctx.check("the change this run made", "steward: num_ctx 65536" in text)
    ctx.check("the machines that called and the rollups", "Machines that called: this machine 5" in text
              and "5 calls" in text)


@test
def test_a_note_lands_and_a_bounded_proposal_applies_in_auto(ctx: Ctx):
    from halo_harness.ollama_steward import notes
    with Home() as h:
        c, done = _ctx(h)
        row, outcomes, said = _write(h, c, done, {"key": KEY, "field": "num_predict", "to": 4096,
                                                  "why": "room for the reply"})
        ctx.check(f"the note's first line is its say, got {row and row['say']!r}",
                  row and row["say"].startswith("The 27B on pc ran out of room"))
        ctx.check(f"the note lines and the cost last, got {row and row['lines']}",
                  row and len(row["lines"]) == 3 and row["lines"][-1].endswith("local, free)"))
        ctx.check("the note is in steward.jsonl", notes.latest(h.state)["id"] == row["id"])
        ctx.check(f"the proposal applied, got {outcomes}", outcomes and outcomes[0]["kind"] == "apply")
        ctx.check(f"the profile has it, got {_profile()}", _profile().get("num_predict") == 4096)
        ctx.check(f"the change said its line, got {said}", any(s.startswith("steward: num_predict 4096") for s in said))
        ctx.check("a change raises the attention flag", row and row["attention"])


@test
def test_review_makes_a_proposal_and_off_only_reports(ctx: Ctx):
    from halo_harness.ollama_steward import steward
    with Home() as h:
        c, done = _ctx(h)
        _row, outcomes, said = _write(h, c, done, {"key": KEY, "field": "num_predict", "to": 4096, "why": "room"},
                                      mode="review")
        ctx.check(f"review: a proposal line, got {outcomes}", outcomes and outcomes[0]["kind"] == "proposal")
        ctx.check("nothing applied yet", "num_predict" not in _profile())
        ctx.check(f"it says the apply command, got {said}", any("halo ollama steward apply agent-" in s for s in said))
        applied, why = steward.apply_by_id(h.state, outcomes[0]["id"], **NO_READS)
        ctx.check(f"`apply <id>` takes it, got {why!r}", applied is not None and _profile().get("num_predict") == 4096)
    with Home() as h:
        c, done = _ctx(h)
        _row, outcomes, _said = _write(h, c, done, {"key": KEY, "field": "num_predict", "to": 4096, "why": "room"},
                                       mode="off")
        ctx.check(f"off: reported only, got {outcomes}", outcomes and outcomes[0]["kind"] == "reported"
                  and "num_predict" not in _profile())


@test
def test_an_out_of_bounds_proposal_is_dropped_with_a_say(ctx: Ctx):
    with Home() as h:
        c, done = _ctx(h, trims=True)
        _row, outcomes, said = _write(h, c, done,
                                      {"key": KEY, "field": "num_ctx", "to": 131072, "why": "more"},
                                      {"key": KEY, "field": "num_ctx", "to": 16384, "why": "less memory"},
                                      {"key": "pc|nothing:1b", "field": "num_ctx", "to": 8192, "why": "x"},
                                      {"key": KEY, "field": "temperature", "to": 0.2, "why": "x"})
        kinds = [o["kind"] for o in outcomes]
        ctx.check(f"all four dropped, got {kinds}", kinds == ["dropped"] * 4)
        reasons = " | ".join(o["reason"] for o in outcomes)
        ctx.check(f"above the measured cap, got {reasons}", "above the learned cap (65536)" in reasons)
        ctx.check("a smaller window for an outgrown conversation", "outgrew" in reasons)
        ctx.check("an unknown host and model, a field that is not a profile's", "no host and model" in reasons
                  and "not a profile field" in reasons)
        ctx.check(f"each drop is said, got {said}", sum(s.startswith("steward model's proposal dropped") for s in said) == 4)
        ctx.check("no profile written", not _profile())


@test
def test_no_call_when_nothing_is_new_and_at_most_one_per_note_every_s(ctx: Ctx):
    from halo_harness.ollama_steward.job import StewardJob
    calls: list = []

    def caller(model, system, user, state_dir=None):
        calls.append(user)
        return {"text": NOTE, "local": True}

    with Home(extra={"ollama": {"steward": {"apply": "off"}}}) as h:
        job = StewardJob(h.state, readers=NO_READS, watch=False, model=("ol:qwen3.5:9b", "given"), caller=caller)
        t0 = time.time()
        job.tick(t0)
        ctx.check("no calls in the ledger: no run, no call", not calls)
        h.cap("qwen3.8:27b", 65536)
        h.calls(*[line(prompt_eval_count=31000, ago=60 - i, session=None) for i in range(5)])
        job.tick(t0)
        ctx.check(f"a new finding: one call, got {len(calls)}", len(calls) == 1)
        job.tick(t0 + 900)
        ctx.check(f"the same findings later: no call, got {len(calls)}", len(calls) == 1)
        job.on_event({"kind": "cpu-spill", "severity": "warn", "notify": True})
        job.tick(t0 + 901)
        ctx.check(f"a server alert after note_every_s: a call, got {len(calls)}", len(calls) == 2)
        job.on_event({"kind": "http-500", "severity": "error", "notify": True})
        job.tick(t0 + 950)
        ctx.check(f"another alert inside note_every_s (600 s): no call, got {len(calls)}", len(calls) == 2)


@test
def test_the_default_model_and_the_cost_line(ctx: Ctx):
    from halo_harness.ollama_steward.agent import NO_MODEL, choose_model, cost_line
    local = [("ol:qwen3.8:27b", 16 * 2 ** 30), ("ol:qwen3.5:9b", 6 * 2 ** 30)]
    ctx.check("ollama.steward.model wins, a cloud one too",
              choose_model(configured="or:vendor/cheap", compaction="ol:x", local=local)[0] == "or:vendor/cheap")
    ctx.check("then a local compactionModel",
              choose_model(configured="", compaction="ol:qwen3.5:4b", local=local) == ("ol:qwen3.5:4b", "compactionModel"))
    got = choose_model(configured="", compaction="or:vendor/model", local=local)
    ctx.check(f"a cloud compactionModel is passed over for the smallest local model, got {got}",
              got[0] == "ol:qwen3.5:9b" and "smallest local" in got[1])
    ctx.check("none: the rules run alone", choose_model(configured="", compaction="", local=[]) == (None, NO_MODEL))
    with Home(extra={"ollama": {"steward": {"model": "ol:qwen3.5:9b"}}}):
        ctx.check("read from config.json", choose_model(local=[])[0] == "ol:qwen3.5:9b")
    ctx.check("a local model is free", cost_line({"local": True, "input_tokens": 900}, "ol:qwen3.5:9b") == "local, free")
    ctx.check("a priced cloud call says its tokens and dollars",
              cost_line({"input_tokens": 1200, "output_tokens": 80, "cost_usd": 0.0012}, "or:vendor/cheap")
              == "1200 in / 80 out tokens, $0.0012")
    ctx.check("an unpriced one says so", cost_line({"input_tokens": 5, "output_tokens": 2}, "or:x").endswith("no price known"))


@test
def test_the_live_call_runs_one_turn_on_a_fake_ollama(ctx: Ctx):
    import os
    from halo_harness.ollama_steward.agent import live_call, parse
    from tests.helpers.mock_ollama import MockUpstream, _finish_chat

    def scn(handler, body):
        _finish_chat(handler, [{"message": {"role": "assistant", "content": _answer(
            {"key": KEY, "field": "num_predict", "to": 4096, "why": "room"})}, "done": False},
            {"message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop",
             "prompt_eval_count": 1500, "eval_count": 40, "eval_duration": 1000, "prompt_eval_duration": 1000}])

    tags = {"models": [{"name": "steward-mock:1b", "model": "steward-mock:1b", "size": 1000, "digest": "sha256:aa",
                        "details": {"family": "qwen3", "parameter_size": "1B", "quantization_level": "Q4_0"}}]}
    show = {"steward-mock:1b": {"capabilities": ["completion"], "details": {"family": "qwen3"},
                                "model_info": {"qwen3.context_length": 32768}}}
    mock = MockUpstream(scenarios={"steward-mock:1b": scn}, tags_response=tags, show_responses=show).start()
    url = f"http://127.0.0.1:{mock.port}"
    try:
        with Home(hosts=[{"name": "loop", "url": url}], extra={"ollama": {"auto_calibrate": False}}) as h:
            os.environ["OLLAMA_HOST"] = url
            reply = live_call("ol:steward-mock:1b", "the guide", "the context", state_dir=h.state)
    finally:
        mock.stop()
    lines, props, why = parse(reply.get("text"))
    ctx.check(f"the note came back, got {lines}", lines and lines[0].startswith("The 27B on pc ran out of room"))
    ctx.check(f"with its proposals block, got {props} {why!r}", props and props[0]["field"] == "num_predict")
    ctx.check(f"the usage and local, got {reply}", reply.get("input_tokens") == 1500 and reply.get("output_tokens") == 40
              and reply.get("local") is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
