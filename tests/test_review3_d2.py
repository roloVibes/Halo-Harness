"""tests.test_review3_d2 -- the 3.0.2.0 review fix pass, round D2 (Signal
bridge), part 1: the bridge loop and the phone's commands.

  * review item 31   a card whose send fails is kept and sent again after the reconnect
  * review item 32   group messages are dropped (no command, no contact request, no nag)
  * review item 33   a card answered at the keyboard no longer swallows the phone's next text
  * review item 101  a command dropped by the per-minute limit keeps its counter unused
  * review item 108  non-ASCII digits in /attach, /tail, `pair --approve` get the usage path
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from halo_harness.remote import bridge_cards as cards
from halo_harness.remote import bridge_commands as commands
from halo_harness.remote import bridge_session as sess
from halo_harness.remote import signing
from halo_harness.remote.signal_errors import IOFailure, RateLimited
from tests.helpers.fake_signal_cli import data_message, sync_sent
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.signal_rig import ACI_A, ACI_B, Home, mk_bridge, pair_peer, pump, say

test, TESTS = new_registry()
OWN = "00000000-0000-4000-8000-0000000000aa"
PERM = {"event": "permission_request", "data": {"id": "perm_1", "name": "Bash", "input": {"command": "echo hi"},
                                                "reason": "needs approval", "suggested_rule": "Bash(echo:*)"}}
QDATA = {"id": "q_1", "input": {"questions": [{"question": "which?", "options": [{"label": "red"}, {"label": "blue"}]}]}}


class FakeClient:
    """A control-socket client: `status` reports `pending`, `answer` succeeds or not."""

    def __init__(self, pending=None, answer_ok: bool = True) -> None:
        self.pending, self.answer_ok, self.calls = pending, answer_ok, []

    def call(self, cmd: str, **fields) -> dict:
        self.calls.append((cmd, fields))
        if cmd == "status":
            res = {"phase": "running"}
            if self.pending is not None:
                res["pending"] = self.pending
            return {"ok": True, "result": res}
        if cmd == "answer":
            return {"ok": True, "result": {"resolved": True}} if self.answer_ok else {"ok": False, "error": "no pending"}
        if cmd == "submit":
            return {"ok": True, "result": {"steered": True}}
        return {"ok": True, "result": {}}

    def cmds(self) -> list:
        return [c for c, _ in self.calls]

    def close(self) -> None:
        pass


def _outcomes(b) -> list:
    return [r["outcome"] for r in b.audit.lines()]


@test
def test_item31_failed_card_is_kept_and_redelivered(ctx: Ctx):
    with Home():
        b, tr, clock = mk_bridge()
        pair_peer(b.pairing, ACI_A, signed=False)
        rt = b.rt(ACI_A)
        rt.client = FakeClient(pending={"permission": ["perm_1"]})
        tr.send_error = IOFailure("signal-cli link closed")
        sess.on_feed(b, rt, PERM)
        ctx.check("nothing reached the phone while the link was down", tr.texts(ACI_A) == [])
        ctx.check("the card is kept for the phone", len(rt.undelivered) >= 1 and rt.permission == [{"id": "perm_1"}])
        ctx.check("the failed card send is audited", "undelivered" in _outcomes(b))
        b.say(ACI_A, "plain relay text")
        ctx.check("plain text is not kept", all("relay" not in p[0] for p in rt.undelivered))
        tr.send_error = None
        b.handle({"kind": "notice", "name": "connected"})
        ctx.check("the card is sent after the reconnect", any("Permission needed: Bash" in t for t in tr.texts(ACI_A)))
        ctx.check("nothing is left kept, and the redelivery is audited",
                  rt.undelivered == [] and "redelivered" in _outcomes(b))


@test
def test_item31_kept_card_goes_before_newer_text_and_turn_end_drops_it(ctx: Ctx):
    with Home():
        b, tr, clock = mk_bridge()
        pair_peer(b.pairing, ACI_A, signed=False)
        rt = b.rt(ACI_A)
        rt.client = FakeClient(pending={"question": ["q_1"]})
        tr.send_error = RateLimited("paused", retry_after=30)
        sess.on_feed(b, rt, {"event": "question", "data": QDATA})
        ctx.check("a card refused during a -5 pause is kept", len(rt.undelivered) == 1)
        tr.send_error = None
        b.say(ACI_A, "later text")
        texts = tr.texts(ACI_A)
        ctx.check(f"the kept card goes out first, got {texts}",
                  len(texts) == 2 and texts[0].startswith("Question") and texts[1] == "later text")
        tr.send_error = IOFailure("down")
        sess.on_feed(b, rt, PERM)
        ctx.check("a second failed card is kept", rt.undelivered)
        tr.send_error = None
        sess.on_feed(b, rt, {"event": "turn_done", "data": {}})
        ctx.check("turn end drops the kept card with an audit line",
                  rt.undelivered == [] and "dropped_turn_done" in _outcomes(b))
        n = len(tr.texts(ACI_A))
        b.handle({"kind": "notice", "name": "connected"})
        ctx.check("a dropped card is not sent on the next reconnect", len(tr.texts(ACI_A)) == n)


@test
def test_item32_group_messages_are_dropped(ctx: Ctx):
    with Home():
        b, tr, clock = mk_bridge()
        pair_peer(b.pairing, ACI_A, signed=True)
        ts = int(clock.now * 1000)
        tr.deliver(data_message(ACI_A, "see you at 6", ts, group="grp-one"))
        tr.deliver(data_message(ACI_A, "/remote status", ts, group="grp-one"))
        tr.deliver(data_message(ACI_B, "hello all", ts, group="grp-one"))
        pump(b)
        ctx.check("no reply and no nag to the paired peer", tr.texts(ACI_A) == [])
        ctx.check("no audit line, no read receipt", b.audit.lines() == [] and tr.receipts == [])
        ctx.check("another group member is not a contact request", b.pairing.pending() == [])
        notes = [n for n in b.pairing.notices() if n["kind"] == "group_message"]
        ctx.check(f"one notice for the group, got {len(notes)}", len(notes) == 1)
        tr.deliver(data_message(ACI_B, "hi", ts, group="grp-two"))
        pump(b)
        ctx.check("a second group gets its own notice",
                  len([n for n in b.pairing.notices() if n["kind"] == "group_message"]) == 2)
        b.pairing.set_signed(ACI_A, False)
        say(b, tr, clock, ACI_A, "/remote status")
        ctx.check("a direct message still works", any("Paired as" in t for t in tr.texts(ACI_A)))


@test
def test_item32_linked_group_sync_is_ignored(ctx: Ctx):
    with Home():
        b, tr, clock = mk_bridge(identity_model="linked", own_aci=OWN)
        pair_peer(b.pairing, OWN, signed=False)
        tr.deliver(sync_sent(OWN, "/remote status", int(clock.now * 1000), group="grp-one"))
        pump(b)
        ctx.check("a group post synced from the owner's phone is not a command", tr.texts(OWN) == [])
        tr.deliver(sync_sent(OWN, "/remote status", int(clock.now * 1000)))
        pump(b)
        ctx.check("Note to Self still is", any("Paired as" in t for t in tr.texts(OWN)))


@test
def test_item33_keyboard_answered_question_does_not_swallow_the_prompt(ctx: Ctx):
    with Home():
        b, tr, clock = mk_bridge()
        pair_peer(b.pairing, ACI_A, signed=False)
        rt = b.rt(ACI_A)
        rt.client = FakeClient(pending={"permission": [], "question": [], "plan": [], "approval": []})
        rt.question = {"id": "q_1", "questions": cards.normalize_questions(QDATA), "idx": 0, "answers": {}}
        kind, outcome = commands.route(b, rt, "also run the linter after the build")
        ctx.check(f"the text is steered into the turn, got {(kind, outcome)}", (kind, outcome) == ("prompt", "steered"))
        ctx.check("no answer was sent for the stale card", "answer" not in rt.client.cmds())
        ctx.check("the stale card is gone", rt.question is None)
        ctx.check("no 'no longer waiting' reply", not any("no longer waiting" in t for t in tr.texts(ACI_A)))
        rt.approval, rt.plan = {"id": "appr_1"}, {"id": "plan_1"}
        ctx.check("a stale approval/plan keyword is routed as text",
                  commands.route(b, rt, "stop")[0] == "prompt" and rt.approval is None and rt.plan is None)


@test
def test_item33_stale_permission_at_the_head_is_skipped(ctx: Ctx):
    with Home():
        b, tr, clock = mk_bridge()
        pair_peer(b.pairing, ACI_A, signed=False)
        rt = b.rt(ACI_A)
        rt.client = FakeClient(pending={"permission": ["perm_2"]})
        rt.permission = [{"id": "perm_old"}, {"id": "perm_2"}]
        commands.route(b, rt, "1")
        answers = [f for c, f in rt.client.calls if c == "answer"]
        ctx.check(f"the reply answers the card still waiting, got {answers}",
                  len(answers) == 1 and answers[0]["request_id"] == "perm_2")
        rt.client = FakeClient(pending={"question": ["q_1"]}, answer_ok=False)
        rt.question = {"id": "q_1", "questions": cards.normalize_questions(QDATA), "idx": 0, "answers": {}}
        kind, _ = commands.route(b, rt, "a different idea")
        ctx.check("an answer refused in a race still reaches the session as text",
                  kind == "prompt" and "submit" in rt.client.cmds())
        rt.client = FakeClient(pending=None)
        rt.question = {"id": "q_1", "questions": cards.normalize_questions(QDATA), "idx": 0, "answers": {}}
        commands.route(b, rt, "a")
        ctx.check("a session without `pending` keeps the card and gets the answer", "answer" in rt.client.cmds())


@test
def test_item101_rate_limited_command_keeps_its_counter(ctx: Ctx):
    with Home():
        b, tr, clock = mk_bridge(rate_per_minute=3)
        secret = pair_peer(b.pairing, ACI_A, signed=True)
        msgs = [signing.sign(secret, n, "/remote status") for n in range(1, 5)]
        for m in msgs:
            say(b, tr, clock, ACI_A, m)
        joined = "\n".join(tr.texts(ACI_A))
        ctx.check("three answered, the fourth dropped", joined.count("Paired as") == 3 and "Too many commands" in joined)
        ctx.check("the dropped command did not advance the counter",
                  b.pairing.peer(ACI_A)["signing"]["counter"] == 3)
        clock.now += 61
        say(b, tr, clock, ACI_A, msgs[3])
        joined = "\n".join(tr.texts(ACI_A))
        ctx.check("the same message resent a minute later is accepted",
                  joined.count("Paired as") == 4 and "already used" not in joined)
        ctx.check("and now the counter is used", b.pairing.peer(ACI_A)["signing"]["counter"] == 4)


@test
def test_item108_non_ascii_digits(ctx: Ctx):
    with Home():
        b, tr, clock = mk_bridge()
        pair_peer(b.pairing, ACI_A, signed=False)
        rt = b.rt(ACI_A)
        ctx.check("/attach with a superscript digit gets the usage line",
                  commands.route(b, rt, "/attach ²") == ("cmd:attach", "usage") and "Usage: /attach" in tr.texts(ACI_A)[-1])
        rt.client = FakeClient()
        commands.route(b, rt, "/tail ٣")
        tails = [f for c, f in rt.client.calls if c == "tail"]
        ctx.check("/tail with an Arabic-Indic digit uses the default", tails == [{"n": 5}])
        b.pairing.note_contact(ACI_B, None, "1" * 60)
        ap = b.pairing.approve(ACI_B)
        ctx.check("a six-character non-ASCII digit string is not a code guess",
                  b.pairing.redeem(ACI_B, "²" * 6).status == "ignored" and ap.code)
        from halo_harness.remote import cli_pair
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cli_pair.cmd_pair(["--approve", "²", "--json", "--wait", "0"])
        ctx.check(f"pair --approve with a superscript is an ordinary failure, rc={rc}",
                  rc == 1 and json.loads(out.getvalue())["error"] == "no_such_request")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
