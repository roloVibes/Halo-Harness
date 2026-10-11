"""halo_harness.remote.cli_pair -- `halo remote signal pair | peers | unpair |
reverify` (Halo 2.0.9 round 4). These work on `peers.json` / `pending.json`
(the same files the bridge uses, under a file lock), so they run whether or
not the bridge is up; the trust step of an approval is finished by the
running bridge within a second."""

from __future__ import annotations

import time
from datetime import datetime

from halo_harness.remote import cli_common as C
from halo_harness.remote import signing
from halo_harness.remote.pairing import Pairing, PairingError


def _when(ts) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return "?"


def _grouped(sn) -> str:
    digits = "".join(str(sn or "").split())
    return " ".join(digits[i:i + 5] for i in range(0, len(digits), 5)) or "(not known yet)"


def peer_rows(pairing: Pairing) -> list:
    """Paired phones for display: no signing secret, ever."""
    rows = []
    for aci, p in sorted(pairing.peers().items(), key=lambda kv: kv[1].get("paired_at") or 0):
        rows.append({"aci": aci, "aci_prefix": aci[:8], "number": p.get("number"), "paired_at": p.get("paired_at"),
                     "signed": bool(p.get("signed", True)), "blocked": bool(p.get("blocked_until_reverified"))})
    return rows


def pending_rows(pairing: Pairing) -> list:
    return [{"index": i, "aci": r["aci"], "aci_prefix": r["aci"][:8], "number": r.get("number"),
             "safety_number": r.get("safety_number"), "state": r.get("state"), "first_seen": r.get("first_seen")}
            for i, r in enumerate(pairing.pending(), 1)]


def pair_secret_view(pairing: Pairing, aci: str) -> dict:
    p = pairing.peer(aci) or {}
    secret = bytes.fromhex((p.get("signing") or {}).get("secret_hex") or "")
    return {"phrase": signing.secret_to_phrase(secret), "link": signing.pair_uri(secret, aci)}


def show_pairing(view: dict, ascii_only: bool = False) -> None:
    print("Paired. Signing secret (this is the only time it is shown here):")
    print(view["phrase"])
    print("\nOr as a link / QR code for a signing app:\n" + view["link"])
    C.print_qr(view["link"], ascii_only)
    print("Every command from the phone ends with ' #<counter>:<mac>' (docs/REMOTE.md, Signing).")


def _approve(a, pairing: Pairing) -> int:
    rows = pending_rows(pairing)
    target = None
    if a.approve.isdigit() and 1 <= int(a.approve) <= len(rows):
        target = rows[int(a.approve) - 1]["aci"]
    else:
        target, err = C.resolve_prefix([r["aci"] for r in rows], a.approve, "contact request")
        if target is None:
            return C.fail(a.json, "no_such_request", err)
    try:
        ap = pairing.approve(target)
    except PairingError as e:
        return C.fail(a.json, "approve_failed", str(e))
    out = {"ok": True, "aci_prefix": target[:8], "code": ap.code, "expires": ap.expires, "trusted": ap.trusted}
    if not a.json:
        print(f"Pairing code for {target[:8]}: {ap.code}   (valid until {_when(ap.expires)})")
        print("On the phone, send exactly this code to the Halo number as the next message.")
        if not ap.trusted:
            print("The running bridge completes the trust step; start it with `halo remote signal run` if it is not up.")
    end = time.time() + max(0.0, float(a.wait))
    while not pairing.is_paired(target) and time.time() < end:
        time.sleep(0.5)
    if pairing.is_paired(target):
        view = pair_secret_view(pairing, target)
        out.update(paired=True, **view)
        if not a.json:
            show_pairing(view, a.ascii)
    else:
        out["paired"] = False
        if not a.json and a.wait:
            print("Not paired yet; the code stays valid until the time above.")
    if a.json:
        C.emit_json(out)
    return 0


def cmd_pair(argv: list) -> int:
    p = C.make_parser("pair", "List contact requests; --approve N issues the one-time pairing code.")
    p.add_argument("--approve", metavar="N", help="request number (or ACI prefix) to approve")
    p.add_argument("--wait", type=float, default=600.0, help="seconds to wait for the phone to send the code (default 600)")
    p.add_argument("--ascii", action="store_true", help="draw QR codes with # instead of block glyphs")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    pairing = Pairing()
    if a.approve:
        return _approve(a, pairing)
    rows, notices = pending_rows(pairing), pairing.notices()
    pairing.clear_notices()
    if a.json:
        C.emit_json({"ok": True, "pending": rows, "notices": notices})
        return 0
    if not rows:
        print("No contact requests. On the phone, open a chat with the Halo number and send any message; "
              "it appears here once the bridge has seen it.")
    for r in rows:
        print(f"{r['index']}  {r['aci_prefix']}  {r['number'] or '(no number)'}  [{r['state']}]  first seen {_when(r['first_seen'])}")
        print(f"   safety number: {_grouped(r['safety_number'])}")
    if rows:
        print("Compare the safety number with the phone (chat name, View safety number), then:\n"
              "  halo remote signal pair --approve <N>")
    for n in notices:
        print(f"notice: {n.get('text')} ({n.get('kind')}, {str(n.get('aci') or '')[:8] or 'bridge'})")
    return 0


def cmd_peers(argv: list) -> int:
    a, rc = C.parse(C.make_parser("peers", "List paired phones."), argv)
    if a is None:
        return rc
    rows = peer_rows(Pairing())
    if a.json:
        C.emit_json({"ok": True, "peers": rows})
        return 0
    if not rows:
        print("No paired phones.")
    for r in rows:
        flags = ("signed" if r["signed"] else "unsigned") + (", BLOCKED (reverify)" if r["blocked"] else "")
        print(f"{r['aci_prefix']}  {r['number'] or '(no number)'}  paired {_when(r['paired_at'])}  {flags}")
    return 0


def _peer_verb(verb: str, argv: list) -> int:
    p = C.make_parser(verb, {"unpair": "Remove a paired phone.", "reverify": "Trust a blocked phone's new safety number."}[verb])
    p.add_argument("aci_prefix", help="the first characters of the phone's ACI (see `peers`)")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    pairing = Pairing()
    aci, err = C.resolve_prefix(list(pairing.peers()), a.aci_prefix, "paired phone")
    if aci is None:
        return C.fail(a.json, "no_such_peer", err)
    if verb == "unpair":
        pairing.unpair(aci)
        out = {"ok": True, "unpaired": aci[:8]}
        msg = f"Unpaired {aci[:8]}. Its signing secret is gone."
    else:
        try:
            done = pairing.reverify(aci)
        except PairingError as e:
            return C.fail(a.json, "reverify_failed", str(e))
        out = {"ok": True, "reverified": aci[:8], "done": done}
        msg = (f"Reverified {aci[:8]}." if done else
               f"Queued the trust step for {aci[:8]}; the running bridge finishes it within a second.")
    C.emit_json(out) if a.json else print(msg)
    return 0


def cmd_unpair(argv: list) -> int:
    return _peer_verb("unpair", argv)


def cmd_reverify(argv: list) -> int:
    return _peer_verb("reverify", argv)
