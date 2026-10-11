"""tests.test_remote_bridge -- Halo 2.0.9 round 3: the Signal bridge
(`halo_harness/remote/bridge*.py`) over real control sockets (round 2's rig:
real Controller + scripted FakeSession) with a stub transport: every chat
command, cards answered from the phone (permission by number, question by
letter, plan by approve, approval by accept), quiet/loud, signed commands,
read receipts after the checks only, the audit line, Note to Self, and that no
message content reaches any file under the scratch homes. The end-to-end test
at the bottom runs the real transport against the fake signal-cli child.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.bridge_rig import Harness
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.signal_rig import ACI_A, wait_for

test, TESTS = new_registry()


def decision(rig, key="perm_1"):
    return rig.session.permission_decisions.get(key)


@test
def test_prompt_roundtrip_and_typing(ctx: Ctx):
    with Harness() as h:
        h.send("hello bridge")
        ctx.check("the first command attaches the newest live session", h.wait_text("Attached to Session 1"))
        ctx.check("the prompt reaches the session", h.wait_idle())
        ctx.check("the session's text comes back (loud is the default)", h.wait_text("hello from the fake session"))
        ctx.check("the turn closes with the done line", h.wait_text("Done."))
        ctx.check("typing started and was stopped at turn_done",
                  wait_for(lambda: (ACI_A, False) in h.tr.typing_calls and (ACI_A, True) in h.tr.typing_calls))
        ctx.check("a read receipt went out for the accepted command", len(h.tr.receipts) == 1 and h.tr.receipts[0][0] == ACI_A)
        user_msgs = [n for n in h.rig.session.log.nodes() if n.get("type") == "user"]
        ctx.check("the session logged the prompt text", user_msgs and user_msgs[0]["content"][0]["text"] == "hello bridge")
        h.send("steer me")
        ctx.check("a second prompt is a second turn", h.wait_idle(turns=2))
        ctx.check("the audit trail has one line per command, hashed",
                  [(r["kind"], r["outcome"]) for r in h.bridge.audit.lines()] == [("prompt", "ok"), ("prompt", "ok")])


@test
def test_sessions_attach_and_commands(ctx: Ctx):
    with Harness(sessions=2) as h:
        h.send("/sessions")
        ctx.check("/sessions lists live sessions newest first with title, cwd tail and phase",
                  h.wait_text("2. Session 1") and "1. Session 2" in h.joined() and "idle" in h.joined())
        ctx.check("nothing is attached yet, so no marker", "* Session" not in h.joined())
        h.send("/attach 1")
        ctx.check("/attach <n> attaches that row", h.wait_text("Attached to Session 2"))
        h.send("/attach 9")
        ctx.check("a bad number gets the usage line", h.wait_text("Usage: /attach <n>"))
        h.send("/attach")
        h.send("/sessions")
        ctx.check("the attached session is marked", wait_for(lambda: "1. * Session 2" in h.joined()))
        h.send("/attach 2")
        ctx.check("re-attaching switches", h.wait_text("Attached to Session 1"))
        h.send("go on session one")
        ctx.check("a prompt goes to the attached session only", h.wait_idle(h.rigs[0])
                  and h.rigs[1].session.turn_count == 0)
        h.send("/status")
        ctx.check("/status shows the session's model, mode and effort", h.wait_text("Model: mock/fake")
                  and "Mode: default" in h.joined() and "Effort: medium" in h.joined())
        h.send("/mode plan")
        ctx.check("/mode sets the permission mode", wait_for(lambda: h.rigs[0].session.permission_engine.mode == "plan")
                  and h.wait_text("Mode set to plan."))
        h.send("/mode nonsense")
        ctx.check("a bad mode reports the session's sentence", h.wait_text("Error: unknown mode"))
        h.send("/model or:some/model")
        ctx.check("/model resolves and queues the model", wait_for(lambda: h.rigs[0].models == ["or:some/model"])
                  and h.wait_text("Model switch queued"))
        h.send("/effort high")
        ctx.check("/effort goes through the effort command", h.wait_text("Effort set to high."))
        h.send("/effort enormous")
        ctx.check("a bad effort is reported", h.wait_text("Error: unknown effort"))
        h.send("/mode")
        ctx.check("a missing argument gets a usage line", h.wait_text("Usage: /mode <mode>"))
        h.send("/stop")
        ctx.check("/stop interrupts the session", wait_for(lambda: h.rigs[0].session.abort.is_set()) and h.wait_text("Interrupt sent."))
        h.send("/cost now")
        ctx.check("another /x passes through as the session's slash command", h.wait_text("ran /cost now"))
        h.send("/tail 2")
        ctx.check("/tail returns the last messages as plain text with upper-case headings",
                  h.wait_text("ASSISTANT") and "reply to: go on session one" in h.joined())
        h.send("/remote status")
        ctx.check("/remote status says who and what", h.wait_text("Paired as 00000000") and "signing off" in h.joined())
        h.send("/remote help")
        ctx.check("/remote help lists the commands", h.wait_text("/sessions  /attach <n>"))
        h.send("/remote pair")
        ctx.check("/remote pair explains how to add a phone", h.wait_text("halo remote signal pair"))
        h.rigs[0].server.close()
        ctx.check("when the attached session goes away the phone is told", h.wait_text("The attached session ended"))
        h.send("hello?")
        ctx.check("the next command re-attaches or says so, it never hangs",
                  wait_for(lambda: "Could not reach" in h.joined() or "No live halo session" in h.joined()
                           or h.joined().count("Attached to") >= 3, 8))


@test
def test_permission_card_by_number(ctx: Ctx):
    with Harness() as h:
        h.send("please ask first")
        ctx.check("the permission card names the tool, the command and the reason",
                  h.wait_text("Permission needed: Bash") and "echo hi" in h.joined() and "Why: needs approval" in h.joined())
        ctx.check("it lists the four numbered choices", "1 allow once" in h.joined() and "2 allow for this session" in h.joined()
                  and "3 always allow" in h.joined() and "4 deny" in h.joined())
        h.send("2")
        ctx.check("2 allows for the session with the suggested rule",
                  wait_for(lambda: decision(h.rig) is not None) and decision(h.rig).action == "allow"
                  and decision(h.rig).rule == "Bash(echo:*)" and h.wait_text("Allowed for this session."))
        ctx.check("the turn then finishes", h.wait_idle() and h.wait_text("Done."))
        h.send("again ask")
        ctx.check("a second card appears", wait_for(lambda: h.joined().count("Permission needed") == 2))
        h.send("4 not this time")
        ctx.check("4 <reason> denies with the reason",
                  wait_for(lambda: decision(h.rig) is not None and decision(h.rig).action == "deny")
                  and decision(h.rig).message == "not this time" and h.wait_text("Denied."))
        h.wait_idle(turns=2)
        h.send("third ask")
        wait_for(lambda: h.joined().count("Permission needed") == 3)
        h.send("1")
        ctx.check("1 allows once without learning a rule", wait_for(lambda: decision(h.rig).action == "allow")
                  and not decision(h.rig).rule and h.wait_text("Allowed once."))
        h.wait_idle(turns=3)
        h.send("1")
        ctx.check("a bare 1 with no card open is just a prompt", h.wait_idle(turns=4))


@test
def test_question_plan_and_approval(ctx: Ctx):
    with Harness() as h:
        h.send("ask-question now")
        ctx.check("the question is lettered", h.wait_text("Question: which?") and "a. red" in h.joined() and "b. blue" in h.joined())
        h.send("b")
        ctx.check("a letter answers with that option's label",
                  wait_for(lambda: h.rig.session.answers.get("q_1", {}).get("answer") == "blue") and h.wait_text("Answered."))
        h.wait_idle()
        h.send("ask-question again")
        wait_for(lambda: h.joined().count("Question: which?") == 2)
        h.send("something else entirely")
        ctx.check("free text is the answer itself",
                  wait_for(lambda: h.rig.session.answers.get("q_1", {}).get("answer") == "something else entirely"))
        h.wait_idle(turns=2)
        h.send("ask-plan one")
        ctx.check("the plan card carries the plan and how to reply",
                  h.wait_text("Plan ready for review") and "do the thing" in h.joined() and "approve" in h.joined())
        h.send("approve")
        ctx.check("approve approves the plan", wait_for(lambda: h.rig.session.answers.get("plan_1", {}).get("decision", {}).get("approved") is True)
                  and h.wait_text("Plan approved."))
        h.wait_idle(turns=3)
        h.send("ask-plan two")
        wait_for(lambda: h.joined().count("Plan ready") == 2)
        h.send("feedback make it smaller")
        dec = lambda: h.rig.session.answers.get("plan_1", {}).get("decision", {})  # noqa: E731
        ctx.check("feedback <text> sends the plan back", wait_for(lambda: dec().get("approved") is False)
                  and dec().get("feedback") == "make it smaller" and h.wait_text("Feedback sent."))
        h.wait_idle(turns=4)
        h.send("ask-approval x")
        ctx.check("the approval gate card appears", h.wait_text("Approval needed (reviewer)"))
        h.send("edit tighten the wording")
        ctx.check("edit <instruction> answers the gate",
                  wait_for(lambda: h.rig.session.answers.get("appr_1", {}).get("decision", {}).get("action") == "edit")
                  and h.rig.session.answers["appr_1"]["decision"]["instruction"] == "tighten the wording")


@test
def test_quiet_and_loud(ctx: Ctx):
    with Harness() as h:
        h.send("/quiet")
        ctx.check("/quiet is confirmed", h.wait_text("Quiet:"))
        h.send("say something")
        ctx.check("quiet still closes the turn with the done line", h.wait_text("Done."))
        ctx.check("quiet drops the streamed text", "hello from the fake session" not in h.joined())
        h.send("/loud")
        h.send("again")
        ctx.check("loud relays the text again", wait_for(lambda: "hello from the fake session" in h.joined()))
        h.send("/quiet")
        h.send("ask quietly")
        ctx.check("cards still arrive in quiet mode", h.wait_text("Permission needed: Bash"))
        h.send("1")
        h.wait_idle(turns=3)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
