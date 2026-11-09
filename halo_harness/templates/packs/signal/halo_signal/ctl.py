"""halo_signal.ctl -- `/signal ...` in a session (the pack's entry command runs it; no model call), and the same
words after `bin/signal.py ctl` in a terminal.

    /signal                         the bridge's state, the account, the phones, the pairing phrase, notices
    /signal pair                    a six-word phrase (and its QR code) the phone texts to pair in one message;
                                    again while it is open: its state ("waiting for a text ..." / "paired +1...0100")
    /signal phones                  the paired phones: number, signing, home folder, what arrives unprompted
    /signal unpair <n>              /signal reverify <n>           /signal home <n> <folder>
    /signal sign on|off <n>         per-command signatures for one phone (on: a new secret, shown here once)
    /signal off | on                the bridge stops answering and its service stops / both back on
    /signal url                     the link (and QR code) that opens a chat with Halo's number on the phone
    /signal test                    a test message to every paired phone (or to Note to Self with a linked account)
    /signal link | register ...     the account: ctl_account.py
    /signal notices                 what the bridge noted (a stranger, a changed safety number, a rate limit)
"""

from __future__ import annotations

import time

from halo_harness.ext import remote as R

from halo_signal import PACK, files, health, settings, signing
from halo_signal.pairing import Pairing, PairingError, mask
from halo_signal.phones import Phones, short

ENTRY = "/signal"


def _when(ts) -> str:
    try:
        return time.strftime("%H:%M", time.localtime(float(ts)))
    except (TypeError, ValueError, OSError):
        return "?"


def _pairing() -> Pairing:
    return Pairing(ttl=int(settings.get("pair_ttl_s")))


def _pick(pairing: Pairing, arg: str) -> "tuple[str | None, str]":
    rows = sorted(pairing.peers().items(), key=lambda kv: kv[1].get("paired_at") or 0)
    if arg.isdigit() and 1 <= int(arg) <= len(rows):
        return rows[int(arg) - 1][0], ""
    hits = [aci for aci, _ in rows if arg and aci.startswith(arg)]
    return (hits[0], "") if len(hits) == 1 else (None, f"no paired phone {arg!r} (/signal phones lists them)")


def status(args) -> int:
    svc = R.service(PACK, "bridge")
    h = health.read()
    cfg = settings.load_signal()
    pairing = _pairing()
    lines = [f"Signal pack ({ENTRY}): the bridge is " + (_svc_line(svc) if svc else
             "not in the supervisor's list yet (enable the pack with the services grant; halo supervise runs it)"),
             f"  last word from the bridge: {h.get('state')} -- {h.get('line') or ''}".rstrip(" -"),
             f"  account: {cfg.get('account') or 'none yet (/signal link, or /signal register +<number>)'}"
             + (f" ({cfg.get('identity_model')})" if cfg.get("account") else ""),
             f"  phones: {len(pairing.peers())} paired (/signal phones); off switch: "
             f"{'on' if settings.get('on') else 'OFF (/signal on)'}"]
    inv = pairing.invite_state()
    if inv["state"] != "none":
        lines.append("  pairing phrase: " + _invite_line(inv))
    notices = pairing.notices()
    if notices:
        lines.append(f"  {len(notices)} notice(s): /signal notices")
    lines += ["", f"Commands: {ENTRY} pair | phones | unpair <n> | sign on|off <n> | home <n> <folder> | off | on | url"
              " | test | link | register | notices"]
    print("\n".join(lines))
    return 0


def _svc_line(row: dict) -> str:
    if row.get("state") == "running":
        return f"running since {_when(row.get('since'))}" + (f" ({row['line']})" if row.get("line") else "")
    return f"{row.get('state')}: {row.get('line') or 'not started'}"


def _invite_line(inv: dict) -> str:
    if inv["state"] == "waiting":
        return f"open until {_when(inv.get('expires'))}, waiting for a text from a new number"
    if inv["state"] == "paired":
        p = inv.get("paired") or {}
        return f"used: paired {p.get('number')} ({p.get('aci')})"
    return f"{inv['state']}" + (f" ({inv['why']})" if inv.get("why") else "") + " -- /signal pair makes a new one"


def pair(args) -> int:
    pairing = _pairing()
    inv = pairing.invite_state()
    if inv["state"] == "waiting" and "--new" not in args:
        print("A pairing phrase is open: " + _invite_line(inv) + ".\n(It was shown when it was made and is not kept in "
              "the clear; `/signal pair --new` makes another.)")
        return 0
    got = pairing.invite()
    cfg = settings.load_signal()
    to = ("your own Note to Self chat" if cfg.get("identity_model") == "linked" else
          f"Halo's number {cfg.get('account') or '(no account yet: /signal link or /signal register)'}")
    print(f"Pairing phrase (good until {_when(got['expires'])}):\n\n    {got['phrase']}\n")
    print(f"From the phone, text exactly these six words to {to}. That one message pairs it; nothing else is "
          "needed. Or scan this with the phone's camera and paste the words into the chat:\n")
    print(R.qr_text(got["phrase"]))
    print(f"\nThen `{ENTRY} pair` (or Setup -> Signal) shows \"paired\". Signing stays off: the Signal session is the "
          "channel's own authentication (README, Threat model); `/signal sign on <n>` adds it per phone.")
    return 0


def phones(args) -> int:
    pairing, ph = _pairing(), Phones()
    rows = sorted(pairing.peers().items(), key=lambda kv: kv[1].get("paired_at") or 0)
    if not rows:
        print("No paired phones. /signal pair makes the phrase a phone texts to pair.")
        return 0
    for i, (aci, p) in enumerate(rows, 1):
        row = ph.get(aci)
        flags = ("signed" if p.get("signed") else "unsigned") + (", BLOCKED: /signal reverify " + str(i)
                                                                  if p.get("blocked_until_reverified") else "")
        print(f"{i}. {mask(p.get('number'))} ({aci[:8]})  {flags}  home {short(row['home'])}  "
              f"notes: {', '.join(row['notify']) or 'none'}  {row.get('verbosity')}")
    return 0


def _phone_verb(verb: str, args) -> int:
    pairing = _pairing()
    if not args:
        print(f"Usage: {ENTRY} {verb} <n> (/signal phones)")
        return 2
    aci, why = _pick(pairing, args[0])
    if aci is None:
        print(why)
        return 1
    if verb == "unpair":
        pairing.unpair(aci)
        Phones().forget(aci)
        print(f"Unpaired {aci[:8]}; it is no longer answered.")
    elif verb == "reverify":
        try:
            done = pairing.reverify(aci)
        except PairingError as e:
            print(str(e))
            return 1
        print(f"Reverified {aci[:8]}." if done else f"Queued the trust step for {aci[:8]}; the running bridge does it.")
    elif verb == "home":
        from halo_signal.phones import resolve_home
        folder, why = resolve_home(" ".join(args[1:]), Phones().get(aci)["home"])
        if folder is None:
            print(why)
            return 1
        Phones().set(aci, home=folder)
        print(f"{aci[:8]}'s new sessions start in {short(folder)}.")
    return 0


def sign(args) -> int:
    if len(args) < 2 or args[0] not in ("on", "off"):
        print(f"Usage: {ENTRY} sign on|off <n>")
        return 2
    pairing = _pairing()
    aci, why = _pick(pairing, args[1])
    if aci is None:
        print(why)
        return 1
    secret = pairing.set_signed(aci, args[0] == "on")
    if args[0] == "off":
        print(f"Signing off for {aci[:8]}: its plain texts are read.")
        return 0
    print(f"Signing on for {aci[:8]}. Its secret, shown this once (a signing app reads the link or the QR code):\n")
    print(signing.secret_to_phrase(secret) + "\n\n" + signing.pair_uri(secret, aci))
    print(R.qr_text(signing.pair_uri(secret, aci)))
    print("Every message from it now ends with ' #<counter>:<mac>' (README, Signing); /signal sign off undoes it.")
    return 0


def onoff(verb: str) -> int:
    on = verb == "on"
    lines = settings.put("on", on)
    if lines:
        print("\n".join(lines))
        return 1
    print(("The bridge answers again. " if on else "The bridge stops answering and its service stops. ")
          + R.service_ask(PACK, "bridge", "start" if on else "stop"))
    return 0


def url(args) -> int:
    cfg = settings.load_signal()
    account = str(cfg.get("account") or "")
    if cfg.get("identity_model") == "linked" or not account.startswith("+"):
        print("With a linked account the conversation is your own Note to Self chat: open it on the phone.")
        return 0
    link = f"https://signal.me/#p/{account}"
    print(f"{link}\n(open it on the phone, or scan this, to start the chat with Halo's number)\n")
    print(R.qr_text(link))
    return 0


def notices(args) -> int:
    pairing = _pairing()
    rows = pairing.notices()
    for n in rows:
        print(f"{_when(n.get('ts'))}  {n.get('text')} ({n.get('kind')}, {str(n.get('aci') or '')[:8] or 'bridge'})")
    pairing.clear_notices()
    print("" if rows else "No notices.")
    return 0


def test(args) -> int:
    files.write_text(files.path("requests", f"test-{int(time.time() * 1000)}.json"), '{"kind": "test"}')
    svc = R.service(PACK, "bridge") or {}
    print("Asked the bridge to send a test message to every paired phone (Note to Self with a linked account)."
          + ("" if svc.get("state") == "running" else " It is not running: it sends it once the supervisor starts it."))
    return 0
