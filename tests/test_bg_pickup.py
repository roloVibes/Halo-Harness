"""tests.test_bg_pickup -- Halo 3.4.1.3: background work that finishes while the session is idle is shown at once
and, by default, picked up by the main agent in a turn of its own (agent/bg_pickup.py).

The owner (2026-11-13): "while you were away these tasks happened" came only once he sent a prompt. Pinned here,
with the repo's mock upstream and the session's own worker pump (no model call):
  * a background job and a background sub-agent each finishing while idle -> the `background` marker at once,
    then a self-started turn whose request carries the framed notice and no message of the person's;
  * two finishing close together -> one turn; text in the input box -> no turn until it is cleared or sent;
  * `background.self_turns` caps the turns in a row; `tell` shows it only; `wait` is the behaviour before;
  * a finish DURING a running turn behaves as before (the next message reads it).
Studio's row, the setting and the TUI's line: tests/test_bg_pickup_studio.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.bg_pickup_rig import FRAME_NEEDLE, NOT_HUMAN, Gated, Rig, general_purpose
from tests.helpers.turn_session import Calls, text_step, tool_step

test, TESTS = new_registry()


@test
def test_a_job_finishing_while_idle_shows_at_once_and_is_picked_up(ctx: Ctx):
    rig = Rig("bgp-job", ["hello there", "The docs build passed: nothing else to do."])
    try:
        rig.submit("hello")
        rig.turns_done(1)
        rig.finish_job("bash_7", "build the docs", output="docs built")
        mk = rig.markers(started=False)
        ctx.check("the marker is out at once, before any model call", len(mk) == 1 and len(rig.requests()) == 1)
        ctx.check(f"it names the job and says what happens next, got {mk[0].data['text']!r}",
                  "build the docs" in mk[0].data["text"] and "no message needed" in mk[0].data["text"])
        ctx.check("the session's status carries it", (rig.session._bg_done or {}).get("count") == 1)
        rig.turns_done(2)
        texts = rig.request_texts()
        ctx.check(f"one self-started turn: 2 main calls, got {len(texts)}", len(texts) == 2)
        ctx.check("its request carries the framed notice", FRAME_NEEDLE in texts[1] and NOT_HUMAN in texts[1]
                  and "bash_7" in texts[1] and "docs built" in texts[1])
        ctx.check("no message of the person's was added", len(rig.user_nodes()) == 1
                  and len(rig.evs("user_message")) == 1)
        ctx.check("the turn is logged as started by background work",
                  any(n.get("bg_turn") for n in rig.session.log.nodes() if n.get("type") == "meta"))
        ctx.check("and drawn as one", len(rig.markers(started=True)) == 1)
        rig.submit("thanks")
        rig.turns_done(3)
        ctx.check("the person's next message clears the Studio row", rig.session._bg_done is None)
    finally:
        rig.close()


@test
def test_a_sub_agent_finishing_while_idle_is_picked_up(ctx: Ctx):
    from tests.helpers.mock_openai import SCENARIOS
    child = Gated("background result ready")
    SCENARIOS["bgp-child"] = child
    rig = Rig("bgp-agent", [], agents=general_purpose(), first=Calls([
        tool_step("Task", {"description": "bg", "prompt": "work in the background", "subagent_type": "general-purpose",
                           "model": "or:mock/bgp-child", "run_in_background": True}),
        text_step("started it in the background"), text_step("The sub-agent is done: the result is ready.")]))
    try:
        rig.submit("run something in the background")
        rig.turns_done(1)
        ctx.check("nothing shown while it still runs", not rig.markers())
        child.gate.set()
        mk = rig.wait(lambda: rig.markers(started=False), "the background marker")
        ctx.check(f"the marker names the sub-agent, got {mk[0].data['text']!r}", "general-purpose" in mk[0].data["text"]
                  or "sub-agent" in mk[0].data["text"])
        rig.turns_done(2)
        texts = rig.request_texts()
        ctx.check(f"a self-started turn: 3 main calls, got {len(texts)}", len(texts) == 3)
        ctx.check("it reads the sub-agent's result in the frame", FRAME_NEEDLE in texts[2]
                  and "background result ready" in texts[2])
        ctx.check("one message of the person's", len(rig.user_nodes()) == 1)
    finally:
        child.gate.set()
        rig.close()


@test
def test_two_finishing_close_together_are_one_turn(ctx: Ctx):
    rig = Rig("bgp-two", ["hi", "Both jobs passed."], window_s=1.0)
    try:
        rig.submit("hello")
        rig.turns_done(1)
        rig.finish_job("bash_1", "lint")
        rig.finish_job("bash_2", "unit tests")
        ctx.check("one marker each, the second counting two", [m.data["count"] for m in rig.markers()] == [1, 2])
        rig.turns_done(2)
        rig.pumped(1)
        texts = rig.request_texts()
        ctx.check(f"one turn for both: 2 main calls, got {len(texts)}", len(texts) == 2)
        ctx.check("both in it", "bash_1" in texts[1] and "bash_2" in texts[1])
        ctx.check("one pickup command", rig.session._bg_pickup.pumps == 1)
    finally:
        rig.close()


@test
def test_text_in_the_input_box_holds_it_until_cleared(ctx: Ctx):
    from halo_harness.agent import bg_pickup
    rig = Rig("bgp-typing", ["hi", "The job passed."])
    try:
        rig.submit("hello")
        rig.turns_done(1)
        bg_pickup.set_typing(rig.session, True)
        rig.finish_job("bash_3", "slow job")
        ctx.check("still shown at once", len(rig.markers()) == 1)
        rig.pumped(1)
        ctx.check("held: no turn while the box holds text", rig.session._bg_pickup.held and len(rig.requests()) == 1)
        bg_pickup.set_typing(rig.session, False)
        rig.turns_done(2)
        ctx.check("cleared: the turn runs", len(rig.requests()) == 2 and FRAME_NEEDLE in rig.request_texts()[1])
    finally:
        rig.close()


@test
def test_text_in_the_input_box_then_sent_reads_it_with_the_message(ctx: Ctx):
    from halo_harness.agent import bg_pickup
    rig = Rig("bgp-sent", ["hi", "Answered, and the job passed."])
    try:
        rig.submit("hello")
        rig.turns_done(1)
        bg_pickup.set_typing(rig.session, True)
        rig.finish_job("bash_4", "slow job")
        rig.pumped(1)
        rig.submit("what next?")
        bg_pickup.set_typing(rig.session, False)  # the TUI clears its box once it sends
        rig.turns_done(2)
        rig.pumped(2)
        texts = rig.request_texts()
        ctx.check(f"no extra turn: 2 main calls, got {len(texts)}", len(texts) == 2)
        ctx.check("the message read it with the old frame", "bash_4" in texts[1] and FRAME_NEEDLE not in texts[1])
    finally:
        rig.close()


@test
def test_the_cap_on_turns_by_itself(ctx: Ctx):
    rig = Rig("bgp-cap", ["hi", "Read it.", "unused"], self_turns=1)
    try:
        rig.submit("hello")
        rig.turns_done(1)
        rig.finish_job("bash_5", "first")
        rig.turns_done(2)
        rig.finish_job("bash_6", "second")
        rig.pumped(2)
        ctx.check(f"capped at one: 2 main calls, got {len(rig.requests())}", len(rig.requests()) == 2)
        stop = [m for m in rig.markers() if m.data.get("stopped")]
        ctx.check("one line says why", len(stop) == 1 and "background.self_turns is 1" in stop[0].data["text"])
        rig.submit("go on")
        rig.turns_done(3)
        ctx.check("the person's message reads it and the count starts over", "bash_6" in rig.request_texts()[2]
                  and rig.session._bg_pickup.self_turns == 0)
    finally:
        rig.close()


@test
def test_tell_shows_it_only_and_wait_is_the_old_behaviour(ctx: Ctx):
    for how in ("tell", "wait"):
        rig = Rig(f"bgp-{how}", ["hi", "unused"], when_done=how)
        try:
            rig.submit("hello")
            rig.turns_done(1)
            rig.finish_job("bash_8", "a job")
            st = rig.session._bg_pickup
            ctx.check(f"{how}: no pickup armed", st.timer is None and rig.commands.empty())
            if how == "tell":
                mk = rig.markers()
                ctx.check("tell: shown at once", len(mk) == 1 and "with your next message" in mk[0].data["text"])
                ctx.check("tell: Studio's row", (rig.session._bg_done or {}).get("mode") == "tell")
            else:
                ctx.check("wait: nothing shown, nothing for Studio", not rig.markers() and rig.session._bg_done is None)
            ctx.check(f"{how}: still queued for the next message", len(rig.session._pending_job_notices) == 1)
        finally:
            rig.close()


@test
def test_a_finish_during_a_running_turn_behaves_as_before(ctx: Ctx):
    gated = Gated("done with your question")
    rig = Rig("bgp-busy", [], first=gated)
    try:
        rig.submit("a long question")
        rig.wait(lambda: rig.session.busy and rig.requests(), "the turn's model call")
        rig.finish_job("bash_9", "during the turn")
        ctx.check("no marker, no pickup armed", not rig.markers() and rig.session._bg_pickup.timer is None)
        gated.gate.set()
        rig.turns_done(1)
        ctx.check("still queued for the next message", len(rig.session._pending_job_notices) == 1)
        ctx.check("no self-started turn", len(rig.requests()) == 1 and rig.session._bg_pickup.pumps == 0)
    finally:
        gated.gate.set()
        rig.close()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
