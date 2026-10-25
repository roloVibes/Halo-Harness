"""tests.test_turn_nudge -- Halo 3.2.2.0 R4: a reply with no tool call whose
last sentence promises work ("Now I'll edit X.") gets ONE user-role notice
("You ended your turn while saying you would do more. Continue.") and one
more model call; the transcript shows `↳ nudged: the reply promised work
and stopped`. Once per turn, never when the turn waits on the user, off
with `turn.nudge_promises: false`.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.turn_session import Calls, markers, new_session, request_text, text_step

test, TESTS = new_registry()


@test
def test_the_promise_patterns(ctx: Ctx):
    from halo_harness.agent.turn_marker import promises_work
    yes = ["I read the config. Now I'll edit the parser.", "Let me check the tests:", "I will run the suite next.",
           "Found it.\n\nNext, I update the docs.", "Going to rebuild the index.", "OK, I'll fix that now.",
           "Done with step one. Now I need to wire the CLI."]
    no = ["All tests pass.", "I'll edit it if you want?", "Let me know if you want more.", "I'll wait for your answer.",
          "I updated the file. Nothing else is needed.", "", "Shall I continue?", "I'll explain: the cache is stale. It works now."]
    for t in yes:
        ctx.check(f"promise: {t!r}", promises_work(t))
    for t in no:
        ctx.check(f"not a promise: {t!r}", not promises_work(t))


@test
def test_should_nudge_once_and_never_while_waiting(ctx: Ctx):
    from halo_harness.agent import turn_marker as tm
    s = SimpleNamespace()
    tm.reset_turn_state(s)
    ctx.check("a promise is nudged", tm.should_nudge(s, "Now I'll edit the file."))
    s._turn_nudged = True
    ctx.check("but only once per turn", not tm.should_nudge(s, "Now I'll edit the file."))
    tm.reset_turn_state(s)
    s._turn_waiting_on = "the plan"
    ctx.check("never when the turn waits on the user", not tm.should_nudge(s, "Let me know. I'll then start."))
    tm.reset_turn_state(s)
    ctx.check("a question to the user is waiting, not a promise", not tm.should_nudge(s, "I'll do A or B. Which one?"))


def _run(model: str, steps: list, *, nudge=None):
    from halo_harness import theme
    from tests.helpers.mock_openai import MockUpstream, SCENARIOS
    mock = MockUpstream().start()
    try:
        SCENARIOS[model.split("/", 1)[1]] = Calls(steps)
        session = new_session(mock=mock, model=model)
        if nudge is not None:
            theme.set_config_value("turn.nudge_promises", nudge)
        evs = list(session.turn("fix the parser"))
        return evs, list(mock.requests), session
    finally:
        mock.stop()


@test
def test_a_promise_is_nudged_once_and_the_turn_continues(ctx: Ctx):
    from halo_harness.agent.turn_marker import NUDGE_TEXT, NUDGED_LINE
    evs, reqs, session = _run("or:mock/r4-nudge-once", [text_step("I read it. Now I'll edit the parser."),
                                                         text_step("Edited the parser. Next is the docs pass.")])
    ctx.check(f"two model calls, got {len(reqs)}", len(reqs) == 2)
    ctx.check("the second call carries the notice", NUDGE_TEXT in request_text(reqs[1]))
    ms = markers(evs)
    ctx.check(f"a nudged line then the done line, got {[m.data['text'] for m in ms]}",
              [m.data["state"] for m in ms] == ["nudged", "done"] and ms[0].data["text"] == NUDGED_LINE)
    ctx.check("the notice is logged as a nudge, never a user prompt",
              any(n.get("kind") == "nudge" for n in session.log.nodes() if n.get("type") == "user"))
    ctx.check("no user bubble for the notice", not [e for e in evs if e.kind == "user_message" and NUDGE_TEXT in e.data.get("text", "")])


@test
def test_only_once_per_turn(ctx: Ctx):
    evs, reqs, _ = _run("or:mock/r4-nudge-twice", [text_step("Let me look at it."), text_step("Let me look again.")])
    ctx.check(f"one nudge only: two calls, got {len(reqs)}", len(reqs) == 2)
    ctx.check("one nudged line", len([m for m in markers(evs) if m.data["state"] == "nudged"]) == 1)


@test
def test_off_by_config(ctx: Ctx):
    evs, reqs, _ = _run("or:mock/r4-nudge-off", [text_step("Now I'll edit the parser."), text_step("x")], nudge=False)
    ctx.check(f"turn.nudge_promises false -> one call, got {len(reqs)}", len(reqs) == 1)
    ctx.check("no nudged line", not [m for m in markers(evs) if m.data["state"] == "nudged"])


@test
def test_never_after_waiting_on_you(ctx: Ctx):
    evs, reqs, _ = _run("or:mock/r4-nudge-wait", [text_step("I'll do A or B next. Which do you want?"), text_step("x")])
    ctx.check(f"a question ends the turn: one call, got {len(reqs)}", len(reqs) == 1)
    ms = markers(evs)
    ctx.check(f"the marker says waiting on you, got {[m.data['text'] for m in ms]}",
              len(ms) == 1 and ms[0].data["state"] == "waiting")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
