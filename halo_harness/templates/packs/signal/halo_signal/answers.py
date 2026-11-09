"""halo_signal.answers -- a text (or a reaction) that answers an open card.

The cards -- permission, question, plan, approval -- are the conversation's questions, answered as before: a
permission by `1`-`4` (`4 <reason>` sends the reason), a question by its letter(s) or any text (that text is the
answer), a plan by `approve` or `feedback <text>`, an approval by `accept`, `edit <instruction>` or `stop`.
3.3.13.0 R3: a plain text while a permission, plan or approval card is open that is not an answer to it is held and
asked about in one line ("A card waits: ... or `send` to pass it to the session"); `send` then submits it as the
prompt (a steer while the turn runs). A thumbs-up reaction on a card answers it as `1` / `approve` / `accept`, a
thumbs-down as `4` / `feedback` (no) / `stop`; a reaction on any other message answers nothing (3.3.13.1).

Before a text is taken as an answer the cards are checked against the session's `status.pending`, so a card answered
at the keyboard is dropped and the text is routed as usual.

    reconcile(b, rt)
    answer_open_card(b, rt, text) -> outcome | ""      "" = not an answer: route it as usual
    held_line(rt, text) -> line | ""                   the one line when `text` is held
    react(b, rt, emoji) -> outcome | ""
"""

from __future__ import annotations

from halo_harness.ext import remote as R

from halo_signal.session import call, one_line

UP, DOWN = ("\U0001F44D", "❤️", "✅"), ("\U0001F44E", "❌")


def _answer(b, rt, *, quiet: bool = False, **fields) -> dict:
    resp = call(b, rt, "answer", **fields)
    if not resp.get("ok") and not quiet:
        b.say(rt.aci, "That card is no longer waiting.")
    return resp


def reconcile(b, rt) -> None:
    if rt.client is None or not (rt.permission or rt.question or rt.plan or rt.approval):
        return
    resp = call(b, rt, "status")
    pend = (resp.get("result") or {}).get("pending") if resp.get("ok") else None
    if not isinstance(pend, dict):
        return

    def live(kind: str) -> set:
        return {str(x) for x in pend.get(kind) or []}
    rt.permission = [c for c in rt.permission if str(c.get("id")) in live("permission")]
    if rt.question and str(rt.question.get("id")) not in live("question"):
        rt.question = None
    if rt.plan and not pend.get("plan"):
        rt.plan = None
    if rt.approval and str(rt.approval.get("id")) not in live("approval"):
        rt.approval = None


def answer_open_card(b, rt, t: str) -> str:
    cards, low = R.cards, t.lower()
    reconcile(b, rt)
    if rt.permission:
        parsed = cards.parse_permission_reply(t)
        if parsed:
            action, scope, message, done = parsed
            card = rt.permission.pop(0)
            if _answer(b, rt, kind="permission", request_id=card["id"], action=action, scope=scope,
                       message=message).get("ok"):
                b.say(rt.aci, done)
                return "ok"
            return "stale"
    if rt.question:
        q = rt.question
        qs = q["questions"]
        q["answers"][qs[q["idx"]]["question"]] = cards.parse_question_reply(qs[q["idx"]], t)
        q["idx"] += 1
        if q["idx"] < len(qs):
            b.say(rt.aci, cards.question_card(qs[q["idx"]], q["idx"], len(qs)), card=True)
            return "ok"
        rt.question = None
        answers = q["answers"]
        value = next(iter(answers.values())) if len(answers) == 1 else answers
        if _answer(b, rt, quiet=True, kind="question", request_id=q["id"], answer=value).get("ok"):
            b.say(rt.aci, "Answered.")
            return "ok"
        return "" if len(qs) == 1 else "stale"
    if rt.plan and (low == "approve" or low.startswith("feedback ")):
        rt.plan = None
        approved = low == "approve"
        if _answer(b, rt, kind="plan", approved=approved, feedback="" if approved else t[9:].strip()).get("ok"):
            b.say(rt.aci, "Plan approved." if approved else "Feedback sent.")
            return "ok"
        return "stale"
    if rt.approval and (low in ("accept", "stop") or low.startswith("edit ")):
        card, rt.approval = rt.approval, None
        action = "edit" if low.startswith("edit ") else low
        if _answer(b, rt, kind="approval", request_id=card["id"], action=action,
                   instruction=t[5:].strip() if action == "edit" else "").get("ok"):
            b.say(rt.aci, {"accept": "Accepted.", "edit": "Edit sent.", "stop": "Stopped."}[action])
            return "ok"
        return "stale"
    return ""


def held_line(rt, t: str) -> str:
    """The line that holds `t` when a card that takes only its own answers is open; '' when none is."""
    if rt.permission:
        what = "reply 1-4 to answer the permission card"
    elif rt.plan:
        what = "reply `approve` or `feedback <text>` to the plan"
    elif rt.approval:
        what = "reply `accept`, `edit <instruction>` or `stop` to the approval"
    else:
        return ""
    rt.held = t
    return f"A card waits: {what}, or `send` to pass \"{one_line(t, 40)}\" to the session instead."


def react(b, rt, emoji: str, target=None) -> str:
    """A reaction on the phone: thumbs up / down on a card answers the oldest open card. 3.3.13.1 (REVIEW #18,
    REMOTE-1): only a reaction whose `targetSentTimestamp` is one of the cards' sent timestamps (outbox.sent_card);
    a heart on yesterday's answer while a card waits does nothing."""
    up, down = emoji in UP, emoji in DOWN
    if not (up or down) or not isinstance(target, int) or target not in rt.card_ts:
        return ""
    reconcile(b, rt)
    if rt.permission:
        return answer_open_card(b, rt, "1" if up else "4")
    if rt.plan:
        return answer_open_card(b, rt, "approve" if up else "feedback no")
    if rt.approval:
        return answer_open_card(b, rt, "accept" if up else "stop")
    return ""
