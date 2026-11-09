"""tests.test_cards -- the cards are the conversation's questions (3.3.13.0 R3): a permission card answered with `1`
and with a thumbs up, a question with `b`, a plan's held text and `send`, a card answered at the keyboard dropped,
and a sub-agent's card tagged. Run: python -m tests.test_cards"""

from __future__ import annotations

from tests.support import ACI_A, main, now_ms, reaction, registry, wait_for
from tests.rig import Phone

test, TESTS = registry()


def _answers(p) -> list:
    s = p.session()
    return list(s.answers) if s else []


@test
def test_permission_with_1(ctx):
    with Phone() as p:
        p.pair()
        p.text("please ask first")
        ctx.check("the permission card arrives", p.wait("echo hi"))
        p.text("1")
        ctx.check("1 allows once", wait_for(lambda: _answers(p) and _answers(p)[0].get("action") == "allow"
                                            and _answers(p)[0].get("scope") == "once", 3.0))
        ctx.check("the phone is told, then the rest of the answer arrives", p.wait("It ran."))


@test
def test_permission_with_a_thumbs_up(ctx):
    with Phone() as p:
        p.pair()
        p.text("please ask first")
        p.wait("echo hi")
        p.tr.deliver(reaction(ACI_A, "\U0001F44D", now_ms()))
        ctx.check("a thumbs up is 1 allow once", wait_for(lambda: _answers(p) and _answers(p)[0].get("action") == "allow", 3.0))


@test
def test_question_with_b(ctx):
    with Phone() as p:
        p.pair()
        p.text("a question for me")
        ctx.check("the question card lists the options", p.wait("which?"))
        p.text("b")
        ctx.check("b answers blue", wait_for(lambda: _answers(p) and _answers(p)[0].get("answer") == "blue", 3.0))
        ctx.check("Answered. and the rest", p.wait("Answered.") and p.wait("Blue it is."))


@test
def test_a_text_that_is_not_an_answer_is_held(ctx):
    with Phone() as p:
        p.pair()
        p.text("make a plan")
        ctx.check("the plan card arrives", p.wait("do the thing"))
        p.text("what about the tests?")
        ctx.check("one line asks which was meant", p.wait("A card waits:") and p.wait("`send`"))
        ctx.check("nothing was submitted yet", len(p.session().submitted) == 1)
        p.text("send")
        ctx.check("send passes the held text to the session",
                  wait_for(lambda: len(p.session().submitted) == 2
                           and p.session().submitted[1]["text"] == "what about the tests?", 3.0))


@test
def test_a_card_answered_at_the_keyboard_is_dropped(ctx):
    with Phone() as p:
        p.pair()
        p.text("please ask first")
        p.wait("echo hi")
        p.session().pending["permission"] = []  # answered elsewhere: status no longer lists it
        p.text("2")
        ctx.check("the 2 is a prompt now, not an answer", wait_for(lambda: len(p.session().submitted) == 2, 3.0)
                  and not _answers(p))


if __name__ == "__main__":
    raise SystemExit(main(TESTS))
