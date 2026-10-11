"""halo_harness.remote.bridge_commands -- what the phone's text means (Halo
2.0.9 round 3). `route(bridge, peer_state, text)` returns `(kind, outcome)`
for the audit line (never the text).

Order: an open card's answer first (permission `1`-`4`, question letters,
plan `approve`/`feedback`, approval `accept`/`edit`/`stop`), then `/commands`,
then plain text (a prompt, or a steer while a turn runs).

Chat commands: /sessions, /attach <n>, /status, /stop, /mode <name>,
/model <ref>, /effort <level>, /quiet, /loud, /tail <n>, /remote
pair|unpair|status|help; any other /x goes to the session as a slash command.
"""

from __future__ import annotations

from halo_harness.remote import bridge_cards as cards
from halo_harness.remote import bridge_session as sess
from halo_harness.remote.bridge_session import call, detach
from halo_harness.remote.client import ControlClient, default_token_for

HELP = ("Chat commands:\n/sessions  /attach <n>  /status  /stop\n/mode <name>  /model <ref>  /effort <level>\n"
        "/quiet  /loud  /tail <n>  /remote pair|unpair|status\nAnything else starting with / runs in the session; "
        "plain text is a prompt (or a steer while a turn runs).")


def _fail(b, aci: str, resp: dict) -> str:
    b.say(aci, "Error: " + cards.one_line(resp.get("error"), 400))
    return "error"


def route(b, rt, text: str) -> tuple:
    t = text.strip()
    if not t:
        return "empty", "ignored"
    if not t.startswith("/"):
        done = answer_open_card(b, rt, t)
        if done:
            return "answer", done
    if t.startswith("/"):
        name, _, args = t[1:].partition(" ")
        handler = HANDLERS.get(name.lower())
        if handler is not None:
            return f"cmd:{name.lower()}", handler(b, rt, args.strip()) or "ok"
        resp = call(b, rt, "slash", line=t)
        if not resp.get("ok"):
            return "slash", _fail(b, rt.aci, resp)
        b.say(rt.aci, (resp["result"].get("output") or "").strip() or f"Ran {t.split()[0]}.", markdown=True)
        return "slash", "ok"
    resp = call(b, rt, "submit", text=t)
    if not resp.get("ok"):
        return "prompt", _fail(b, rt.aci, resp)
    b.transport.typing.start(rt.aci)
    return "prompt", "steered" if resp["result"].get("steered") else "ok"


# ---- answers to open cards ----------------------------------------------------------------
def _answer(b, rt, **fields) -> dict:
    resp = call(b, rt, "answer", **fields)
    if not resp.get("ok"):
        b.say(rt.aci, "That card is no longer waiting.")
    return resp


def answer_open_card(b, rt, t: str) -> str:
    """The outcome string when `t` answered an open card, else ''."""
    low = t.lower()
    if rt.permission:
        parsed = cards.parse_permission_reply(t)
        if parsed:
            action, scope, message, done = parsed
            card = rt.permission.pop(0)
            if _answer(b, rt, kind="permission", request_id=card["id"], action=action, scope=scope,
                       message=message).get("ok"):
                b.say(rt.aci, done)
            return "ok"
    if rt.question and not t.startswith("/"):
        q = rt.question
        qs = q["questions"]
        q["answers"][qs[q["idx"]]["question"]] = cards.parse_question_reply(qs[q["idx"]], t)
        q["idx"] += 1
        if q["idx"] < len(qs):
            b.say(rt.aci, cards.question_card(qs[q["idx"]], q["idx"], len(qs)))
            return "ok"
        rt.question = None
        answers = q["answers"]
        value = next(iter(answers.values())) if len(answers) == 1 else answers
        if _answer(b, rt, kind="question", request_id=q["id"], answer=value).get("ok"):
            b.say(rt.aci, "Answered.")
        return "ok"
    if rt.plan and (low == "approve" or low.startswith("feedback ")):
        rt.plan = None
        approved = low == "approve"
        if _answer(b, rt, kind="plan", approved=approved, feedback="" if approved else t[9:].strip()).get("ok"):
            b.say(rt.aci, "Plan approved." if approved else "Feedback sent.")
        return "ok"
    if rt.approval and (low in ("accept", "stop") or low.startswith("edit ")):
        card, rt.approval = rt.approval, None
        action = "edit" if low.startswith("edit ") else low
        if _answer(b, rt, kind="approval", request_id=card["id"], action=action,
                   instruction=t[5:].strip() if action == "edit" else "").get("ok"):
            b.say(rt.aci, {"accept": "Accepted.", "edit": "Edit sent.", "stop": "Stopped."}[action])
        return "ok"
    return ""


# ---- chat commands ------------------------------------------------------------------------------
def _phase(entry: dict) -> str:
    try:
        c = ControlClient(entry["endpoint"], default_token_for(entry), timeout=1.0)
    except (OSError, ValueError, KeyError):
        return "unreachable"
    try:
        r = c.call("status")
        st = r.get("result") or {}
        waiting = sum(len(v) for v in (st.get("pending") or {}).values())
        return str(st.get("phase", "?")) + (" - waiting on you" if waiting else "")
    except (OSError, ValueError, TimeoutError):
        return "unreachable"
    finally:
        c.close()


def cmd_sessions(b, rt, args: str):
    rows = sess.live_sessions(b)
    rt.sessions = rows
    if not rows:
        b.say(rt.aci, "No live halo sessions.")
        return
    cur = (rt.entry or {}).get("session_id")
    b.say(rt.aci, "\n".join(f"{i}. {'* ' if r.get('session_id') == cur else ''}{sess.label(r)} - {_phase(r)}"
                            for i, r in enumerate(rows, 1)) + "\n(* = attached; /attach <n>)")


def cmd_attach(b, rt, args: str):
    rows = rt.sessions or sess.live_sessions(b)
    if not args.isdigit() or not 1 <= int(args) <= len(rows):
        b.say(rt.aci, "Usage: /attach <n> (see /sessions).")
        return "usage"
    err = sess.attach(b, rt, rows[int(args) - 1])
    b.say(rt.aci, err or "Attached to " + sess.label(rows[int(args) - 1]) + ".")
    return "error" if err else "ok"


def cmd_status(b, rt, args: str):
    resp = call(b, rt, "status")
    if resp.get("ok"):
        b.say(rt.aci, cards.status_text(resp["result"]))
        return "ok"
    return _fail(b, rt.aci, resp)


def _simple(cmd: str, field: str, done: str):
    def handler(b, rt, args: str):
        if not args and field:
            b.say(rt.aci, f"Usage: /{cmd} <{field}>")
            return "usage"
        resp = call(b, rt, cmd, **({field: args} if field else {}))
        if not resp.get("ok"):
            return _fail(b, rt.aci, resp)
        b.say(rt.aci, done.format(args=args))
        return "ok"
    return handler


def cmd_verbosity(level: str):
    def handler(b, rt, args: str):
        rt.verbosity = level
        b.say(rt.aci, "Quiet: only cards, errors and the closing line." if level == "quiet"
              else "Loud: the session's text is relayed too.")
    return handler


def cmd_tail(b, rt, args: str):
    n = int(args) if args.isdigit() else 5
    resp = call(b, rt, "tail", n=n)
    if not resp.get("ok"):
        return _fail(b, rt.aci, resp)
    b.say(rt.aci, resp["result"].get("markdown") or "(nothing yet)", markdown=True)


def cmd_remote(b, rt, args: str):
    sub = args.split()[0].lower() if args else "status"
    if sub == "unpair":
        b.pairing.unpair(rt.aci)
        detach(b, rt)
        b.say(rt.aci, "Unpaired. This phone is no longer answered.")
    elif sub == "pair":
        b.say(rt.aci, "To pair another phone, message the Halo number from it, then approve its contact request "
                      "with `halo remote signal pair` on the computer.")
    elif sub == "help":
        b.say(rt.aci, HELP)
    else:
        peer = b.pairing.peer(rt.aci) or {}
        b.say(rt.aci, f"Paired as {rt.aci[:8]}; signing {'on' if peer.get('signed', True) else 'off'}; "
                      f"relay {rt.verbosity}; session " + (sess.label(rt.entry) if rt.entry else "none attached") + ".")


HANDLERS = {
    "sessions": cmd_sessions, "attach": cmd_attach, "status": cmd_status,
    "stop": _simple("interrupt", "", "Interrupt sent."),
    "mode": _simple("mode", "mode", "Mode set to {args}."),
    "model": _simple("model", "ref", "Model switch queued: {args}."),
    "effort": _simple("effort", "level", "Effort set to {args}."),
    "quiet": cmd_verbosity("quiet"), "loud": cmd_verbosity("loud"), "tail": cmd_tail, "remote": cmd_remote,
}
