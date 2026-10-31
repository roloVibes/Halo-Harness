"""tests.test_degrade -- Halo 3.3.6.0 R4 deliverable 6, the degradation ladder (agent/degrade.py, wired into
agent/loop.py), through the loop rig with a scripted fake Ollama on 127.0.0.1:0 (no model call, no real server):

1. each rung reached in order on a model that keeps answering empty: repair (the re-ask with the note), a smaller
   ask (the lean prompt, six tools at most), another local model (a probed one with tools, through the switch),
   which answers; each rung one line; the rungs on the ledger line (`ladder`);
2. one pass per turn: with nothing else to switch to and no policy, cloud is not taken (said why) and the ask rung
   ends the turn with its question -- no call after it;
3. the cloud rung is the escalation policy: `ask: true` refuses it (said), `ask: false` takes its `to`;
4. `tool_failures` between tool rounds takes the next rung that fits it (a smaller ask; repair is the repair round's);
5. `local.ladder: off` leaves R1's own line; a custom order is followed.
Run: python -m tests.test_degrade
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402

ensure_default_provider_credentials()
from tests.helpers.model_switch_rig import Rig, ledger_lines  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_dialect_loop import lines, reply, say, script  # noqa: E402

test, TESTS = new_registry()


def _probed(rig, model: str = "big:30b") -> None:
    from halo_harness.providers.battery_probes import PROBE_SET
    from halo_harness.providers.battery_profile import finish
    from halo_harness.providers.ollama_capability import save_profile
    save_profile(rig.state_dir, finish({
        "model": model, "host": "lan", "digest": "sha256:m00", "ollama_version": "0.40.13", "probe_set": PROBE_SET,
        "probed_at": time.time(), "tools": "yes", "system_role": "honoured", "instruction": "strict", "output": "json",
        "identifiers": "trusted", "reasoning": "none", "window": {"trained": 65536, "used": 32768, "verified": True},
        "speed": {"tok_s": 120.0}, "resident": {"co_resides_with": ["mid:14b"], "pivot_only": False}, "evidence": {}}))


def _set(key: str, value) -> None:
    from halo_harness.theme import set_config_value
    set_config_value(key, value)


def _rungs(evs) -> list:
    return [x for x in lines(evs) if x.startswith("rung ")]


@test
def test_each_rung_in_order(ctx: Ctx):
    with Rig() as rig:
        _probed(rig)
        mid = script([reply("")])
        big = script([reply("fine, from the big one")])
        rig.mock.scenarios.update({"mid:14b": mid, "big:30b": big})
        evs = rig.run(rig.session("ol:mid:14b@lan"), [say("list the files")])
        got = _rungs(evs)
        ctx.check(f"repair, a smaller ask, another local model, in order, got {got}", len(got) == 3
                  and got[0].startswith("rung 1: repair -- asked again") and got[1].startswith("rung 2: a smaller ask -- ")
                  and got[2] == "rung 3: another local model -- ol:big:30b@lan")
        bodies = mid.box["bodies"]
        ctx.check(f"the repair re-ask carries the note, got {bodies[2]['messages'][-1]}", len(bodies) == 4
                  and "Your last reply was empty" in bodies[2]["messages"][-1]["content"])
        ctx.check(f"the smaller ask sends six tools at most, got {len(bodies[3].get('tools') or [])} "
                  f"(before {len(bodies[0].get('tools') or [])})", 0 < len(bodies[3].get("tools") or []) <= 6
                  < len(bodies[0].get("tools") or []))
        ctx.check(f"another local model answered, got {big.box['turn']}", big.box["turn"] == 1
                  and any(e.kind == "turn_done" for e in evs))
        led = [x for x in ledger_lines(rig.state_dir) if x.get("kind") == "turn" and x.get("ladder")]
        ctx.check(f"the ledger line carries the rungs, got {[x['ladder'] for x in led][-1:]}",
                  led and [r["rung"] for r in led[-1]["ladder"]] == ["repair", "smaller-ask", "other-local"])


@test
def test_one_pass_then_the_ask(ctx: Ctx):
    with Rig() as rig:
        mid = script([reply("")])
        rig.mock.scenarios["mid:14b"] = mid
        evs = rig.run(rig.session("ol:mid:14b@lan"), [say("list the files")])
        got = _rungs(evs)
        ctx.check(f"every rung once, cloud not taken (no policy), then the ask, got {got}", len(got) == 5
                  and "none probed with tools here" in got[2] and got[3] == "rung 4: cloud -- not taken: no routing.escalation policy"
                  and got[4].startswith("rung 5: ask -- an empty reply on ol:mid:14b@lan; tried repair, smaller-ask."))
        ctx.check(f"no call after the ask (two, the repair, the smaller ask), got {mid.box['turn']}", mid.box["turn"] == 4)
        errs = [e for e in evs if e.kind == "error"]
        ctx.check("the ask is the turn's one error line", len(errs) == 1 and "What next" in str(errs[0].data))


@test
def test_the_cloud_rung_is_the_policy(ctx: Ctx):
    with Rig() as rig:
        _set("local.ladder", ["cloud", "ask"])
        _set("routing.escalation", {"to": "ol:big:30b@lan", "when": ["tool_failures"], "ask": True})
        rig.mock.scenarios["mid:14b"] = script([reply("")])
        evs = rig.run(rig.session("ol:mid:14b@lan"), [say("hi")])
        got = _rungs(evs)
        ctx.check(f"ask: true refuses it, said, then the ask, got {got}", len(got) == 2
                  and got[0].startswith("rung 1: cloud -- not taken: routing.escalation asks first") and got[1].startswith("rung 2: ask"))
    with Rig() as rig:
        _set("local.ladder", ["cloud", "ask"])
        _set("routing.escalation", {"to": "ol:big:30b@lan", "when": ["tool_failures"], "ask": False})
        big = script([reply("from the policy's model")])
        rig.mock.scenarios.update({"mid:14b": script([reply("")]), "big:30b": big})
        s = rig.session("ol:mid:14b@lan")
        evs = rig.run(s, [say("hi")])
        ctx.check(f"ask: false takes its `to`, got {_rungs(evs)}", _rungs(evs) == ["rung 1: cloud -- ol:big:30b@lan (routing.escalation)"]
                  and big.box["turn"] == 1 and s.model_ref.raw == "ol:big:30b@lan")


@test
def test_tool_failures_between_rounds(ctx: Ctx):
    with Rig() as rig:
        two = {"message": {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "Read", "arguments": {"file_path": "a.txt"}}},
            {"function": {"name": "Read", "arguments": {"file_path": "b.txt"}}}]}, "done": True, "done_reason": "stop",
            "prompt_eval_count": 50, "eval_count": 30}
        mid = script([two, reply("done")])
        rig.mock.scenarios["mid:14b"] = mid
        evs = rig.run(rig.session("ol:mid:14b@lan"), [say("read both")])
        got = _rungs(evs)
        ctx.check(f"two failed calls: the next rung that fits (a smaller ask), got {got}", got == ["rung 2: a smaller ask -- the lean prompt"])
        ctx.check(f"the next call is the smaller ask, got {len(mid.box['bodies'][1].get('tools') or [])} tools",
                  0 < len(mid.box["bodies"][1].get("tools") or []) <= 6)


@test
def test_off_and_a_custom_order(ctx: Ctx):
    with Rig() as rig:
        _set("local.ladder", "off")
        rig.mock.scenarios["mid:14b"] = script([reply("")])
        evs = rig.run(rig.session("ol:mid:14b@lan"), [say("hi")])
        ctx.check(f"off: no rung, R1's line, got {lines(evs)}", not _rungs(evs)
                  and any("returned an empty reply twice" in x for x in lines(evs)))
    with Rig() as rig:
        _set("local.ladder", ["ask"])
        mid = script([reply("")])
        rig.mock.scenarios["mid:14b"] = mid
        evs = rig.run(rig.session("ol:mid:14b@lan"), [say("hi")])
        ctx.check(f"a custom order: the ask first, got {_rungs(evs)}", len(_rungs(evs)) == 1
                  and _rungs(evs)[0].startswith("rung 1: ask -- ") and "tried nothing else" in _rungs(evs)[0]
                  and mid.box["turn"] == 2)
    from halo_harness.agent.degrade import RUNGS, rungs
    _set("local.ladder", ["smaller-ask", "bogus", "ask"])
    ctx.check(f"an unknown rung is dropped, got {rungs()}", rungs() == ["smaller-ask", "ask"])
    _set("local.ladder", None)
    ctx.check("unset: the default order", rungs() == list(RUNGS))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
