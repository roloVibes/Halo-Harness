"""tests.test_dialect_loop -- Halo 3.3.6.0 R4 deliverable 2, the dialect record applied before every call, through
the loop rig (tests/helpers/model_switch_rig.py: a real Session over a fake Ollama on 127.0.0.1:0; no model call):

1. placement: a record set to user-turn on an unprobed model puts Halo's instructions in the first user message;
2. the stop quirks go out as `options.stop`; the ledger line carries the dialect in force;
3. the JSON repair loop: a tool call with broken arguments is asked again with the parse error, at most `attempts`
   times (two attempts repair it here; off asks none);
4. the loop guard: the same 40-token span three times stops the stream with one line, the repeats cut off the reply,
   the ledger line marks `loop`; a guard that is off only marks it, and the ledger's rule then turns it on;
5. the tool budget: tools_max 3 -> three tools and the rest named in one line of the system prompt; tools_max 0 ->
   none; the long tail ranked by its relevance to the task (prompt_lean.cap_tools).
Run: python -m tests.test_dialect_loop
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402

ensure_default_provider_credentials()
from tests.helpers.mock_ollama import _finish_chat  # noqa: E402
from tests.helpers.model_switch_rig import Rig, ledger_lines  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def say(text):
    from halo_harness import events
    return events.Command("user_input", {"text": text})


def lines(evs) -> list:
    return [(e.data.get("text") or e.data.get("message") or "").replace("↳ ", "") for e in evs
            if e.kind in ("turn_marker", "error")]


def reply(content="", *, tool=None, done="stop") -> dict:
    msg = {"role": "assistant", "content": content}
    if tool:
        msg["tool_calls"] = [{"function": {"name": tool[0], "arguments": tool[1]}}]
    return {"message": msg, "done": True, "done_reason": done, "prompt_eval_count": 50, "eval_count": 30,
            "load_duration": 100_000, "eval_duration": 30_000_000, "prompt_eval_duration": 40_000_000}


def script(turns: list, repairs: "list | None" = None):
    """A scenario: turn calls answered from `turns` in order, repair calls (a `format` in the body) from `repairs`."""
    box = {"turn": 0, "repair": 0, "bodies": []}

    def fn(h, body):
        box["bodies"].append(body)
        kind = "repair" if body.get("format") else "turn"
        steps = (repairs or [reply("{}")]) if kind == "repair" else turns
        i = min(box[kind], len(steps) - 1)
        box[kind] += 1
        _finish_chat(h, steps[i] if isinstance(steps[i], list) else [steps[i]])
    fn.box = box
    return fn


def dialect(host: str, model: str, **fields) -> None:
    from halo_harness.providers.dialect import set_fields
    _stored, bad = set_fields(host, model, fields, by="user")
    assert not bad, bad


@test
def test_placement_and_the_stop_quirks(ctx: Ctx):
    with Rig() as rig:
        dialect("lan", "mid:14b", instruction_placement="user-turn", stop_quirks=["<|im_end|>"])
        scn = script([reply("fine")])
        rig.mock.scenarios["mid:14b"] = scn
        evs = rig.run(rig.session("ol:mid:14b@lan"), [say("hello there")])
        body = scn.box["bodies"][0]
        msgs = body["messages"]
        sys_msg = next((m for m in msgs if m["role"] == "system"), {})
        first_user = next(m for m in msgs if m["role"] == "user")
        ctx.check(f"the system message keeps one pointer line, got {str(sys_msg.get('content'))[:120]!r}",
                  "start of the first user message" in str(sys_msg.get("content")))
        ctx.check("Halo's instructions ride the first user message", len(str(first_user["content"])) > 500)
        ctx.check(f"the line says so, got {lines(evs)}", any("ignores the system role" in x for x in lines(evs)))
        ctx.check(f"the stop quirk goes out as options.stop, got {body['options'].get('stop')}",
                  "<|im_end|>" in (body["options"].get("stop") or []))
        led = ledger_lines(rig.state_dir)[-1]
        ctx.check(f"the ledger line carries the dialect in force, got {led.get('dialect_record')}",
                  (led.get("dialect_record") or {}).get("placement") == "user-turn"
                  and led["dialect_record"]["stop"] == ["<|im_end|>"] and led["dialect"] == "ollama")


@test
def test_the_json_repair_loop(ctx: Ctx):
    for attempts, want_repairs, repaired in ((2, 2, True), (1, 1, False), (0, 0, False)):
        with Rig() as rig:
            notes = Path(rig.fh["proj"]) / "notes.txt"
            notes.write_text("hi", encoding="utf-8")
            good = json.dumps({"file_path": notes.as_posix()})
            dialect("lan", "mid:14b", json_repair={"on": attempts > 0, "attempts": max(attempts, 1) if attempts else 1})
            scn = script([reply(tool=("Read", good[:-1])), reply("done")], repairs=[reply("still not json"), reply(good)])
            rig.mock.scenarios["mid:14b"] = scn
            s = rig.session("ol:mid:14b@lan")
            rig.run(s, [say("read notes.txt")])
            n = scn.box["repair"]
            errs = [nd for nd in s.log.nodes() if nd.get("type") == "tool_result" and nd.get("is_error")]
            ctx.check(f"attempts {attempts}: {want_repairs} repair calls, repaired {repaired}, got {n} calls, "
                      f"{len(errs)} errors", n == want_repairs and (not errs) == repaired)
            if attempts == 2:
                second = [b for b in scn.box["bodies"] if b.get("format")][1]
                ctx.check("the second attempt carries the first one's parse error",
                          "repair attempt 1 failed too" in json.dumps(second["messages"]))


def _looping() -> list:
    span = " ".join(f"step{i}" for i in range(40)) + " "
    text = "Here is the plan. " + span * 5
    chunks = [text[i:i + 30] for i in range(0, len(text), 30)]
    out = [{"message": {"role": "assistant", "content": c}, "done": False} for c in chunks]
    return out + [{"message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop",
                   "prompt_eval_count": 50, "eval_count": 400, "eval_duration": 1_000_000_000}]


@test
def test_the_loop_guard(ctx: Ctx):
    with Rig() as rig:
        dialect("lan", "mid:14b", loop_guard={"on": True, "window": 40})
        rig.mock.scenarios["mid:14b"] = script([_looping()])
        s = rig.session("ol:mid:14b@lan")
        evs = rig.run(s, [say("plan it")])
        said = [x for x in lines(evs) if "started repeating; stopped" in x]
        ctx.check(f"one line, got {lines(evs)}", len(said) == 1 and said[0].startswith("ol:mid:14b@lan started repeating"))
        texts = [b.get("text") for nd in s.log.nodes() if nd.get("type") == "assistant" for b in nd["content"]
                 if b.get("type") == "text"]
        reps = texts[-1].count("step0 ") if texts else 0
        ctx.check(f"the repeats cut off the reply (at most two spans kept), got {reps}", texts and reps <= 2)
        led = [x for x in ledger_lines(rig.state_dir) if x.get("kind") == "turn"]
        ctx.check(f"the ledger line marks the loop, got {[x.get('loop') for x in led]}", led and led[-1].get("loop") is True)
    with Rig() as rig:
        rig.mock.scenarios["mid:14b"] = script([_looping()])
        evs = rig.run(rig.session("ol:mid:14b@lan"), [say("plan it")])
        from halo_harness.providers.dialect import record
        rec = record("lan", "mid:14b", state_dir=rig.state_dir)
        ctx.check(f"a guard that is off lets it finish, marks it, and the ledger's rule turns it on, got {lines(evs)} "
                  f"{rec['loop_guard']} {rec['from']['loop_guard']}", not any("stopped" in x for x in lines(evs))
                  and any("the loop guard is on" in x for x in lines(evs)) and rec["loop_guard"]["on"] is True
                  and rec["from"]["loop_guard"] == "ledger")


@test
def test_the_tool_budget(ctx: Ctx):
    with Rig() as rig:
        dialect("lan", "mid:14b", tools_max=3)
        scn = script([reply("ok")])
        rig.mock.scenarios["mid:14b"] = scn
        rig.run(rig.session("ol:mid:14b@lan"), [say("hello")])
        body = scn.box["bodies"][0]
        system = next((m["content"] for m in body["messages"] if m["role"] == "system"), "")
        ctx.check(f"tools_max 3: three tools sent, got {len(body.get('tools') or [])}", len(body.get("tools") or []) == 3)
        ctx.check("the rest named in one line of the system prompt", "Other tools you can call by name" in system)
    with Rig() as rig:
        dialect("lan", "mid:14b", tools_max=0)
        scn = script([reply("ok")])
        rig.mock.scenarios["mid:14b"] = scn
        rig.run(rig.session("ol:mid:14b@lan"), [say("hello")])
        ctx.check(f"tools_max 0: no tools, got {len(scn.box['bodies'][0].get('tools') or [])}",
                  not scn.box["bodies"][0].get("tools"))
    from types import SimpleNamespace
    from halo_harness.agent.prompt_lean import cap_tools
    s = SimpleNamespace(model_ref=None, _lean_profile_tools_max=1, model_profile=None)
    tools = [{"name": "zz_deploy", "description": "deploy a kubernetes cluster"},
             {"name": "zz_weather", "description": "the weather forecast for a city"}]
    kept, dropped = cap_tools(s, tools, "what is the weather in Paris tomorrow")
    ctx.check(f"the long tail ranked by relevance to the task, got {[t['name'] for t in kept]}",
              [t["name"] for t in kept] == ["zz_weather"] and dropped == 1)
    kept, _d = cap_tools(s, tools, "")
    ctx.check("no task: the catalog's order", [t["name"] for t in kept] == ["zz_deploy"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
