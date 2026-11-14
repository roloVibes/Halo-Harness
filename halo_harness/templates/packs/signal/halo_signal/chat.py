"""halo_signal.chat -- the bridge's own chat commands (any other `/x` runs in the session as its slash command).

    /sessions  /attach <n>  /new [<folder>]  /cd <folder>      which session the phone talks to, where new ones start
    /status  /cost  /tail [n]  /stop                          the attached session: its state, its spend, its last lines
    /mode <name>  /model <ref>  /effort <level>               change it
    /live                                                     this harness's sessions and what waits on you
    /notify [on|off <kind>]                                   what arrives unprompted: turn_done asks errors supervisor steward
    /quiet  /loud                                             only your own turns, or every turn of the attached session
    /file <path>  /shot                                       a file of the session's folder; Studio, now
    /signal [status|unpair]  /help
"""

from __future__ import annotations

from halo_harness.ext import remote as R

from halo_signal import media
from halo_signal.phones import KINDS, resolve_home, short
from halo_signal.session import call, detach, label, live_sessions, start_new

HELP = ("Chat commands:\n/sessions  /attach <n>  /new [folder]  /cd <folder>\n/status  /cost  /tail [n]  /stop\n"
        "/mode <name>  /model <ref>  /effort <level>\n/live  /notify [on|off <kind>]  /quiet  /loud\n"
        "/file <path>  /shot  /signal status|unpair\nAnything else starting with / runs in the session; plain text, "
        "a picture or a voice note is the prompt (a steer while a turn runs). A card: 1-4, a letter, approve, accept "
        "-- or a thumbs up / down on it.")


def _number(s: str) -> bool:
    return s.isascii() and s.isdigit()


def _fail(b, rt, resp: dict) -> str:
    b.say(rt.aci, "Error: " + R.cards.one_line(resp.get("error"), 400))
    return "error"


def _phase(b, row: dict) -> str:
    c = None
    try:
        c = b.sessions.connect(row["session_id"])
        if c is None:
            return "unreachable"
        st = (c.call("status") or {}).get("result") or {}
        waiting = sum(len(v) for v in (st.get("pending") or {}).values() if isinstance(v, list))
        return str(st.get("phase", "?")) + (" - waiting on you" if waiting else "")
    except (OSError, ValueError, TimeoutError, KeyError):
        return "unreachable"
    finally:
        if c is not None:
            c.close()


def cmd_sessions(b, rt, args: str):
    rows = live_sessions(b)
    rt.sessions = rows
    if not rows:
        b.say(rt.aci, "No live halo sessions. Send a text and one starts in " + short(b.phones.get(rt.aci)["home"]) + ".")
        return
    cur = (rt.entry or {}).get("session_id")
    b.say(rt.aci, "\n".join(f"{i}. {'* ' if r.get('session_id') == cur else ''}{label(r)} - {_phase(b, r)}"
                            for i, r in enumerate(rows, 1)) + "\n(* = attached; /attach <n>; /new starts another)")


def cmd_attach(b, rt, args: str):
    from halo_signal.session import attach
    rows = rt.sessions or live_sessions(b)
    if not _number(args) or not 1 <= int(args) <= len(rows):
        b.say(rt.aci, "Usage: /attach <n> (see /sessions).")
        return "usage"
    err = attach(b, rt, rows[int(args) - 1])
    b.say(rt.aci, err or "Attached to " + label(rows[int(args) - 1]) + ".")
    return "error" if err else "ok"


def cmd_new(b, rt, args: str):
    home = b.phones.get(rt.aci)["home"]
    if args:
        folder, why = resolve_home(args, home)
        if folder is None:
            b.say(rt.aci, why)
            return "usage"
        home = folder
    b.phones.set(rt.aci, session_id=None)
    start_new(b, rt, home)
    return "ok"


def cmd_cd(b, rt, args: str):
    folder, why = resolve_home(args, b.phones.get(rt.aci)["home"])
    if folder is None:
        b.say(rt.aci, why)
        return "usage"
    b.phones.set(rt.aci, home=folder)
    b.say(rt.aci, f"New sessions start in {short(folder)} (/new starts one there now).")
    return "ok"


def cmd_status(b, rt, args: str):
    if rt.client is None:
        b.say(rt.aci, "No session attached. A text starts one in " + short(b.phones.get(rt.aci)["home"]) + ".")
        return "no_session"
    resp = call(b, rt, "status")
    if not resp.get("ok"):
        return _fail(b, rt, resp)
    b.say(rt.aci, label(rt.entry) + "\n" + R.cards.status_text(resp["result"]))


def cmd_cost(b, rt, args: str):
    resp = call(b, rt, "status")
    if not resp.get("ok"):
        return _fail(b, rt, resp)
    st = resp["result"]
    cost = st.get("cost_usd")
    b.say(rt.aci, (f"This session so far: ${cost:.4f}{'+' if st.get('cost_complete') is False else ''}"
                   if isinstance(cost, (int, float)) else "This session's cost is not known (an unpriced model)")
          + f"; {st.get('total_input_tokens') or 0} tokens in, {st.get('total_output_tokens') or 0} out.")


def _simple(cmd: str, field: str, done: str):
    def handler(b, rt, args: str):
        if not args and field:
            b.say(rt.aci, f"Usage: /{cmd} <{field}>")
            return "usage"
        resp = call(b, rt, cmd, **({field: args} if field else {}))
        if not resp.get("ok"):
            return _fail(b, rt, resp)
        b.say(rt.aci, done.format(args=args))
    return handler


def cmd_verbosity(level: str):
    def handler(b, rt, args: str):
        rt.verbosity = level
        b.phones.set(rt.aci, verbosity=level)
        b.say(rt.aci, "Quiet: your own turns are answered; other turns only as /notify says." if level == "quiet"
              else "Loud: every turn of the attached session reaches you.")
    return handler


def cmd_tail(b, rt, args: str):
    resp = call(b, rt, "tail", n=int(args) if _number(args) else 5)
    if not resp.get("ok"):
        return _fail(b, rt, resp)
    b.say(rt.aci, resp["result"].get("markdown") or "(nothing yet)", markdown=True)


def cmd_live(b, rt, args: str):
    b.say(rt.aci, "\n".join(b.live_lines()) or "Nothing to show.")


def cmd_notify(b, rt, args: str):
    words = args.lower().split()
    if len(words) == 2 and words[1] in ("on", "off") and words[0] in KINDS:
        words.reverse()  # `/notify asks on` reads as well as `/notify on asks`
    if len(words) == 2 and words[0] in ("on", "off") and words[1] in KINDS:
        now = b.phones.notify_set(rt.aci, words[1], words[0] == "on")
        b.say(rt.aci, f"{words[1]} {words[0]}. Arriving unprompted: {', '.join(now) or 'nothing'}.")
        return "ok"
    if words:
        b.say(rt.aci, f"Usage: /notify on|off <kind> (kinds: {', '.join(KINDS)})")
        return "usage"
    now = b.phones.get(rt.aci)["notify"]
    b.say(rt.aci, f"Arriving unprompted: {', '.join(now) or 'nothing'} (of {', '.join(KINDS)}; /notify on|off <kind>).")


def cmd_signal(b, rt, args: str):
    sub = args.split()[0].lower() if args else "status"
    if sub == "unpair":
        b.pairing.unpair(rt.aci)
        b.phones.forget(rt.aci)
        detach(b, rt)
        b.say(rt.aci, "Unpaired. This phone is no longer answered; /signal pair on the computer pairs it again.")
        return "ok"
    peer = b.pairing.peer(rt.aci) or {}
    ph = b.phones.get(rt.aci)
    b.say(rt.aci, f"Paired as {rt.aci[:8]}; signing {'on' if peer.get('signed') else 'off'}; {rt.verbosity}; "
                  f"home {short(ph['home'])}; notes: {', '.join(ph['notify']) or 'none'}; session "
                  + (label(rt.entry) if rt.entry else "none attached") + ".")


def cmd_help(b, rt, args: str):
    b.say(rt.aci, HELP)


HANDLERS = {
    "sessions": cmd_sessions, "attach": cmd_attach, "new": cmd_new, "cd": cmd_cd, "status": cmd_status,
    "cost": cmd_cost, "stop": _simple("interrupt", "", "Interrupt sent."),
    "mode": _simple("mode", "mode", "Mode set to {args}."), "model": _simple("model", "ref", "Model switch queued: {args}."),
    "effort": _simple("effort", "level", "Effort set to {args}."), "quiet": cmd_verbosity("quiet"),
    "loud": cmd_verbosity("loud"), "tail": cmd_tail, "live": cmd_live, "notify": cmd_notify,
    "file": lambda b, rt, a: media.send_file(b, rt, a), "shot": lambda b, rt, a: media.shot(b, rt),
    "signal": cmd_signal, "remote": cmd_signal, "help": cmd_help,
}
